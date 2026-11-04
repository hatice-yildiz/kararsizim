from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import CancelForm, QuestionForm, ResolveForm
from .models import CORRECT_POINTS, MAX_CHOICES, Category, Prediction, Question, Status

TABS = {
    "acik": ("Tahmine Açık", "accepting"),
    "bekleyen": ("Sonuç Bekliyor", "awaiting"),
    "sonuclanan": ("Sonuçlananlar", "finished"),
}
User = get_user_model()


def _questions():
    return Question.objects.select_related("created_by").annotate(prediction_count=Count("predictions"))


def _with_distribution(question, my_choice_id=None):
    """Seçenekleri tahmin sayısı ve yüzdesiyle döndürür."""
    choices = list(question.choices.annotate(count=Count("predictions")))
    total = sum(c.count for c in choices)
    top = max((c.count for c in choices), default=0)
    for c in choices:
        c.percent = round(c.count * 100 / total) if total else 0
        c.is_mine = c.pk == my_choice_id
        c.is_leader = top > 0 and c.count == top
        c.is_correct = question.correct_choice_id == c.pk
    return choices, total


# --------------------------------------------------------------------------- listeler
def home(request):
    tab = request.GET.get("sekme", "acik")
    if tab not in TABS:
        tab = "acik"
    category = request.GET.get("kategori", "")
    qs = getattr(_questions(), TABS[tab][1])()
    if category in Category.values:
        qs = qs.filter(category=category)
    else:
        category = ""
    order = {"acik": ("closes_at", "pk"), "bekleyen": ("closes_at", "pk"), "sonuclanan": ("-resolved_at", "-pk")}[tab]
    page = Paginator(qs.order_by(*order), 12).get_page(request.GET.get("sayfa"))
    counts = {
        "acik": Question.objects.accepting().count(),
        "bekleyen": Question.objects.awaiting().count(),
        "sonuclanan": Question.objects.finished().count(),
    }
    return render(request, "predictions/home.html", {
        "page": page, "tab": tab, "tabs": [(k, v[0], counts[k]) for k, v in TABS.items()],
        "category": category, "categories": Category.choices,
    })


def leaderboard(request):
    rows = list(
        User.objects.annotate(
            total_points=Coalesce(Sum("predictions__points_awarded"), 0),
            correct_count=Count("predictions", filter=Q(predictions__is_correct=True)),
            judged_count=Count("predictions", filter=Q(predictions__is_correct__isnull=False)),
        )
        .filter(judged_count__gt=0)
        .order_by("-total_points", "-correct_count", "username")
        .values("username", "total_points", "correct_count", "judged_count")[:100]  # e-posta hiç seçilmez
    )
    rank = 0
    for i, row in enumerate(rows):
        if i == 0 or (row["total_points"], row["correct_count"]) != (rows[i - 1]["total_points"], rows[i - 1]["correct_count"]):
            rank = i + 1
        row["rank"] = rank
        row["is_me"] = request.user.is_authenticated and row["username"] == request.user.username
    return render(request, "predictions/leaderboard.html", {"rows": rows})


@login_required
def my_predictions(request):
    predictions = (
        Prediction.objects.filter(user=request.user)
        .select_related("question__created_by", "choice", "question__correct_choice")
        .order_by("-updated_at", "-pk")
    )
    total_points = sum(p.points_awarded for p in predictions)
    correct = sum(1 for p in predictions if p.is_correct)
    page = Paginator(predictions, 20).get_page(request.GET.get("sayfa"))
    return render(request, "predictions/my_predictions.html", {
        "page": page, "total_points": total_points, "correct": correct, "total": len(predictions),
    })


@login_required
def my_questions(request):
    questions = _questions().filter(created_by=request.user).order_by("-created_at", "-pk")
    return render(request, "predictions/my_questions.html", {"questions": questions})


# --------------------------------------------------------------------------- detay / tahmin
def question_detail(request, pk):
    question = get_object_or_404(Question.objects.select_related("created_by", "correct_choice"), pk=pk)
    my_prediction = None
    if request.user.is_authenticated:
        my_prediction = Prediction.objects.filter(question=question, user=request.user).first()
    choices, total = _with_distribution(question, my_prediction.choice_id if my_prediction else None)
    is_owner = request.user.is_authenticated and request.user.pk == question.created_by_id
    return render(request, "predictions/detail.html", {
        "question": question, "choices": choices, "total": total, "my_prediction": my_prediction,
        "is_owner": is_owner,
        "can_predict": question.accepts_predictions and not is_owner,
        "can_delete": is_owner and total == 0,
        "can_edit": is_owner and question.status == Status.OPEN,
        "can_resolve": is_owner and question.awaits_result,
        "can_cancel": is_owner and question.status == Status.OPEN,
        "points": CORRECT_POINTS,
    })


@require_POST
@login_required
def predict(request, pk):
    get_object_or_404(Question, pk=pk)
    try:
        _, created, changed = services.make_prediction(request.user, pk, request.POST.get("choice", ""))
    except services.ServiceError as exc:
        messages.error(request, str(exc))
    else:
        if created:
            messages.success(request, "Tahminin kaydedildi!")
        elif changed:
            messages.success(request, "Tahminin güncellendi.")
        else:
            messages.info(request, "Zaten bu seçeneği seçmiştin.")
    return redirect("question_detail", pk=pk)


# --------------------------------------------------------------------------- yönetim
def _owned(request, pk):
    return get_object_or_404(Question, pk=pk, created_by=request.user)


@login_required
def question_create(request):
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            try:
                question = services.create_question(request.user, form.cleaned_data)
            except services.ServiceError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Tahmin sorun yayında!")
                return redirect("question_detail", pk=question.pk)
    else:
        form = QuestionForm()
    return render(request, "predictions/form.html", {"form": form, "editing": False, "max_choices": MAX_CHOICES})


@login_required
def question_edit(request, pk):
    question = _owned(request, pk)
    if question.status != Status.OPEN:
        messages.error(request, "Sonuçlanan ya da iptal edilen soru düzenlenemez.")
        return redirect("question_detail", pk=pk)
    locked = question.predictions.exists()
    if request.method == "POST":
        form = QuestionForm(request.POST, lock_core=locked)
        if form.is_valid():
            try:
                services.update_question(request.user, pk, form.cleaned_data)
            except services.ServiceError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Soru güncellendi.")
                return redirect("question_detail", pk=pk)
    else:
        initial = {
            "title": question.title, "description": question.description,
            "resolution_criteria": question.resolution_criteria, "category": question.category,
            "closes_at": timezone.localtime(question.closes_at).strftime("%Y-%m-%dT%H:%M"),
            "closes_at_utc": question.closes_at.isoformat(),
        }
        for i, choice in enumerate(question.choices.all(), start=1):
            initial[f"choice_{i}"] = choice.text
        form = QuestionForm(initial=initial, lock_core=locked)
    return render(request, "predictions/form.html", {
        "form": form, "editing": True, "locked": locked, "question": question, "max_choices": MAX_CHOICES,
    })


@login_required
def question_delete(request, pk):
    question = _owned(request, pk)
    if question.predictions.exists():
        messages.error(request, "Tahmin almış bir soru silinemez.")
        return redirect("question_detail", pk=pk)
    if request.method == "POST":
        try:
            services.delete_question(request.user, pk)
        except services.ServiceError as exc:
            messages.error(request, str(exc))
            return redirect("question_detail", pk=pk)
        messages.success(request, "Soru silindi.")
        return redirect("my_questions")
    return render(request, "predictions/delete.html", {"question": question})


@login_required
def question_resolve(request, pk):
    """İki adım: önce seçim + açıklama, sonra onay sayfası; onaylanınca geri alınamaz."""
    question = _owned(request, pk)
    if not question.awaits_result:
        messages.error(request, "Sonuç yalnızca tahmin süresi dolduktan sonra, bir kez bildirilebilir.")
        return redirect("question_detail", pk=pk)
    choices, total = _with_distribution(question)
    ctx = {"question": question, "choices": choices, "total": total, "points": CORRECT_POINTS}
    if request.method == "POST":
        form = ResolveForm(request.POST)
        valid_choice = question.choices.filter(pk=request.POST.get("choice", "")).first() if request.POST.get("choice", "").isdigit() else None
        if form.is_valid() and valid_choice:
            if request.POST.get("confirm") == "1":
                try:
                    winners = services.resolve_question(
                        request.user, pk, valid_choice.pk, form.cleaned_data["note"], form.cleaned_data["source_url"]
                    )
                except services.ServiceError as exc:
                    messages.error(request, str(exc))
                    return redirect("question_detail", pk=pk)
                messages.success(request, f"Sonuç açıklandı. {winners} kişi {CORRECT_POINTS} puan kazandı.")
                return redirect("question_detail", pk=pk)
            winners_preview = next(c.count for c in choices if c.pk == valid_choice.pk)
            return render(request, "predictions/resolve_confirm.html", {
                **ctx, "form": form, "chosen": valid_choice, "winners_preview": winners_preview,
            })
        if not valid_choice:
            form.add_error("choice", "Doğru seçeneği seçmelisin.")
    else:
        form = ResolveForm()
    return render(request, "predictions/resolve.html", {**ctx, "form": form})


@login_required
def question_cancel(request, pk):
    question = _owned(request, pk)
    if question.status != Status.OPEN:
        messages.error(request, "Bu soru zaten sonuçlandı ya da iptal edildi.")
        return redirect("question_detail", pk=pk)
    if request.method == "POST":
        form = CancelForm(request.POST)
        if form.is_valid():
            if request.POST.get("confirm") == "1":
                try:
                    services.cancel_question(request.user, pk, form.cleaned_data["reason"])
                except services.ServiceError as exc:
                    messages.error(request, str(exc))
                    return redirect("question_detail", pk=pk)
                messages.success(request, "Soru iptal edildi. Kimseye puan verilmedi.")
                return redirect("question_detail", pk=pk)
            return render(request, "predictions/cancel_confirm.html", {"question": question, "form": form})
    else:
        form = CancelForm()
    return render(request, "predictions/cancel.html", {"question": question, "form": form})
