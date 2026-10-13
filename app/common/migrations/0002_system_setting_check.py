from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("common", "0001_initial")]
    operations = [migrations.RunSQL(
        "SELECT 1",
        reverse_sql=migrations.RunSQL.noop,
    )]
