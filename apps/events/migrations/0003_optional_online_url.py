from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0002_add_completed_schedule_status"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="event",
            name="published_online_event_has_url",
        ),
    ]
