from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PollForm
from django.views.decorators.http import require_POST

from .models import Option, Poll, Vote
from .voting import get_voter_key


def _poll_queryset():
    return (
        Poll.objects.select_related("created_by")
        .annotate(option_count=Count("options", distinct=True), total_votes=Count("votes", distinct=True))
        .order_by("-created_at", "-pk")  # annotate() Meta.ordering'i düşürür, açıkça belirt
    )


def home(request):
    paginator = Paginator(_poll_queryset(), 10)
    page = paginator.get_page(request.GET.get("sayfa"))
    return render(request, "polls/home.html", {"page": page})


def build_results(poll, user_option_id=None):
    """Seçenekler için oy sayısı, yüzde ve vurgu bilgisi."""
    options = list(poll.options.annotate(vote_count=Count("votes")))
    total = sum(o.vote_count for o in options)
    top = max((o.vote_count for o in options), default=0)
    for o in options:
        o.percent = round(o.vote_count * 100 / total) if total else 0
        o.is_leader = top > 0 and o.vote_count == top
        o.is_mine = o.pk == user_option_id
    return options, total


def popular(request):
    """En çok oy alan anketler (en az 1 oy), eşitlikte en yeni üstte."""
    polls = _poll_queryset().filter(total_votes__gt=0).order_by("-total_votes", "-created_at", "-pk")
    page = Paginator(polls, 10).get_page(request.GET.get("sayfa"))
    return render(request, "polls/popular.html", {"page": page})


def poll_detail(request, pk):
    poll = get_object_or_404(Poll.objects.select_related("created_by"), pk=pk)
    my_vote = Vote.objects.filter(poll=poll, voter_key=get_voter_key(request)).first()
    show_results = my_vote is not None  # sonuçlar yalnızca oy verdikten sonra görünür
    context = {"poll": poll, "is_owner": request.user == poll.created_by, "has_voted": my_vote is not None}
    if show_results:
        options, total = build_results(poll, my_vote.option_id if my_vote else None)
        context.update(options=options, total_votes=total, show_results=True)
    else:
        context.update(options=poll.options.all(), show_results=False)
    return render(request, "polls/detail.html", context)


@require_POST
def poll_vote(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    detail = redirect("poll_detail", pk=poll.pk)
    if not poll.is_active:
        messages.error(request, "Bu anket artık oylamaya kapalı.")
        return detail

    option_id = request.POST.get("option", "")
    option = poll.options.filter(pk=option_id).first() if option_id.isdigit() else None
    if option is None:
        messages.error(request, "Geçersiz seçenek.")
        return detail

    voter_key = get_voter_key(request)
    try:
        with transaction.atomic():
            Vote.objects.create(
                poll=poll,
                option=option,
                voter_key=voter_key,
                user=request.user if request.user.is_authenticated else None,
            )
    except IntegrityError:
        messages.error(request, "Bu ankete zaten oy verdin.")
        return detail
    messages.success(request, "Oyun kaydedildi!")
    return detail


@login_required
def poll_create(request):
    if request.method == "POST":
        form = PollForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                poll = Poll.objects.create(
                    question=form.cleaned_data["question"].strip(),
                    description=form.cleaned_data["description"].strip(),
                    created_by=request.user,
                )
                Option.objects.bulk_create(
                    Option(poll=poll, text=text, order=i)
                    for i, text in enumerate(form.cleaned_data["options"], start=1)
                )
            messages.success(request, "Anketin oluşturuldu!")
            return redirect("poll_detail", pk=poll.pk)
    else:
        form = PollForm()
    return render(request, "polls/create.html", {"form": form})


@login_required
def my_polls(request):
    polls = _poll_queryset().filter(created_by=request.user)
    return render(request, "polls/my_polls.html", {"polls": polls})


@login_required
def poll_delete(request, pk):
    poll = get_object_or_404(Poll, pk=pk, created_by=request.user)
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anket silindi.")
        return redirect("my_polls")
    return render(request, "polls/delete.html", {"poll": poll})
