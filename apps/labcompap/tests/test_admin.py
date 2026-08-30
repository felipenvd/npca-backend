import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_admin_exposes_only_equipment_and_gallery(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    equipment = client.get(reverse("admin:labcompap_labequipment_changelist"))
    gallery = client.get(reverse("admin:labcompap_labgalleryimage_changelist"))
    index = client.get(reverse("admin:index")).content.decode()

    assert equipment.status_code == 200
    assert gallery.status_code == 200
    assert "Página do LabCompAp" not in index
    assert "Equipamentos" in index
    assert "Galeria" in index
