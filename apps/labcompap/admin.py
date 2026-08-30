from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import LabEquipment, LabGalleryImage


class OrderedContentAdmin(ModelAdmin):
    list_editable = ("display_order",)


@admin.register(LabEquipment)
class LabEquipmentAdmin(OrderedContentAdmin):
    list_display = ("inventory_code", "name_pt_br", "brand", "model_name", "display_order")
    search_fields = ("inventory_code", "name_pt_br", "name_en", "brand", "model_name")


@admin.register(LabGalleryImage)
class LabGalleryImageAdmin(OrderedContentAdmin):
    list_display = ("thumbnail", "caption_pt_br", "credit", "display_order")
    search_fields = ("caption_pt_br", "caption_en", "alt_text_pt_br", "alt_text_en")
    readonly_fields = ("preview",)

    @admin.display(description="Imagem")
    def thumbnail(self, obj: LabGalleryImage) -> str:
        return format_html(
            '<img src="{}" alt="" style="height: 44px; width: 72px; object-fit: cover;">',
            obj.image.url,
        )

    @admin.display(description="Prévia")
    def preview(self, obj: LabGalleryImage) -> str:
        return format_html(
            '<img src="{}" alt="" '
            'style="max-height: 260px; max-width: 520px; object-fit: contain;">',
            obj.image.url,
        )
