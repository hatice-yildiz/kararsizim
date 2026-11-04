from django.contrib import admin

from .models import Option, Poll


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "created_by", "created_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("question", "created_by__username")
    inlines = [OptionInline]
