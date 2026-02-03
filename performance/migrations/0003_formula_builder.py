from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("performance", "0002_initial"),
        ("schemas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="performanceindicator",
            name="frequency",
            field=models.CharField(
                choices=[
                    ("DAILY", "Diario"),
                    ("WEEKLY", "Semanal"),
                    ("MONTHLY", "Mensual"),
                    ("YEARLY", "Anual"),
                ],
                default="MONTHLY",
                help_text="Frecuencia por defecto para evaluar esta fórmula.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="performanceindicator",
            name="expression",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Expresión (tokens) configurada desde el constructor visual.",
            ),
        ),
        migrations.AddField(
            model_name="performanceindicator",
            name="expression_text",
            field=models.TextField(
                blank=True,
                help_text="Expresión legible para el usuario (generada desde el builder).",
            ),
        ),
        migrations.CreateModel(
            name="PerformanceIndicatorInput",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "token",
                    models.SlugField(
                        help_text="Identificador usado dentro de la fórmula (ej: v1, var_kcl).",
                        max_length=40,
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=255)),
                (
                    "aggregation",
                    models.CharField(
                        choices=[
                            ("SUM", "Suma"),
                            ("AVG", "Promedio"),
                            ("MAX", "Máximo"),
                            ("MIN", "Mínimo"),
                            ("LAST", "Último (por periodo)"),
                            ("NONE", "Sin agregación"),
                        ],
                        default="SUM",
                        max_length=10,
                    ),
                ),
                (
                    "transform",
                    models.CharField(
                        choices=[
                            ("NONE", "Ninguna"),
                            ("MULTIPLY", "Multiplicar por factor"),
                            ("ADD", "Sumar factor"),
                        ],
                        default="NONE",
                        max_length=10,
                    ),
                ),
                ("transform_value", models.FloatField(blank=True, null=True)),
                (
                    "offset_periods",
                    models.IntegerField(
                        default=0,
                        help_text="Desfase de periodos según la frecuencia seleccionada (p. ej. 1 = periodo anterior).",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "column",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="performance_inputs",
                        to="schemas.columndef",
                    ),
                ),
                (
                    "indicator",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="inputs",
                        to="performance.performanceindicator",
                    ),
                ),
            ],
            options={
                "ordering": ["indicator__plant__code", "indicator__key", "token"],
                "unique_together": {("indicator", "token")},
            },
        ),
    ]
