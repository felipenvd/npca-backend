import pytest
from django.db import IntegrityError, transaction

from apps.labcompap.models import LabEquipment


@pytest.mark.django_db
def test_equipment_inventory_code_is_unique() -> None:
    LabEquipment.objects.create(
        inventory_code="ABC-1",
        name_pt_br="Computador",
        name_en="Computer",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        LabEquipment.objects.create(
            inventory_code="ABC-1",
            name_pt_br="Outro computador",
            name_en="Another computer",
        )


@pytest.mark.django_db
def test_equipment_uses_display_order() -> None:
    second = LabEquipment.objects.create(
        inventory_code="ABC-2",
        name_pt_br="Segundo",
        name_en="Second",
        display_order=2,
    )
    first = LabEquipment.objects.create(
        inventory_code="ABC-1",
        name_pt_br="Primeiro",
        name_en="First",
        display_order=1,
    )

    assert list(LabEquipment.objects.all()) == [first, second]
