from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline

from .forms import EventForm, EventTranslationForm, EventTranslationInlineFormSet
from .models import Event, EventTranslation


class EventTranslationInline(StackedInline):
    model = EventTranslation
    form = EventTranslationForm
    formset = EventTranslationInlineFormSet
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
                    "location_name",
                    "location_address",
                    "cover_alt_text",
                    "seo_title",
                    "seo_description",
                ),
                "description": (
                    "Título, slug, resumo e descrição são obrigatórios nos dois idiomas "
                    "para publicar. Eventos presenciais e híbridos também exigem o local."
                ),
            },
        ),
    )


@admin.register(Event)
class EventAdmin(ModelAdmin):
    form = EventForm
    inlines = (EventTranslationInline,)
    list_display = (
        "title_pt_br",
        "status",
        "schedule_status",
        "event_type",
        "start_date",
        "start_time",
        "modality",
        "display_order",
    )
    list_editable = ("display_order",)
    list_filter = (
        "status",
        "schedule_status",
        "event_type",
        "modality",
        "is_all_day",
        "start_date",
    )
    search_fields = (
        "translations__title",
        "translations__summary",
        "translations__location_name",
        "translations__location_address",
    )
    ordering = ("start_date", "start_time", "display_order", "pk")
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
                    "schedule_status",
                    ("event_type", "modality"),
                    ("start_date", "end_date"),
                    "is_all_day",
                    ("start_time", "end_time"),
                    "display_order",
                ),
                "description": (
                    "Tipo, modalidade e agenda completa são obrigatórios para publicar. "
                    "Eventos de dia inteiro não usam horários."
                ),
            },
        ),
        (
            "Apresentação",
            {"fields": ("cover", "cover_preview", "cover_credit")},
        ),
        (
            "Acesso e inscrição",
            {"fields": ("online_url", "registration_url")},
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
    def title_pt_br(self, obj: Event) -> str:
        translation = next(
            (item for item in obj.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Evento #{obj.pk}"

    @admin.display(description="Prévia da imagem")
    def cover_preview(self, obj: Event) -> str:
        if not obj.cover:
            return "Sem imagem"
        return format_html(
            '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: cover;">',
            obj.cover.url,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations")

    def save_model(self, request, obj: Event, form, change: bool) -> None:
        if obj.created_by_id is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
