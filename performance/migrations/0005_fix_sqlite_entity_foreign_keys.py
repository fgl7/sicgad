from django.db import migrations


def _sqlite_table_sql(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=%s",
            [table_name],
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _has_structure_entity_fk_issue(connection, table_name):
    sql = _sqlite_table_sql(connection, table_name) or ""
    return 'REFERENCES "plants_plant"' in sql and '"entity_id"' in sql


def _assert_no_orphans(connection, table_name, fk_column, target_table):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM "{table_name}" t
            LEFT JOIN "{target_table}" x ON x.id = t."{fk_column}"
            WHERE x.id IS NULL
            """
        )
        count = cursor.fetchone()[0]
    if count:
        raise RuntimeError(
            f"No se puede reparar FK de {table_name}.{fk_column}: hay {count} filas sin referencia en {target_table}."
        )


def _rebuild_performance_variable(connection):
    _assert_no_orphans(connection, "performance_performancevariable", "entity_id", "structure_entity")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE "performance_performancevariable__new" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "key" varchar(80) NOT NULL UNIQUE,
                "label" varchar(255) NOT NULL,
                "unit" varchar(50) NOT NULL,
                "value_type" varchar(20) NOT NULL,
                "description" text NOT NULL,
                "is_active" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "entity_id" bigint NOT NULL REFERENCES "structure_entity" ("id") DEFERRABLE INITIALLY DEFERRED
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO "performance_performancevariable__new"
            ("id","key","label","unit","value_type","description","is_active","created_at","updated_at","entity_id")
            SELECT
            "id","key","label","unit","value_type","description","is_active","created_at","updated_at","entity_id"
            FROM "performance_performancevariable"
            """
        )
        cursor.execute('DROP TABLE "performance_performancevariable"')
        cursor.execute(
            'ALTER TABLE "performance_performancevariable__new" RENAME TO "performance_performancevariable"'
        )
        cursor.execute(
            'CREATE INDEX "performance_performancevariable_plant_id_3aeaa62c" '
            'ON "performance_performancevariable" ("entity_id")'
        )


def _rebuild_performance_indicator_result(connection):
    _assert_no_orphans(connection, "performance_performanceindicatorresult", "entity_id", "structure_entity")
    _assert_no_orphans(
        connection, "performance_performanceindicatorresult", "indicator_id", "performance_performanceindicator"
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE "performance_performanceindicatorresult__new" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "period_start" date NOT NULL,
                "period_end" date NOT NULL,
                "frequency" varchar(20) NOT NULL,
                "stage" varchar(20) NOT NULL,
                "status" varchar(20) NOT NULL,
                "numeric_value" real NULL,
                "text_value" text NOT NULL,
                "trace" text NOT NULL CHECK ((JSON_VALID("trace") OR "trace" IS NULL)),
                "computed_at" datetime NOT NULL,
                "indicator_id" bigint NOT NULL REFERENCES "performance_performanceindicator" ("id") DEFERRABLE INITIALLY DEFERRED,
                "entity_id" bigint NOT NULL REFERENCES "structure_entity" ("id") DEFERRABLE INITIALLY DEFERRED
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO "performance_performanceindicatorresult__new"
            ("id","period_start","period_end","frequency","stage","status","numeric_value","text_value","trace","computed_at","indicator_id","entity_id")
            SELECT
            "id","period_start","period_end","frequency","stage","status","numeric_value","text_value","trace","computed_at","indicator_id","entity_id"
            FROM "performance_performanceindicatorresult"
            """
        )
        cursor.execute('DROP TABLE "performance_performanceindicatorresult"')
        cursor.execute(
            'ALTER TABLE "performance_performanceindicatorresult__new" RENAME TO "performance_performanceindicatorresult"'
        )
        cursor.execute(
            'CREATE INDEX "performance_performanceindicatorresult_plant_id_2fc668a0" '
            'ON "performance_performanceindicatorresult" ("entity_id")'
        )
        cursor.execute(
            'CREATE INDEX "performance_performanceindicatorresult_indicator_id_d4442039" '
            'ON "performance_performanceindicatorresult" ("indicator_id")'
        )
        cursor.execute(
            'CREATE UNIQUE INDEX "performance_performanceindicatorresult_indicator_id_plant_id_period_end_frequency_7afba515_uniq" '
            'ON "performance_performanceindicatorresult" ("indicator_id", "entity_id", "period_end", "frequency")'
        )


def fix_sqlite_entity_foreign_keys(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "sqlite":
        return

    needs_variable_fix = _has_structure_entity_fk_issue(connection, "performance_performancevariable")
    needs_result_fix = _has_structure_entity_fk_issue(connection, "performance_performanceindicatorresult")
    if not (needs_variable_fix or needs_result_fix):
        return

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF")
    try:
        if needs_variable_fix:
            _rebuild_performance_variable(connection)
        if needs_result_fix:
            _rebuild_performance_indicator_result(connection)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA foreign_key_check")
            violations = cursor.fetchall()
    if violations:
        raise RuntimeError(f"Persisten violaciones de FK luego de la reparacion: {violations[:5]}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("performance", "0004_performanceindicator_approved_at_and_more"),
    ]

    operations = [
        migrations.RunPython(fix_sqlite_entity_foreign_keys, migrations.RunPython.noop),
    ]

