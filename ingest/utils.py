from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Tuple

from io import TextIOWrapper
import csv

import openpyxl

from .models import DatasetInstance, PublishedDataPoint
from schemas.models import ColumnDef


@dataclass
class ParsedRow:
  row_index: int
  values: List[str]


def _read_instance_file(instance: DatasetInstance) -> Tuple[List[str], List[ParsedRow]]:
    """
    Lee el archivo bruto de una instancia y devuelve encabezado y filas.
    No aplica ningún tipo de validación de negocio; solo lectura.
    """

    header: List[str] = []
    rows: List[ParsedRow] = []

    if not instance.raw_file:
        return header, rows

    file_field = instance.raw_file
    name = file_field.name or ""
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""

    if ext in ("xlsx", "xlsm", "xltx", "xltm"):
        with file_field.open("rb") as fh:
            wb = openpyxl.load_workbook(fh, read_only=True, data_only=True)
            ws = wb.active
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                values = ["" if v is None else str(v) for v in row]
                if i == 0:
                    header = values
                else:
                    rows.append(ParsedRow(row_index=i, values=values))
    else:
        with file_field.open("rb") as fh:
            wrapper = TextIOWrapper(fh, encoding="utf-8", errors="ignore")
            reader = csv.reader(wrapper)
            for i, row in enumerate(reader):
                values = row
                if i == 0:
                    header = values
                else:
                    rows.append(ParsedRow(row_index=i, values=values))

    return header, rows


def _parse_value(raw: str, column: ColumnDef):
    if raw is None:
        return None, None, None, None

    raw = str(raw).strip()
    if raw == "":
        return None, None, None, None

    dt = column.data_type

    if dt in ("INTEGER", "FLOAT"):
        try:
            return float(raw), None, None, None
        except ValueError:
            return None, raw, None, None

    if dt == "DATE":
        if isinstance(raw, (date, datetime)):
            return None, None, raw.date() if isinstance(raw, datetime) else raw, None
        try:
            parsed = date.fromisoformat(raw)
            return None, None, parsed, None
        except Exception:
            return None, raw, None, None

    if dt == "BOOLEAN":
        lowered = raw.lower()
        if lowered in ("1", "true", "t", "yes", "y", "si", "sí"):
            return None, None, None, True
        if lowered in ("0", "false", "f", "no", "n"):
            return None, None, None, False
        return None, raw, None, None

    # STRING / CHOICE / otros
    return None, raw, None, None


def materialize_instance(instance: DatasetInstance) -> int:
    """
    Convierte el archivo bruto de una instancia publicada en filas de PublishedDataPoint.
    Si ya existían puntos para la instancia, se eliminan primero.
    Devuelve la cantidad de puntos creados.
    """

    # Limpieza previa
    PublishedDataPoint.objects.filter(instance=instance).delete()

    header, rows = _read_instance_file(instance)
    if not header or not rows:
        return 0

    # Mapeo encabezado -> ColumnDef
    dataset = instance.dataset_type
    columns = list(dataset.columns.all())

    header_map = {}
    for col in columns:
        expected = (col.label or col.name or "").strip()
        if not expected:
            continue
        header_map[expected.lower()] = col

    index_to_column: List[ColumnDef | None] = []
    for name in header:
        col = header_map.get((name or "").strip().lower())
        index_to_column.append(col)

    points: list[PublishedDataPoint] = []
    for row in rows:
        for idx, raw in enumerate(row.values):
            column = index_to_column[idx] if idx < len(index_to_column) else None
            if not column:
                continue

            numeric_value, text_value, date_value, bool_value = _parse_value(raw, column)
            if (
                numeric_value is None
                and text_value in (None, "")
                and date_value is None
                and bool_value is None
            ):
                continue

            points.append(
                PublishedDataPoint(
                    instance=instance,
                    column=column,
                    row_index=row.row_index,
                    numeric_value=numeric_value,
                    text_value=text_value or "",
                    date_value=date_value,
                    bool_value=bool_value,
                )
            )

    if points:
        PublishedDataPoint.objects.bulk_create(points, batch_size=1000)

    return len(points)

