"""Tüm yazma işlemleri ve iş kuralları burada; view'lar yalnızca bunları çağırır.

Her işlem tek bir veritabanı işlemi (transaction) içinde ve soru satırı kilitlenerek yapılır.
Aynı kurallar PostgreSQL tetikleyicileriyle (bkz. migrations/0002_db_guards.py) bir kez daha
veritabanı seviyesinde uygulanır; yani arayüzü/sunucuyu atlayan bir yol olsa bile kural çiğnenemez.
"""
from contextlib import contextmanager

from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from .models import CORRECT_POINTS, MAX_CHOICES, MIN_CHOICES, Choice, Prediction, Question, Status


class ServiceError(Exception):
    """Kullanıcıya olduğu gibi gösterilebilen (Türkçe) iş kuralı hatası."""


DB_RULE_MESSAGE = "İşlem veritabanı kurallarına takıldı; sayfayı yenileyip tekrar dene."


@contextmanager
def _db_rules():
    """Veritabanı kuralı ihlallerini (benzersizlik/CHECK ya da tetikleyicinin RAISE EXCEPTION'ı, SQLSTATE P0001)
    kullanıcıya gösterilebilir ServiceError'a çevirir. Diğer veritabanı hataları olduğu gibi yükselir."""
    try:
        yield
    except DatabaseError as exc:
        cause = getattr(exc, "__cause__", None)
        if isinstance(exc, IntegrityError) or getattr(cause, "sqlstate", None) == "P0001":
            raise ServiceError(DB_RULE_MESSAGE) from exc
        raise


def _lock(pk):
    return Question.objects.select_for_update().get(pk=pk)


# --------------------------------------------------------------------------- tahmin
def make_prediction(user, question_pk, choice_pk):
    """Tahmini kaydeder ya da kapanışa kadar değiştirir. (prediction, created, changed) döner."""
    with _db_rules(), transaction.atomic():
        question = _lock(question_pk)
        if question.created_by_id == user.pk:
            raise ServiceError("Kendi sorunuza tahmin yapamazsınız.")
        if question.status != Status.OPEN:
            raise ServiceError("Bu soru artık tahmine açık değil.")
        if question.closes_at <= timezone.now():
            raise ServiceError("Bu sorunun tahmin süresi doldu.")
        choice = question.choices.filter(pk=choice_pk).first() if str(choice_pk).isdigit() else None
        if choice is None:
            raise ServiceError("Geçersiz seçenek.")

        prediction, created = Prediction.objects.get_or_create(
            question=question, user=user, defaults={"choice": choice}
        )
        changed = False
        if not created and prediction.choice_id != choice.pk:
            prediction.choice = choice
            prediction.save(update_fields=["choice", "updated_at"])
            changed = True
        return prediction, created, changed


# --------------------------------------------------------------------------- soru
def create_question(user, data):
    """data: title, description, resolution_criteria, category, closes_at (aware), choices (list[str])."""
    choices = data["choices"]
    if not MIN_CHOICES <= len(choices) <= MAX_CHOICES:
        raise ServiceError(f"{MIN_CHOICES}-{MAX_CHOICES} arası seçenek girmelisin.")
    with transaction.atomic():
        question = Question.objects.create(
            title=data["title"],
            description=data["description"],
            resolution_criteria=data["resolution_criteria"],
            category=data["category"],
            closes_at=data["closes_at"],
            created_by=user,
        )
        Choice.objects.bulk_create(
            Choice(question=question, text=text, position=i) for i, text in enumerate(choices, start=1)
        )
    return question


def update_question(user, question_pk, data):
    """İlk tahmine kadar her alan; sonrasında yalnızca açıklama ve kategori değişir."""
    with _db_rules(), transaction.atomic():
        question = _lock(question_pk)
        if question.created_by_id != user.pk:
            raise ServiceError("Bu soruyu yalnızca oluşturan kişi düzenleyebilir.")
        if question.status != Status.OPEN:
            raise ServiceError("Sonuçlanan ya da iptal edilen soru düzenlenemez.")

        question.description = data["description"]
        question.category = data["category"]
        fields = ["description", "category"]

        if not question.predictions.exists():
            question.title = data["title"]
            question.resolution_criteria = data["resolution_criteria"]
            question.closes_at = data["closes_at"]
            fields += ["title", "resolution_criteria", "closes_at"]
            question.choices.all().delete()
            Choice.objects.bulk_create(
                Choice(question=question, text=text, position=i)
                for i, text in enumerate(data["choices"], start=1)
            )
        question.save(update_fields=fields)
        return question


def delete_question(user, question_pk):
    """Yalnızca sahibi ve yalnızca henüz tahmin almamış soruyu siler."""
    with _db_rules(), transaction.atomic():
        question = _lock(question_pk)
        if question.created_by_id != user.pk:
            raise ServiceError("Bu soruyu yalnızca oluşturan kişi silebilir.")
        if question.predictions.exists():
            raise ServiceError("Tahmin almış bir soru silinemez.")
        question.delete()


# --------------------------------------------------------------------------- sonuç
def resolve_question(user, question_pk, choice_pk, note, source_url=""):
    """Doğru seçeneği açıklar ve puanları dağıtır. Tek seferliktir; dağıtılan puan sayısını döner.

    Güvence: durum geçişi tek bir koşullu UPDATE'tir (`WHERE status='open'`). Aynı soru için ikinci
    bir çağrı 0 satır etkiler ve hata verir; puanlar yalnızca bu geçişi başaran işlemde yazılır.
    """
    note = (note or "").strip()
    source_url = (source_url or "").strip()
    if len(note) < 5:
        raise ServiceError("Sonuç için kısa bir açıklama yazmalısın (en az 5 karakter).")
    with _db_rules(), transaction.atomic():
        question = _lock(question_pk)
        if question.created_by_id != user.pk:
            raise ServiceError("Sonucu yalnızca soruyu oluşturan kişi bildirebilir.")
        if question.status != Status.OPEN:
            raise ServiceError("Bu sorunun sonucu zaten açıklandı ya da soru iptal edildi.")
        now = timezone.now()
        if question.closes_at > now:
            raise ServiceError("Sonuç, tahmin süresi dolduktan sonra belirlenebilir.")
        choice = question.choices.filter(pk=choice_pk).first() if str(choice_pk).isdigit() else None
        if choice is None:
            raise ServiceError("Doğru seçeneği seçmelisin.")

        moved = Question.objects.filter(pk=question.pk, status=Status.OPEN, closes_at__lte=now).update(
            status=Status.RESOLVED,
            correct_choice=choice,
            resolved_at=now,
            resolution_note=note,
            resolution_source_url=source_url,
        )
        if moved != 1:  # başka bir istek öne geçti
            raise ServiceError("Bu sorunun sonucu zaten açıklandı.")

        winners = (
            Prediction.objects.filter(question=question, choice=choice)
            .exclude(user_id=question.created_by_id)
            .update(is_correct=True, points_awarded=CORRECT_POINTS)
        )
        Prediction.objects.filter(question=question).exclude(choice=choice).update(is_correct=False)
        return winners


def cancel_question(user, question_pk, reason):
    """Sonuç belirlenemiyorsa gerekçeyle iptal eder; kimseye puan verilmez."""
    reason = (reason or "").strip()
    if len(reason) < 10:
        raise ServiceError("İptal için bir gerekçe yazmalısın (en az 10 karakter).")
    with _db_rules(), transaction.atomic():
        question = _lock(question_pk)
        if question.created_by_id != user.pk:
            raise ServiceError("Soruyu yalnızca oluşturan kişi iptal edebilir.")
        now = timezone.now()
        moved = Question.objects.filter(pk=question.pk, status=Status.OPEN).update(
            status=Status.CANCELLED, cancel_reason=reason, resolved_at=now
        )
        if moved != 1:
            raise ServiceError("Bu soru zaten sonuçlandı ya da iptal edildi.")
