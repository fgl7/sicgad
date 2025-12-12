from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_accountprofile_last_seen_validation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountprofile",
            name="last_seen_certification_alert",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha/hora en la que el usuario revisó las alertas de certificación mensual.",
                null=True,
            ),
        ),
    ]

