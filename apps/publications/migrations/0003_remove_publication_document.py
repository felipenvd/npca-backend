from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("publications", "0002_publication_cover_publication_cover_credit_and_more"),
    ]

    operations = [
        migrations.RemoveField(model_name="publication", name="document"),
    ]
