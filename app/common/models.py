import uuid

from django.db import models


class SystemSetting(models.Model):
    key = models.CharField(max_length=128, primary_key=True)
    typed_value = models.JSONField()
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk__isnull=True), name="system_setting_empty_allowlist")]

class OperationReceipt(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_uuid = models.UUIDField()
    idempotency_key = models.CharField(max_length=256)
    operation_uuid = models.UUIDField(unique=True)
    request_digest = models.CharField(max_length=64)
    confirmation_uuid = models.UUIDField(null=True)
    result_ref = models.JSONField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor_uuid", "idempotency_key"], name="receipt_actor_key")]


class ChangeConfirmation(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_digest = models.CharField(max_length=64, unique=True)
    actor_uuid = models.UUIDField()
    actor_auth_version = models.PositiveBigIntegerField()
    session_epoch = models.PositiveBigIntegerField()
    target_kind = models.CharField(max_length=64)
    target_uuid = models.UUIDField(null=True)
    target_version = models.PositiveBigIntegerField(null=True)
    actions = models.JSONField()
    proposed_changes = models.JSONField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    operation_uuid = models.UUIDField(null=True)


class Job(models.Model):
    uuid = models.UUIDField(primary_key=True)
    kind = models.CharField(max_length=64)
    state = models.CharField(max_length=32, default="queued")
    payload = models.JSONField(default=dict)
    attempts = models.PositiveIntegerField(default=0)
    claimed_at = models.DateTimeField(null=True)
    operation_uuid = models.UUIDField(unique=True)
