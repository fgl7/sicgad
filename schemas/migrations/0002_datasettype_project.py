from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0004_project_workflow_fields"),
        ("schemas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasettype",
            name="project",
            field=models.ForeignKey(
                blank=True,
                help_text="Proyecto operativo al que pertenece este esquema cuando nace desde el modulo projects.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="datasets",
                to="projects.project",
            ),
        ),
    ]
