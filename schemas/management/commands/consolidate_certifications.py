from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from schemas.services import consolidate_all_certifications


class Command(BaseCommand):
    help = "Consolida automáticamente los esquemas de certificación usando los datos del mes anterior."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reference-date",
            dest="reference_date",
            help="Fecha de referencia en formato YYYY-MM-DD (opcional).",
        )

    def handle(self, *args, **options):
        reference = options.get("reference_date")
        reference_date = None
        if reference:
            try:
                reference_date = datetime.strptime(reference, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("Formato inválido para reference-date. Use YYYY-MM-DD.") from exc

        instances = consolidate_all_certifications(reference_date=reference_date)
        self.stdout.write(
            self.style.SUCCESS(f"Se consolidaron {len(instances)} esquema(s) de certificación.")
        )

