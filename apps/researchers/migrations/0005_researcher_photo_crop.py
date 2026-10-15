import apps.researchers.photos
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("researchers", "0004_remove_translation_role_and_photo_alt_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="researcher",
            name="photo_crop",
            field=models.JSONField(
                blank=True, default=dict,
                validators=[apps.researchers.photos.validate_photo_crop],
                verbose_name="enquadramento da foto",
            ),
        ),
        migrations.AddField(
            model_name="researcher",
            name="photo_cropped",
            field=models.ImageField(
                blank=True, editable=False, upload_to="researchers/cropped/",
                verbose_name="foto enquadrada",
            ),
        ),
    ]
