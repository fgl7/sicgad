from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schemas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasettype",
            name="last_consolidated_period",
            field=models.DateField(
                blank=True,
                help_text="Último periodo (último día del mes) consolidado automáticamente para certificación.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="datasettype",
            name="source_dataset",
            field=models.ForeignKey(
                blank=True,
                help_text="Dataset base diario utilizado para consolidaciones de certificación.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="derived_certifications",
                to="schemas.datasettype",
            ),
        ),
    ]

