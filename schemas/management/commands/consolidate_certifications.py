from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from schemas.models import DatasetType
from schemas.services import (
    backfill_all_certifications,
    backfill_certification_schema,
    consolidate_all_certifications,
)


class Command(BaseCommand):
    help = "Consolida esquemas de certificacion para el mes previo o en modo backfill historico."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reference-date",
            dest="reference_date",
            help="Fecha de referencia en formato YYYY-MM-DD (opcional).",
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            help="Ejecuta consolidacion historica mensual para todos los meses disponibles.",
        )
        parser.add_argument(
            "--schema-id",
            dest="schema_id",
            type=int,
            help="ID de esquema de certificacion especifico para backfill.",
        )
        parser.add_argument(
            "--from-date",
            dest="from_date",
            help="Fecha inicial (YYYY-MM-DD) para limitar el backfill.",
        )
        parser.add_argument(
            "--to-date",
            dest="to_date",
            help="Fecha final (YYYY-MM-DD) para limitar el backfill.",
        )

    def _parse_date(self, value: str | None, arg_name: str):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(f"Formato invalido para {arg_name}. Use YYYY-MM-DD.") from exc

    def handle(self, *args, **options):
        reference_date = self._parse_date(options.get("reference_date"), "reference-date")
        from_date = self._parse_date(options.get("from_date"), "from-date")
        to_date = self._parse_date(options.get("to_date"), "to-date")
        backfill = bool(options.get("backfill"))
        schema_id = options.get("schema_id")

        if from_date and to_date and from_date > to_date:
            raise CommandError("from-date no puede ser mayor que to-date.")

        if backfill:
            if schema_id:
                try:
                    schema = DatasetType.objects.select_related("entity", "source_dataset").get(pk=schema_id)
                except DatasetType.DoesNotExist as exc:
                    raise CommandError("No existe el esquema indicado en --schema-id.") from exc
                if not schema.is_certification:
                    raise CommandError("El esquema indicado en --schema-id no es de certificacion.")

                instances = backfill_certification_schema(
                    schema,
                    from_date=from_date,
                    to_date=to_date,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Backfill completado para esquema {schema.id}: {len(instances)} instancia(s) mensual(es)."
                    )
                )
                return

            instances = backfill_all_certifications(from_date=from_date, to_date=to_date)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Backfill completado para todos los esquemas: {len(instances)} instancia(s) mensual(es)."
                )
            )
            return

        instances = consolidate_all_certifications(reference_date=reference_date)
        self.stdout.write(
            self.style.SUCCESS(f"Se consolidaron {len(instances)} esquema(s) de certificacion.")
        )
