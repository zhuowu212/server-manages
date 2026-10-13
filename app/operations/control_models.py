import uuid

from django.db import models


class BackupCatalog(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=32)
    state = models.CharField(max_length=32)
    size = models.PositiveBigIntegerField(default=0)
    path = models.CharField(max_length=4096)
    digest = models.CharField(max_length=128)
    key_id = models.CharField(max_length=256)
    pin_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "operations"
        constraints = [
            models.CheckConstraint(condition=models.Q(source__in=["manual", "automatic", "recovery_protection"]), name="backup_source_valid"),
            models.CheckConstraint(condition=models.Q(state__in=["creating", "available", "failed", "deleting", "deleted"]), name="backup_state_valid"),
            models.CheckConstraint(condition=models.Q(pin_count__gte=0), name="backup_pin_nonnegative"),
        ]


class RestoreOperation(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phase = models.CharField(max_length=32)
    old_generation = models.UUIDField(null=True)
    new_generation = models.UUIDField(null=True)
    epoch = models.PositiveBigIntegerField(default=0)
    receipt_digest = models.CharField(max_length=128)
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = "operations"
        constraints = [models.CheckConstraint(condition=models.Q(phase__in=["VALIDATING", "PREBACKUP", "PREPARED", "REPLACING", "VERIFYING", "COMMITTED", "ROLLING_BACK", "ROLLED_BACK", "MANUAL_RECOVERY"]), name="restore_phase_valid")]


class SessionEpoch(models.Model):
    singleton = models.BooleanField(primary_key=True, default=True)
    epoch = models.PositiveBigIntegerField(default=1)
    maintenance = models.BooleanField(default=False)

    class Meta:
        app_label = "operations"
        constraints = [models.CheckConstraint(condition=models.Q(epoch__gte=1), name="session_epoch_positive")]


class ControlConfirmation(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_digest = models.CharField(max_length=64, unique=True)
    actor_uuid = models.UUIDField()
    actor_auth_version = models.PositiveBigIntegerField()
    epoch = models.PositiveBigIntegerField()
    target_kind = models.CharField(max_length=64)
    target_uuid = models.UUIDField(null=True)
    target_version = models.PositiveBigIntegerField(null=True)
    actions = models.JSONField()
    proposed_changes = models.JSONField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    operation_uuid = models.UUIDField(null=True)

    class Meta:
        app_label = "operations"


class ControlReceipt(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_uuid = models.UUIDField()
    idempotency_key = models.CharField(max_length=256)
    operation_uuid = models.UUIDField(unique=True)
    request_digest = models.CharField(max_length=64)
    confirmation_uuid = models.UUIDField(null=True)
    result_ref = models.JSONField(null=True)

    class Meta:
        app_label = "operations"
        constraints = [models.UniqueConstraint(fields=["actor_uuid", "idempotency_key"], name="control_receipt_actor_key")]
