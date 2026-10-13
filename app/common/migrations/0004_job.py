import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("common", "0003_changeconfirmation_operationreceipt")]
    operations = [migrations.CreateModel(
        name="Job",
        fields=[
            ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("kind", models.CharField(max_length=64)),
            ("state", models.CharField(default="queued", max_length=32)),
            ("payload", models.JSONField(default=dict)),
            ("attempts", models.PositiveIntegerField(default=0)),
            ("claimed_at", models.DateTimeField(null=True)),
            ("operation_uuid", models.UUIDField(unique=True)),
        ],
    )]
