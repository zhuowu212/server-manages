import uuid

from django.db import models


class AssetIdentity(models.Model):
    normalized_asset_no = models.CharField(max_length=255, primary_key=True)
    asset_uuid = models.UUIDField(unique=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_deleted_at = models.DateTimeField(null=True)


class Asset(models.Model):
    class Type(models.TextChoices):
        PHYSICAL = "physical", "物理机"
        VIRTUAL = "virtual", "虚拟机"
        NETWORK = "network", "网络设备"
        STORAGE = "storage", "存储设备"

    class Status(models.TextChoices):
        PLANNED = "planned", "规划"
        PURCHASED = "purchased", "已采购"
        RACKED = "racked", "已上架"
        ACTIVE = "active", "运行中"
        REPAIR = "repair", "维修中"
        RETIRED = "retired", "已退役"

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.OneToOneField(AssetIdentity, on_delete=models.PROTECT, related_name="asset")
    asset_no = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=16, choices=Type.choices)
    purpose = models.CharField(max_length=4096)
    environment = models.CharField(max_length=128)
    owner = models.CharField(max_length=128)
    status = models.CharField(max_length=16, choices=Status.choices)
    room = models.CharField(max_length=128)
    region = models.CharField(max_length=128)
    hardware_text = models.CharField(max_length=16384, null=True, blank=True)
    serial = models.CharField(max_length=255, null=True, blank=True)
    serial_key = models.CharField(max_length=255, null=True, blank=True, unique=True)
    hostname = models.CharField(max_length=253, null=True, blank=True)
    hostname_key = models.CharField(max_length=253, null=True, blank=True, unique=True)
    supplier = models.CharField(max_length=255, null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    rack_date = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    credential_ref = models.CharField(max_length=2048, null=True, blank=True)
    host = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="virtual_children")
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(type__in=["physical", "virtual", "network", "storage"]), name="asset_type_valid"),
            models.CheckConstraint(condition=models.Q(status__in=["planned", "purchased", "racked", "active", "repair", "retired"]), name="asset_status_valid"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="asset_version_positive"),
            models.CheckConstraint(condition=models.Q(type="virtual") | models.Q(host__isnull=True), name="asset_nonvirtual_host_null"),
            models.CheckConstraint(condition=models.Q(purchase_date__isnull=True) | models.Q(rack_date__isnull=True) | models.Q(rack_date__gte=models.F("purchase_date")), name="asset_rack_after_purchase"),
        ]


class AssetAddress(models.Model):
    class Scope(models.TextChoices):
        INTERNAL = "internal", "内网"
        EXTERNAL = "external", "外网"

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="addresses")
    scope = models.CharField(max_length=16, choices=Scope.choices)
    ip_display = models.CharField(max_length=64)
    ip_key = models.CharField(max_length=64, unique=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(scope__in=["internal", "external"]), name="asset_address_scope_valid"),
        ]
