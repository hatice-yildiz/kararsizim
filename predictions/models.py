from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

MIN_CHOICES = 2
MAX_CHOICES = 4
CORRECT_POINTS = 10


class Category(models.TextChoices):
    SPORTS = "spor", "Spor"
    TECH = "teknoloji", "Teknoloji"
    ENTERTAINMENT = "eglence", "Eğlence"
    DAILY = "gunluk", "Günlük Hayat"
    OTHER = "diger", "Diğer"


class Status(models.TextChoices):
    OPEN = "open", "Açık"
    RESOLVED = "resolved", "Sonuçlandı"
    CANCELLED = "cancelled", "İptal edildi"


class QuestionQuerySet(models.QuerySet):
    """Görünen durumlar: Tahmine açık / Sonuç bekliyor / Sonuçlandı / İptal edildi."""

    def accepting(self):
        return self.filter(status=Status.OPEN, closes_at__gt=timezone.now())

    def awaiting(self):
        return self.filter(status=Status.OPEN, closes_at__lte=timezone.now())

    def finished(self):
        return self.filter(status__in=[Status.RESOLVED, Status.CANCELLED])


class Question(models.Model):
    title = models.CharField("başlık", max_length=200)
    description = models.TextField("açıklama", max_length=500, blank=True)
    resolution_criteria = models.TextField("sonucun belirlenme ölçütü", max_length=500)
    category = models.CharField("kategori", max_length=20, choices=Category.choices, default=Category.OTHER)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions")
    closes_at = models.DateTimeField("tahminlerin kapanışı")  # UTC saklanır
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Sonuç bilgileri (yalnızca sonuçlandıktan / iptalden sonra dolar, bir daha değişmez)
    # DO_NOTHING: soru silinirken (yalnızca tahmin almamışsa mümkün) seçenekleriyle birlikte gider;
    # PROTECT bu silmeyi engellerdi. Tutarlılığı veritabanı FK'sı (commit anında) ve tetikleyiciler korur.
    correct_choice = models.ForeignKey(
        "Choice", null=True, blank=True, on_delete=models.DO_NOTHING, related_name="+", db_constraint=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, max_length=500)
    resolution_source_url = models.URLField(blank=True, max_length=300)
    cancel_reason = models.TextField(blank=True, max_length=500)

    objects = QuestionQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["open", "resolved", "cancelled"]), name="question_status_valid"
            ),
            models.CheckConstraint(condition=Q(closes_at__gt=F("created_at")), name="question_closes_after_creation"),
            models.CheckConstraint(
                condition=Q(status="resolved", correct_choice__isnull=False, resolved_at__isnull=False)
                | Q(status="cancelled", correct_choice__isnull=True) & ~Q(cancel_reason="")
                | Q(status="open", correct_choice__isnull=True),
                name="question_state_consistent",
            ),
        ]

    def __str__(self):
        return self.title

    # --- Durum yardımcıları -------------------------------------------------
    @property
    def is_closed_by_time(self):
        return self.closes_at <= timezone.now()

    @property
    def accepts_predictions(self):
        return self.status == Status.OPEN and not self.is_closed_by_time

    @property
    def awaits_result(self):
        return self.status == Status.OPEN and self.is_closed_by_time

    @property
    def display_status(self):
        """'open' | 'pending' | 'resolved' | 'cancelled'"""
        if self.status == Status.OPEN:
            return "pending" if self.is_closed_by_time else "open"
        return self.status

    @property
    def display_status_label(self):
        return {
            "open": "Tahmine açık",
            "pending": "Sonuç bekliyor",
            "resolved": "Sonuçlandı",
            "cancelled": "İptal edildi",
        }[self.display_status]

    def has_predictions(self):
        return self.predictions.exists()


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("seçenek", max_length=100)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "position"], name="choice_unique_position"),
        ]

    def __str__(self):
        return self.text


class Prediction(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="predictions")
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, related_name="predictions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="predictions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Sonuçlanınca bir kez yazılır: doğruysa True/10 puan, yanlışsa False/0.
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["question", "user"], name="one_prediction_per_user_per_question"),
            models.CheckConstraint(
                condition=Q(points_awarded=0) | Q(points_awarded=CORRECT_POINTS, is_correct=True),
                name="prediction_points_valid",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.choice_id}"
