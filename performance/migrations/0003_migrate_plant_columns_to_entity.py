from django.db import migrations


def _table_columns(connection, table_name):
    with connection.cursor() as cursor:
        return {col.name for col in connection.introspection.get_table_description(cursor, table_name)}


def _build_entity_map(connection):
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        if "plants_plant" not in tables or "structure_entity" not in tables:
            return {}
        cursor.execute("SELECT id, code FROM plants_plant")
        plant_rows = cursor.fetchall()
        cursor.execute("SELECT id, code FROM structure_entity")
        entity_rows = cursor.fetchall()

    entity_by_code = {code: entity_id for entity_id, code in entity_rows if code}
    mapping = {}
    for plant_id, code in plant_rows:
        if code and code in entity_by_code:
            mapping[plant_id] = entity_by_code[code]
    return mapping


def migrate_columns(apps, schema_editor):
    connection = schema_editor.connection
    tables = set(connection.introspection.table_names())

    targets = [
        "performance_performancevariable",
        "performance_performanceindicator",
        "performance_performanceindicatorresult",
    ]

    with connection.cursor() as cursor:
        for table in targets:
            if table not in tables:
                continue
            cols = _table_columns(connection, table)
            if "plant_id" in cols and "entity_id" not in cols:
                cursor.execute(f'ALTER TABLE "{table}" RENAME COLUMN "plant_id" TO "entity_id"')

    mapping = _build_entity_map(connection)
    if not mapping:
        return

    with connection.cursor() as cursor:
        for table in targets:
            if table not in tables:
                continue
            cols = _table_columns(connection, table)
            if "entity_id" not in cols:
                continue
            for old_id, new_id in mapping.items():
                if old_id == new_id:
                    continue
                cursor.execute(
                    f'UPDATE "{table}" SET "entity_id" = %s WHERE "entity_id" = %s',
                    [new_id, old_id],
                )


class Migration(migrations.Migration):
    dependencies = [
        ("performance", "0002_alter_performanceindicator_expression_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_columns, migrations.RunPython.noop),
    ]
