import json
from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.projects.api import serialize_person
from apps.publications.api import serialize_author
from apps.publications.models import PublicationAuthor
from apps.researchers.forms import ResearcherForm
from apps.researchers.models import Researcher
from apps.researchers.photos import cropped_photo, validate_photo_crop
from apps.researchers.tests.test_admin import researcher_data
from apps.researchers.tests.test_api import create_active_researcher


def portrait():
    image = Image.new("RGB", (200, 400), "blue")
    image.paste("red", (0, 0, 200, 200))
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return SimpleUploadedFile("portrait.png", buffer.getvalue(), content_type="image/png")


@pytest.mark.parametrize(
    "crop",
    (
        [],
        "crop",
        {"x": -1},
        {"y": 101},
        {"zoom": 0.9},
        {"zoom": 3.1},
        {"x": True},
        {"x": "20"},
        {"x": float("nan")},
        {"zoom": float("inf")},
        {"unknown": 0},
    ),
)
def test_crop_rejects_invalid_coordinates(crop):
    with pytest.raises(ValidationError):
        validate_photo_crop(crop)


def test_crop_respects_position_and_zoom_without_modifying_original():
    upload = portrait()
    original = upload.read()
    crop = cropped_photo(upload, {"x": 50, "y": 0, "zoom": 2})

    with Image.open(crop) as image:
        assert image.format == "WEBP"
        assert image.size == (100, 100)
        red, green, blue = image.convert("RGB").getpixel((50, 50))
        assert red > 240 and green < 10 and blue < 10
    assert upload.read() == original


def test_crop_honors_exif_orientation():
    image = Image.new("RGB", (400, 200), "blue")
    image.paste("red", (0, 0, 200, 200))
    exif = Image.Exif()
    exif[274] = 6  # Rotate the landscape upload to an upright portrait.
    buffer = BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    upload = SimpleUploadedFile("portrait.jpg", buffer.getvalue(), content_type="image/jpeg")

    with Image.open(cropped_photo(upload, {"y": 0})) as result:
        red, _, blue = result.convert("RGB").getpixel((100, 100))
        assert red > 240 and blue < 10


def form_data(researcher, crop):
    return {
        "full_name": researcher.full_name,
        "academic_category": researcher.academic_category,
        "display_order": 0,
        "photo_crop": json.dumps(crop),
    }


@pytest.mark.django_db
def test_admin_saves_crop_and_every_public_avatar_uses_it(settings, tmp_path, client):
    settings.MEDIA_ROOT = tmp_path
    researcher = create_active_researcher(name="Ana Silva")
    form = ResearcherForm(
        data=form_data(researcher, {"x": 50, "y": 0, "zoom": 1}),
        files={"photo": portrait()},
        instance=researcher,
    )
    assert form.is_valid(), form.errors
    researcher = form.save()
    researcher.is_active = True
    researcher.save()
    researcher.refresh_from_db()

    assert researcher.photo.name.endswith(".png")
    assert researcher.photo_cropped.name.endswith(".webp")
    assert researcher.photo_crop == {"x": 50, "y": 0, "zoom": 1}
    with Image.open(researcher.photo.path) as original:
        assert original.size == (200, 400)
    with Image.open(researcher.photo_cropped.path) as cropped:
        assert cropped.size == (200, 200)
    url = researcher.photo_cropped.url
    for lang in ("pt-br", "en"):
        listing = client.get("/api/v1/researchers", {"lang": lang}).json()
        detail = client.get("/api/v1/researchers/ana-silva", {"lang": lang}).json()
        assert listing["items"][0]["photo"]["url"] == url
        assert detail["photo"]["url"] == url
        assert serialize_person(researcher, lang).photo.url == url
        assert serialize_author(PublicationAuthor(researcher=researcher), lang).photo.url == url

    unchanged = ResearcherForm(
        data=form_data(researcher, researcher.photo_crop), instance=researcher
    )
    assert unchanged.is_valid(), unchanged.errors
    assert unchanged.save().photo_cropped.url == url

    adjusted = ResearcherForm(data=form_data(researcher, {"y": 100}), instance=researcher)
    assert adjusted.is_valid(), adjusted.errors
    researcher = adjusted.save()
    assert researcher.photo_cropped.url != url
    with Image.open(researcher.photo_cropped.path) as image:
        assert image.convert("RGB").getpixel((100, 100))[2] > 240


@pytest.mark.django_db
def test_replacing_and_clearing_photo_reset_the_crop(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    researcher = create_active_researcher(name="Ana Silva")
    first = ResearcherForm(
        data=form_data(researcher, {"zoom": 2}), files={"photo": portrait()}, instance=researcher
    )
    assert first.is_valid(), first.errors
    first.save()
    original_crop = researcher.photo_cropped.name

    replacement = ResearcherForm(
        data={
            key: value for key, value in form_data(researcher, {}).items() if key != "photo_crop"
        },
        files={"photo": portrait()},
        instance=researcher,
    )
    assert replacement.is_valid(), replacement.errors
    replacement.save()
    assert researcher.photo_crop == {}
    assert researcher.photo_cropped.name != original_crop

    clear = ResearcherForm(
        data={**form_data(researcher, {}), "photo-clear": "on"}, instance=researcher
    )
    assert clear.is_valid(), clear.errors
    clear.save()
    researcher.refresh_from_db()
    assert not researcher.photo
    assert not researcher.photo_cropped
    assert researcher.photo_crop == {}
    assert researcher.display_photo is None


@pytest.mark.django_db
def test_form_rejects_invalid_crop_before_writing_files():
    form = ResearcherForm(
        data={
            "full_name": "Ana",
            "academic_category": "doctor",
            "display_order": 0,
            "photo_crop": "[1, 2]",
        }
    )
    assert not form.is_valid()
    assert "photo_crop" in form.errors


@pytest.mark.django_db
def test_admin_renders_editor_and_restores_saved_crop(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    researcher = create_active_researcher(name="Ana Silva", photo=portrait())
    researcher.photo_crop = {"x": 50, "y": 0, "zoom": 1.5}
    researcher.save()

    response = admin_client.get(
        reverse("admin:researchers_researcher_change", args=[researcher.pk])
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "researchers/admin/photo_crop.js" in html
    assert "researchers/admin/photo_crop.css" in html
    assert "Ajustar enquadramento" in html
    assert "data-photo-editor" in html
    assert f'data-initial-url="{researcher.photo.url}"' in html
    assert 'name="photo_crop"' in html
    assert "Prévia da foto" not in html


@pytest.mark.django_db
def test_admin_only_writes_crop_after_the_whole_profile_is_valid(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    data = researcher_data(active=True)
    data.update({"photo": portrait(), "photo_crop": '{"y": 0, "zoom": 1.5}'})
    invalid = admin_client.post(reverse("admin:researchers_researcher_add"), data)
    assert invalid.status_code == 200
    assert not list(tmp_path.rglob("*.webp"))

    data.update(
        {
            "photo": portrait(),
            "translations-1-research_area": "Artificial Intelligence",
            "translations-1-biography_html": "<p>Biography</p>",
        }
    )
    valid = admin_client.post(reverse("admin:researchers_researcher_add"), data)
    assert valid.status_code == 302
    researcher = Researcher.objects.get()
    assert researcher.photo_cropped
    assert researcher.photo_crop == {"y": 0, "zoom": 1.5}
