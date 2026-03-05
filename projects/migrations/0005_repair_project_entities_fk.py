from django.db import migrations


def _fk_target_for_column(connection, table_name, column_name):
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
        for row in cursor.fetchall():
            # (id, seq, table, from, to, on_update, on_delete, match)
            if len(row) >= 4 and row[3] == column_name:
                return row[2]
    return None


def _build_plant_to_entity_map(connection, entity_by_id, entity_by_code):
    tables = set(connection.introspection.table_names())
    if "plants_plant" not in tables:
        return {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, code FROM plants_plant")
        plant_rows = cursor.fetchall()
    mapping = {}
    for plant_id, code in plant_rows:
        if plant_id in entity_by_id:
            mapping[plant_id] = plant_id
            continue
        if code and code in entity_by_code:
            mapping[plant_id] = entity_by_code[code]
    return mapping


def repair_project_entities_fk_sqlite(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "sqlite":
        return

    table_name = "projects_project_entities"
    legacy_table_name = "projects_project_entities_legacy_fk"
    tables = set(connection.introspection.table_names())
    if table_name not in tables or "structure_entity" not in tables:
        return

    current_target = _fk_target_for_column(connection, table_name, "entity_id")
    if current_target == "structure_entity":
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT project_id, entity_id FROM projects_project_entities")
        current_rows = cursor.fetchall()
        cursor.execute("SELECT id, code FROM structure_entity")
        entity_rows = cursor.fetchall()

    entity_by_id = {entity_id: entity_id for entity_id, _ in entity_rows}
    entity_by_code = {code: entity_id for entity_id, code in entity_rows if code}
    plant_to_entity = _build_plant_to_entity_map(connection, entity_by_id, entity_by_code)

    repaired_rows = []
    dedupe = set()
    for project_id, raw_entity_id in current_rows:
        resolved_entity_id = raw_entity_id
        if resolved_entity_id not in entity_by_id:
            resolved_entity_id = plant_to_entity.get(raw_entity_id)
        if resolved_entity_id not in entity_by_id:
            continue
        key = (project_id, resolved_entity_id)
        if key in dedupe:
            continue
        dedupe.add(key)
        repaired_rows.append(key)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND tbl_name = %s
              AND name NOT LIKE 'sqlite_%%'
            """,
            [table_name],
        )
        index_names = [row[0] for row in cursor.fetchall()]
        for index_name in index_names:
            cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')

        cursor.execute(f'ALTER TABLE "{table_name}" RENAME TO "{legacy_table_name}"')
        cursor.execute(
            """
            CREATE TABLE "projects_project_entities" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "project_id" bigint NOT NULL
                    REFERENCES "projects_project" ("id") DEFERRABLE INITIALLY DEFERRED,
                "entity_id" bigint NOT NULL
                    REFERENCES "structure_entity" ("id") DEFERRABLE INITIALLY DEFERRED
            )
            """
        )
        if repaired_rows:
            cursor.executemany(
                """
                INSERT INTO "projects_project_entities" ("project_id", "entity_id")
                VALUES (%s, %s)
                """,
                repaired_rows,
            )
        cursor.execute(f'DROP TABLE "{legacy_table_name}"')
        cursor.execute(
            """
            CREATE INDEX "projects_project_entities_project_id_idx"
            ON "projects_project_entities" ("project_id")
            """
        )
        cursor.execute(
            """
            CREATE INDEX "projects_project_entities_entity_id_idx"
            ON "projects_project_entities" ("entity_id")
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX "projects_project_entities_project_entity_uniq"
            ON "projects_project_entities" ("project_id", "entity_id")
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0004_project_workflow_fields"),
    ]

    operations = [
        migrations.RunPython(repair_project_entities_fk_sqlite, migrations.RunPython.noop),
    ]

