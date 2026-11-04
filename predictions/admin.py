"""Moderasyon paneli: sorular, seçenekler ve tahminler yalnızca GÖRÜNTÜLENEBİLİR; yalnızca soru SİLİNEBİLİR.

Düzenleme bilerek kapalıdır: sonuç, puan ve kilitli alanlar yalnızca servis katmanından (services.py) değişir ve
veritabanı tetikleyicileri de buna dayanır. Uygunsuz bir soru silinirse tahminleri de gider (silme onay sayfası
etkilenen kayıtları listeler); hesap silme ise `PROTECT` yüzünden engellenir, bunun yerine hesabı pasifleştir.
"""
from django.contrib import admin

from .models import Choice, Prediction, Question


class ReadOnlyMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ChoiceInline(ReadOnlyMixin, admin.TabularInline):
    model = Choice
    extra = 0
    can_delete = False
    fields = ("position", "text")


class PredictionInline(ReadOnlyMixin, admin.TabularInline):
    """Tahminler yalnızca bu soru sayfasında görünür; tek tek silinemez (dağılım ve puanlar bozulmasın).
    Prediction modeli bilerek ayrıca kayıt edilmedi: kayıtlı olsaydı Django, soruyu silmek için tahmin silme izni isterdi."""
    model = Prediction
    extra = 0
    can_delete = False
    fields = ("user", "choice", "is_correct", "points_awarded", "updated_at")
    readonly_fields = fields


@admin.register(Question)
class QuestionAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("title", "created_by", "category", "status", "closes_at", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "created_by__username")
    date_hierarchy = "created_at"
    inlines = [ChoiceInline, PredictionInline]

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser
