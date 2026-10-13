from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("assets", "0001_initial")]

    operations = [
        migrations.RunSQL(
            """
            CREATE TRIGGER asset_host_insert_guard
            BEFORE INSERT ON assets_asset
            WHEN NEW.host_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM assets_asset host
              WHERE host.uuid = NEW.host_id
                AND host.type = 'physical'
                AND host.status IN ('racked', 'active', 'repair')
            )
            BEGIN
              SELECT RAISE(ABORT, 'INVALID_HOST');
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS asset_host_insert_guard;",
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER asset_host_update_guard
            BEFORE UPDATE OF host_id ON assets_asset
            WHEN NEW.host_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM assets_asset host
              WHERE host.uuid = NEW.host_id
                AND host.type = 'physical'
                AND host.status IN ('racked', 'active', 'repair')
            )
            BEGIN
              SELECT RAISE(ABORT, 'INVALID_HOST');
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS asset_host_update_guard;",
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER asset_host_child_guard
            BEFORE UPDATE OF type, status ON assets_asset
            WHEN EXISTS (SELECT 1 FROM assets_asset child WHERE child.host_id = OLD.uuid)
              AND NOT (NEW.type = 'physical' AND NEW.status IN ('racked', 'active', 'repair'))
            BEGIN
              SELECT RAISE(ABORT, 'DEPENDENCY_CONFLICT');
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS asset_host_child_guard;",
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER asset_host_delete_guard
            BEFORE DELETE ON assets_asset
            WHEN EXISTS (SELECT 1 FROM assets_asset child WHERE child.host_id = OLD.uuid)
            BEGIN
              SELECT RAISE(ABORT, 'DEPENDENCY_CONFLICT');
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS asset_host_delete_guard;",
        ),
    ]
