from django.contrib import admin

from apps.core.admin import BilingualContentAdmin, BilingualTranslationInline

from .forms import (
    ResearcherForm,
    ResearcherTranslationForm,
    ResearcherTranslationInlineFormSet,
)
from .models import Researcher, ResearcherTranslation


class ResearcherTranslationInline(BilingualTranslationInline):
    model = ResearcherTranslation
    form = ResearcherTranslationForm
    formset = ResearcherTranslationInlineFormSet
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "language",
                    "slug",
                    "research_area",
                    "biography_html",
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
class ResearcherAdmin(BilingualContentAdmin):
    form = ResearcherForm
    inlines = (ResearcherTranslationInline,)
    list_display = (
        "full_name",
        "academic_category",
        "is_active",
        "display_order",
        "updated_at",
    )
    list_editable = ("display_order",)
    list_filter = ("academic_category", "is_active", "updated_at")
    search_fields = (
        "full_name",
        "public_email",
        "translations__research_area",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    fieldsets = (
        ("Dados gerais", {"fields": ("full_name", "academic_category", "photo", "photo_crop")}),
        (
            "Contatos e currículo",
            {"fields": ("public_email", "lattes_url", "orcid_url", "linkedin_url")},
        ),
        ("Opções avançadas", {"fields": ("display_order",)}),
        (
            "Auditoria",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
        ("Publicação", {"fields": ("is_active",)}),
    )
    warn_unsaved_form = True

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations")

    def save_model(self, request, obj: Researcher, form, change: bool) -> None:
        if isinstance(form, ResearcherForm):
            form.prepare_photo_crop()
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
