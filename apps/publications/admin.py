from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from .forms import (
    PublicationAuthorForm,
    PublicationAuthorInlineFormSet,
    PublicationForm,
    PublicationTranslationForm,
    PublicationTranslationInlineFormSet,
)
from .models import Publication, PublicationAuthor, PublicationTranslation


class PublicationTranslationInline(StackedInline):
    model = PublicationTranslation
    form = PublicationTranslationForm
    formset = PublicationTranslationInlineFormSet
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
                    "title",
                    "abstract",
                    "cover_alt_text",
                    "seo_title",
                    "seo_description",
                ),
                "description": (
                    "Título e resumo são obrigatórios nos dois idiomas para publicar, "
                    "mas podem ficar vazios enquanto o registro for um rascunho."
                ),
            },
        ),
    )


class PublicationAuthorInline(TabularInline):
    model = PublicationAuthor
    form = PublicationAuthorForm
    formset = PublicationAuthorInlineFormSet
    autocomplete_fields = ("researcher",)
    extra = 1
    verbose_name = "autor"
    verbose_name_plural = "autores"


@admin.register(Publication)
class PublicationAdmin(ModelAdmin):
    form = PublicationForm
    inlines = (PublicationTranslationInline, PublicationAuthorInline)
    autocomplete_fields = ("project",)
    list_display = (
        "title_pt_br",
        "status",
        "year",
        "venue",
        "project",
        "display_order",
        "updated_at",
    )
    list_editable = ("display_order",)
    list_filter = ("status", "year", "updated_at")
    search_fields = (
        "translations__title",
        "translations__abstract",
        "venue",
        "doi",
        "author_records__researcher__full_name",
        "author_records__external_name",
        "project__translations__title",
    )
    ordering = ("-year", "display_order", "pk")
    readonly_fields = (
        "cover_preview",
        "document_link",
        "published_at",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    fieldsets = (
        (
            None,
            {
                "fields": ("status", ("year", "display_order"), "venue", "project"),
                "description": (
                    "Ano, periódico ou evento, ao menos um autor e as traduções completas "
                    "são obrigatórios para publicar."
                ),
            },
        ),
        (
            "Apresentação",
            {"fields": ("cover", "cover_preview", "cover_credit")},
        ),
        (
            "Acesso à publicação",
            {"fields": ("doi", "external_url", "document", "document_link")},
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "published_at",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    warn_unsaved_form = True

    @admin.display(description="Título", ordering="translations__title")
    def title_pt_br(self, obj: Publication) -> str:
        translation = next(
            (item for item in obj.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Publicação #{obj.pk}"

    @admin.display(description="Prévia da imagem")
    def cover_preview(self, obj: Publication) -> str:
        if not obj.cover:
            return "Sem imagem"
        return format_html(
            '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: cover;">',
            obj.cover.url,
        )

    @admin.display(description="Arquivo atual")
    def document_link(self, obj: Publication) -> str:
        if not obj.document:
            return "Sem arquivo"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Abrir PDF</a>',
            obj.document.url,
        )

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("project").prefetch_related("translations")
        )

    def save_model(self, request, obj: Publication, form, change: bool) -> None:
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
