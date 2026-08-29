from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline

from .forms import NewsTranslationForm, NewsTranslationInlineFormSet
from .models import News, NewsTranslation


class NewsTranslationInline(StackedInline):
    model = NewsTranslation
    form = NewsTranslationForm
    formset = NewsTranslationInlineFormSet
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
                    "cover_alt_text",
                    "seo_title",
                    "seo_description",
                ),
                "description": (
                    "Os campos marcados com * são obrigatórios para publicar, "
                    "mas podem ficar vazios enquanto a notícia for um rascunho."
                ),
            },
        ),
    )


@admin.register(News)
class NewsAdmin(ModelAdmin):
    inlines = (NewsTranslationInline,)
    list_display = ("title_pt_br", "status", "published_at", "updated_at")
    list_filter = ("status", "published_at", "updated_at")
    search_fields = ("translations__title", "translations__summary")
    ordering = ("-published_at", "-pk")
    readonly_fields = (
        "cover_preview",
        "published_at",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    fields = (
        "status",
        "cover",
        "cover_preview",
        "cover_credit",
        "published_at",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    warn_unsaved_form = True

    @admin.display(description="Título", ordering="translations__title")
    def title_pt_br(self, obj: News) -> str:
        translation = next(
            (item for item in obj.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Notícia #{obj.pk}"

    @admin.display(description="Prévia da capa")
    def cover_preview(self, obj: News) -> str:
        if not obj.cover:
            return "Sem imagem"
        return format_html(
            '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: cover;">',
            obj.cover.url,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations")

    def save_model(self, request, obj: News, form, change: bool) -> None:
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
