import uuid

from django.db import models


class AuditEvent(models.Model):
    event_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance_id = models.UUIDField()
    time_utc = models.DateTimeField(auto_now_add=True)
    actor_uuid = models.UUIDField(null=True)
    actor_name_snapshot = models.CharField(max_length=128, blank=True)
    asset_uuid = models.UUIDField(null=True)
    asset_no_snapshot = models.CharField(max_length=255, blank=True)
    asset_name_snapshot = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=32)
    action = models.CharField(max_length=64)
    result = models.CharField(max_length=32)
    request_id = models.UUIDField(null=True)
    operation_uuid = models.UUIDField(null=True)
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    summary = models.JSONField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(category__in=["asset", "authentication", "account", "import", "export", "backup", "restore", "security"]),
                name="audit_category_valid",
            ),
            models.CheckConstraint(condition=models.Q(result__in=["started", "success", "rejected", "denied", "failed", "partial", "interrupted", "transferred", "aborted", "rolled_back", "recovery_required"]), name="audit_result_valid"),
        ]
