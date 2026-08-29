from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline

from .forms import (
    ResearcherForm,
    ResearcherTranslationForm,
    ResearcherTranslationInlineFormSet,
)
from .models import Researcher, ResearcherTranslation


class ResearcherTranslationInline(StackedInline):
    model = ResearcherTranslation
    form = ResearcherTranslationForm
    formset = ResearcherTranslationInlineFormSet
    extra = 2
    max_num = 2
    can_delete = False
    classes = ("collapse",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "language",
                    "slug",
                    "role",
                    "research_area",
                    "biography_html",
                    "photo_alt_text",
                    "seo_title",
                    "seo_description",
                ),
                "description": (
                    "Os campos marcados com * são obrigatórios para ativar, "
                    "mas podem ficar vazios enquanto o pesquisador estiver inativo."
                ),
            },
        ),
    )


@admin.register(Researcher)
class ResearcherAdmin(ModelAdmin):
    form = ResearcherForm
    inlines = (ResearcherTranslationInline,)
    list_display = ("full_name", "is_active", "display_order", "updated_at")
    list_editable = ("display_order",)
    list_filter = ("is_active", "updated_at")
    search_fields = (
        "full_name",
        "public_email",
        "translations__role",
        "translations__research_area",
    )
    ordering = ("display_order", "full_name", "pk")
    readonly_fields = (
        "photo_preview",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    fields = (
        "full_name",
        "is_active",
        "display_order",
        "photo",
        "photo_preview",
        "public_email",
        "lattes_url",
        "orcid_url",
        "linkedin_url",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    warn_unsaved_form = True

    @admin.display(description="Prévia da foto")
    def photo_preview(self, obj: Researcher) -> str:
        if not obj.photo:
            return "Sem foto"
        return format_html(
            '<img src="{}" alt="" style="height: 180px; width: 180px; '
            'border-radius: 9999px; object-fit: cover;">',
            obj.photo.url,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations")

    def save_model(self, request, obj: Researcher, form, change: bool) -> None:
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
