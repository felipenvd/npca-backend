from pathlib import PurePath
from uuid import uuid4

from django.db import models

from .validators import validate_labcompap_image


def labcompap_image_upload_to(instance, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"labcompap/gallery/{uuid4().hex}{extension}"


class OrderedLabContent(models.Model):
    display_order = models.PositiveIntegerField("ordem de exibição", default=0)

    class Meta:
        abstract = True
        ordering = ("display_order", "pk")


class LabEquipment(OrderedLabContent):
    inventory_code = models.CharField("código", max_length=60, unique=True)
    name_pt_br = models.CharField("nome (PT-BR)", max_length=200)
    name_en = models.CharField("nome (EN)", max_length=200)
    brand = models.CharField("marca", max_length=120, blank=True)
    model_name = models.CharField("modelo", max_length=180, blank=True)

    class Meta(OrderedLabContent.Meta):
        verbose_name = "equipamento"
        verbose_name_plural = "equipamentos"

    def __str__(self) -> str:
        return f"{self.inventory_code} — {self.name_pt_br}"


class LabGalleryImage(OrderedLabContent):
    image = models.ImageField(
        "imagem",
        upload_to=labcompap_image_upload_to,
        validators=[validate_labcompap_image],
    )
    credit = models.CharField("crédito", max_length=200, blank=True)
    alt_text_pt_br = models.CharField("texto alternativo (PT-BR)", max_length=250, blank=True)
    alt_text_en = models.CharField("texto alternativo (EN)", max_length=250, blank=True)
    caption_pt_br = models.CharField("legenda (PT-BR)", max_length=250, blank=True)
    caption_en = models.CharField("legenda (EN)", max_length=250, blank=True)

    class Meta(OrderedLabContent.Meta):
        verbose_name = "imagem da galeria"
        verbose_name_plural = "galeria"

    def __str__(self) -> str:
        return self.caption_pt_br or f"Imagem {self.display_order + 1}"
