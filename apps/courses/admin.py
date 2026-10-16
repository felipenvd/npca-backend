from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin import BilingualContentAdmin, BilingualTranslationInline

from .forms import (
    CourseForm,
    CourseTranslationForm,
    CourseTranslationInlineFormSet,
)
from .models import Course, CourseTranslation


class CourseTranslationInline(BilingualTranslationInline):
    model = CourseTranslation
    form = CourseTranslationForm
    formset = CourseTranslationInlineFormSet
    fieldsets = (
        (
            None,
            {
                "fields": ("language", "title", "summary"),
                "description": (
                    "Título e resumo são obrigatórios nos dois idiomas para publicar, "
                    "mas podem ficar vazios enquanto o registro for um rascunho."
                ),
            },
        ),
    )


@admin.register(Course)
class CourseAdmin(BilingualContentAdmin):
    form = CourseForm
    inlines = (CourseTranslationInline,)
    list_display = (
        "title_pt_br",
        "status",
        "course_type",
        "is_featured",
        "display_order",
        "updated_at",
    )
    list_editable = ("is_featured", "display_order")
    list_filter = ("status", "course_type", "is_featured", "updated_at")
    search_fields = (
        "translations__title",
        "translations__summary",
        "external_url",
    )
    ordering = ("-is_featured", "display_order", "pk")
    readonly_fields = (
        "cover_preview",
        "external_link",
        "published_at",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    fieldsets = (
        (
            "Dados gerais",
            {
                "fields": (
                    "course_type",
                    "external_url",
                    "external_link",
                ),
                "description": (
                    "Tipo, URL HTTPS e traduções completas são obrigatórios para publicar. "
                    "O vídeo permanecerá hospedado no serviço externo."
                ),
            },
        ),
        (
            "Apresentação",
            {"fields": ("cover", "cover_preview", "cover_credit")},
        ),
        ("Opções avançadas", {"fields": ("is_featured", "display_order")}),
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
        ("Publicação", {"fields": ("status",)}),
    )
    warn_unsaved_form = True

    @admin.display(description="Título", ordering="translations__title")
    def title_pt_br(self, obj: Course) -> str:
        translation = next(
            (item for item in obj.translations.all() if item.language == "pt-br"),
            None,
        )
        title = translation.title if translation and translation.title else f"Curso #{obj.pk}"
        return format_html(
            '<span title="{}" style="display: block; max-width: 20rem; overflow: hidden; '
            'text-overflow: ellipsis; white-space: nowrap;">{}</span>',
            title,
            title,
        )

    @admin.display(description="Prévia da imagem")
    def cover_preview(self, obj: Course) -> str:
        if not obj.cover:
            return "Sem imagem"
        return format_html(
            '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: cover;">',
            obj.cover.url,
        )

    @admin.display(description="Link atual")
    def external_link(self, obj: Course) -> str:
        if not obj.external_url:
            return "Sem link"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Abrir conteúdo</a>',
            obj.external_url,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations")

    def save_model(self, request, obj: Course, form, change: bool) -> None:
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
