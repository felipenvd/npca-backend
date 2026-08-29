from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from .forms import (
    ProjectForm,
    ProjectTeamMemberForm,
    ProjectTeamMemberInlineFormSet,
    ProjectTranslationForm,
    ProjectTranslationInlineFormSet,
)
from .models import Project, ProjectTeamMember, ProjectTranslation


class ProjectTranslationInline(StackedInline):
    model = ProjectTranslation
    form = ProjectTranslationForm
    formset = ProjectTranslationInlineFormSet
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
                    "slug",
                    "summary",
                    "body_html",
                    "seo_title",
                    "seo_description",
                ),
                "description": (
                    "Os campos marcados com * são obrigatórios para publicar, "
                    "mas podem ficar vazios enquanto o projeto for um rascunho."
                ),
            },
        ),
    )


class ProjectTeamMemberInline(TabularInline):
    model = ProjectTeamMember
    form = ProjectTeamMemberForm
    formset = ProjectTeamMemberInlineFormSet
    autocomplete_fields = ("researcher",)
    extra = 1
    verbose_name = "integrante da equipe"
    verbose_name_plural = "equipe"


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    form = ProjectForm
    inlines = (ProjectTranslationInline, ProjectTeamMemberInline)
    autocomplete_fields = ("coordinator",)
    list_display = (
        "title_pt_br",
        "status",
        "situation",
        "coordinator",
        "is_featured",
        "display_order",
        "updated_at",
    )
    list_editable = ("is_featured", "display_order")
    list_filter = ("status", "situation", "is_featured", "updated_at")
    search_fields = (
        "translations__title",
        "translations__summary",
        "coordinator__full_name",
        "team__full_name",
        "funding",
        "partners",
    )
    ordering = ("display_order", "pk")
    readonly_fields = (
        "cover_preview",
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
                "fields": (
                    "status",
                    "situation",
                    "coordinator",
                    ("start_date", "end_date"),
                    "is_featured",
                    "display_order",
                ),
                "description": (
                    "Coordenador e data de início são obrigatórios para publicar. "
                    "Projetos concluídos também exigem data de término."
                ),
            },
        ),
        (
            "Apresentação",
            {"fields": ("cover", "cover_preview", "cover_credit")},
        ),
        (
            "Apoio e links",
            {
                "fields": (
                    "funding",
                    "partners",
                    "website_url",
                    "repository_url",
                )
            },
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
    def title_pt_br(self, obj: Project) -> str:
        translation = next(
            (item for item in obj.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Projeto #{obj.pk}"

    @admin.display(description="Prévia da capa")
    def cover_preview(self, obj: Project) -> str:
        if not obj.cover:
            return "Sem imagem"
        return format_html(
            '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: cover;">',
            obj.cover.url,
        )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("coordinator")
            .prefetch_related("translations")
        )

    def save_model(self, request, obj: Project, form, change: bool) -> None:
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
