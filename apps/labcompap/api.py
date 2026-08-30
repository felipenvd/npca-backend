from ninja import Router

from .models import LabEquipment, LabGalleryImage
from .schemas import LabCompApResponse, LabEquipmentItem, LabImage, Language

router = Router(tags=["labcompap"])


@router.get("", response=LabCompApResponse, summary="Obtém o acervo do LabCompAp")
def get_labcompap(request, lang: Language) -> LabCompApResponse:
    is_pt_br = lang == "pt-br"

    return LabCompApResponse(
        equipment=[
            LabEquipmentItem(
                inventory_code=item.inventory_code,
                name=item.name_pt_br if is_pt_br else item.name_en,
                brand=item.brand or None,
                model=item.model_name or None,
            )
            for item in LabEquipment.objects.all()
        ],
        gallery=[
            LabImage(
                url=item.image.url,
                alt=item.alt_text_pt_br if is_pt_br else item.alt_text_en,
                caption=(item.caption_pt_br if is_pt_br else item.caption_en) or None,
                credit=item.credit or None,
            )
            for item in LabGalleryImage.objects.all()
        ],
    )
