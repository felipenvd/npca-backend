from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]


class LabImage(Schema):
    url: str
    alt: str
    caption: str | None = None
    credit: str | None = None


class LabEquipmentItem(Schema):
    inventory_code: str
    name: str
    brand: str | None
    model: str | None


class LabCompApResponse(Schema):
    equipment: list[LabEquipmentItem]
    gallery: list[LabImage]
