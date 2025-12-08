from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountprofile",
            name="last_seen_validation_status",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha/hora en la que el usuario vio por ultima vez el estado de sus cargas.",
                null=True,
            ),
        ),
    ]

