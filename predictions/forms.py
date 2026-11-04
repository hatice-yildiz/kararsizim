from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django import forms
from django.utils import timezone

from .models import MAX_CHOICES, MIN_CHOICES, Category

MIN_LEAD = 60  # saniye: kapanış en az 1 dakika sonra olmalı


def parse_closing(local_value, utc_value):
    """Tarayıcının gönderdiği UTC değerini tercih eder; yoksa yerel (İstanbul) saat kabul edilir."""
    utc_value = (utc_value or "").strip()
    if utc_value:
        try:
            dt = datetime.fromisoformat(utc_value.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, dt_timezone.utc)
            return dt
        except ValueError:
            pass
    try:
        dt = datetime.strptime((local_value or "").strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    return timezone.make_aware(dt, timezone.get_current_timezone())


class QuestionForm(forms.Form):
    title = forms.CharField(
        label="Başlık", max_length=200,
        error_messages={"required": "Başlık zorunludur.", "max_length": "Başlık en fazla 200 karakter olabilir."},
    )
    description = forms.CharField(
        label="Kısa açıklama (opsiyonel)", max_length=500, required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"max_length": "Açıklama en fazla 500 karakter olabilir."},
    )
    resolution_criteria = forms.CharField(
        label="Sonuç hangi ölçüte göre belirlenecek?", max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Örn: Maç sonu resmi skor, 90 dakika + uzatmalar."}),
        error_messages={
            "required": "Sonucun nasıl belirleneceğini yazmalısın.",
            "max_length": "Ölçüt en fazla 500 karakter olabilir.",
        },
    )
    category = forms.ChoiceField(
        label="Kategori", choices=Category.choices,
        error_messages={"required": "Kategori seçmelisin.", "invalid_choice": "Geçerli bir kategori seç."},
    )
    closes_at = forms.CharField(label="Tahminlerin kapanacağı tarih ve saat", error_messages={"required": "Kapanış zamanı zorunludur."})
    closes_at_utc = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, lock_core=False, **kwargs):
        """lock_core=True: ilk tahminden sonra başlık/ölçüt/seçenek/kapanış değiştirilemez."""
        super().__init__(*args, **kwargs)
        self.lock_core = lock_core
        for i in range(1, MAX_CHOICES + 1):
            self.fields[f"choice_{i}"] = forms.CharField(
                label=f"Seçenek {i}", max_length=100, required=False,
                error_messages={"max_length": "Seçenek en fazla 100 karakter olabilir."},
            )
        if lock_core:
            for name in ["title", "resolution_criteria", "closes_at", "closes_at_utc",
                         *(f"choice_{i}" for i in range(1, MAX_CHOICES + 1))]:
                self.fields[name].required = False
                if name != "closes_at_utc":
                    self.fields[name].widget.attrs["readonly"] = True

    @property
    def choice_fields(self):
        return [self[f"choice_{i}"] for i in range(1, MAX_CHOICES + 1)]

    def clean(self):
        cleaned = super().clean()
        if self.lock_core:  # kilitli alanlar gönderilse bile dikkate alınmaz
            return cleaned

        closes_at = parse_closing(cleaned.get("closes_at"), cleaned.get("closes_at_utc"))
        if "closes_at" not in self.errors:
            if closes_at is None:
                self.add_error("closes_at", "Geçerli bir tarih ve saat gir.")
            elif closes_at <= timezone.now() + timedelta(seconds=MIN_LEAD):
                self.add_error("closes_at", "Kapanış zamanı gelecekte olmalı.")
            else:
                cleaned["closes_at"] = closes_at

        choices, seen = [], set()
        for i in range(1, MAX_CHOICES + 1):
            name = f"choice_{i}"
            text = (cleaned.get(name) or "").strip()
            if not text:
                continue
            if text.casefold() in seen:
                self.add_error(name, "Bu seçenek zaten eklenmiş.")
                continue
            seen.add(text.casefold())
            choices.append(text)
        if len(choices) < MIN_CHOICES and not any(self.errors.get(f"choice_{i}") for i in range(1, MAX_CHOICES + 1)):
            self.add_error("choice_1", f"En az {MIN_CHOICES} seçenek girmelisin.")
        cleaned["choices"] = choices
        return cleaned


class ResolveForm(forms.Form):
    choice = forms.CharField(error_messages={"required": "Doğru seçeneği seçmelisin."})
    note = forms.CharField(
        label="Kısa açıklama", min_length=5, max_length=500, widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={
            "required": "Sonuç için kısa bir açıklama yazmalısın.",
            "min_length": "Açıklama en az 5 karakter olmalı.",
            "max_length": "Açıklama en fazla 500 karakter olabilir.",
        },
    )
    source_url = forms.URLField(
        label="Kaynak bağlantısı (opsiyonel)", required=False, max_length=300,
        error_messages={"invalid": "Geçerli bir bağlantı gir (https://… ile başlamalı)."},
    )


class CancelForm(forms.Form):
    reason = forms.CharField(
        label="İptal gerekçesi", min_length=10, max_length=500, widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={
            "required": "İptal için bir gerekçe yazmalısın.",
            "min_length": "Gerekçe en az 10 karakter olmalı.",
            "max_length": "Gerekçe en fazla 500 karakter olabilir.",
        },
    )
