from __future__ import annotations

import uuid
from typing import Any

from accounts.models import User
from common.receipts import save_receipt
from django.db import IntegrityError, transaction
from django.utils import timezone

from .audit import record_asset_event
from .delete import consume_delete_confirmation, create_delete_confirmation
from .lifecycle import editor_can_transition
from .models import Asset, AssetAddress, AssetIdentity
from .relationships import blocking_children, ensure_host_can_change, resolve_host
from .serializers import asset_to_values, public_asset
from .validators import ASSET_WRITE_FIELDS, audit_payload, normalize_asset_payload

ASSET_RECEIPT_KEYS = frozenset({"route", "target_uuid", "version", *ASSET_WRITE_FIELDS} - {"credential_ref"})


class AssetAuthorizationError(ValueError):
    pass


def _precheck_unique(values: dict[str, Any], *, exclude_uuid=None) -> None:
    if AssetIdentity.objects.filter(normalized_asset_no=values["asset_no_key"]).exists():
        raise ValueError("ASSET_NO_CONFLICT")
    _precheck_current_unique(values, exclude_uuid=exclude_uuid)


def _precheck_current_unique(values: dict[str, Any], *, exclude_uuid=None) -> None:
    if values.get("serial_key"):
        query = Asset.objects.filter(serial_key=values["serial_key"])
        if exclude_uuid:
            query = query.exclude(uuid=exclude_uuid)
        if query.exists():
            raise ValueError("SERIAL_CONFLICT")
    if values.get("hostname_key"):
        query = Asset.objects.filter(hostname_key=values["hostname_key"])
        if exclude_uuid:
            query = query.exclude(uuid=exclude_uuid)
        if query.exists():
            raise ValueError("HOSTNAME_CONFLICT")
    ip_keys = [item["key"] for item in values["internal_ips"]] + [item["key"] for item in values["external_ips"]]
    if ip_keys:
        address_query = AssetAddress.objects.filter(ip_key__in=ip_keys)
        if exclude_uuid:
            address_query = address_query.exclude(asset_id=exclude_uuid)
        if address_query.exists():
            raise ValueError("IP_CONFLICT")


def _apply_addresses(asset: Asset, values: dict[str, Any]) -> None:
    asset.addresses.all().delete()
    rows = []
    for scope, field in ((AssetAddress.Scope.INTERNAL, "internal_ips"), (AssetAddress.Scope.EXTERNAL, "external_ips")):
        for item in values[field]:
            rows.append(AssetAddress(asset=asset, scope=scope, ip_display=item["display"], ip_key=item["key"]))
    AssetAddress.objects.bulk_create(rows)


def _set_asset_fields(asset: Asset, values: dict[str, Any], host: Asset | None) -> None:
    asset.asset_no = values["asset_no"]
    asset.name = values["name"]
    asset.type = values["type"]
    asset.purpose = values["purpose"]
    asset.environment = values["environment"]
    asset.owner = values["owner"]
    asset.status = values["status"]
    asset.room = values["room"]
    asset.region = values["region"]
    asset.hardware_text = values.get("hardware_text")
    asset.serial = values.get("serial")
    asset.serial_key = values.get("serial_key")
    asset.hostname = values.get("hostname")
    asset.hostname_key = values.get("hostname_key")
    asset.supplier = values.get("supplier")
    asset.purchase_date = values.get("purchase_date")
    asset.rack_date = values.get("rack_date")
    asset.warranty_end = values.get("warranty_end")
    asset.expires_on = values.get("expires_on")
    asset.credential_ref = values.get("credential_ref")
    asset.host = host


def create_asset(
    *,
    actor: User,
    payload: dict[str, object],
    idempotency_key: str | None = None,
    receipt_payload: dict[str, object] | None = None,
) -> Asset:
    if actor.role not in {User.Role.ADMIN, User.Role.EDITOR}:
        raise AssetAuthorizationError("FORBIDDEN")
    values = normalize_asset_payload(payload)
    _precheck_unique(values)
    host = resolve_host(values.get("host_asset_no"))
    asset_uuid = uuid.uuid4()
    operation_uuid = uuid.uuid4()
    try:
        with transaction.atomic():
            identity = AssetIdentity.objects.create(
                normalized_asset_no=values["asset_no_key"],
                asset_uuid=asset_uuid,
            )
            asset = Asset(uuid=asset_uuid, identity=identity)
            _set_asset_fields(asset, values, host)
            asset.save()
            _apply_addresses(asset, values)
            record_asset_event(
                action="created",
                result="success",
                actor=actor,
                operation_uuid=operation_uuid,
                asset_uuid=asset.uuid,
                asset_no=asset.asset_no,
                asset_name=asset.name,
                before=None,
                after=audit_payload(values),
            )
            if idempotency_key and receipt_payload is not None:
                save_receipt(
                    actor_uuid=actor.uuid,
                    idempotency_key=idempotency_key,
                    payload=receipt_payload,
                    operation_uuid=operation_uuid,
                    result_ref={"id": str(asset.uuid), "version": asset.version},
                    allowed_keys=ASSET_RECEIPT_KEYS,
                )
            return asset
    except IntegrityError as exc:
        raise ValueError(_constraint_code(exc)) from exc


def update_asset(
    *,
    actor: User,
    asset: Asset,
    version: int,
    payload: dict[str, object],
    idempotency_key: str | None = None,
    receipt_payload: dict[str, object] | None = None,
) -> Asset:
    with transaction.atomic():
        asset = Asset.objects.select_for_update().select_related("identity", "host", "host__identity").prefetch_related("addresses").get(pk=asset.pk)
        if asset.version != version:
            raise ValueError("STALE_VERSION")
        current = asset_to_values(asset)
        values = normalize_asset_payload(payload, partial=True, current=current)
        if values["asset_no_key"] != asset.identity.normalized_asset_no:
            raise ValueError("ASSET_NO_IMMUTABLE")
        if actor.role == User.Role.EDITOR and not editor_can_transition(asset.status, values["status"]):
            raise AssetAuthorizationError("FORBIDDEN")
        if actor.role not in {User.Role.ADMIN, User.Role.EDITOR}:
            raise AssetAuthorizationError("FORBIDDEN")
        ensure_host_can_change(asset, new_type=values["type"], new_status=values["status"])
        host = resolve_host(values.get("host_asset_no"), self_uuid=asset.uuid)
        _precheck_current_unique(values, exclude_uuid=asset.uuid)
        before = audit_payload(current)
        _set_asset_fields(asset, values, host)
        asset.version += 1
        try:
            asset.save()
            _apply_addresses(asset, values)
        except IntegrityError as exc:
            raise ValueError(_constraint_code(exc)) from exc
        operation_uuid = uuid.uuid4()
        action = "status_changed" if before.get("status") != values["status"] else "updated"
        record_asset_event(
            action=action,
            result="success",
            actor=actor,
            operation_uuid=operation_uuid,
            asset_uuid=asset.uuid,
            asset_no=asset.asset_no,
            asset_name=asset.name,
            before=before,
            after=audit_payload(values),
        )
        if idempotency_key and receipt_payload is not None:
            save_receipt(
                actor_uuid=actor.uuid,
                idempotency_key=idempotency_key,
                payload=receipt_payload,
                operation_uuid=operation_uuid,
                result_ref=public_asset(asset),
                allowed_keys=ASSET_RECEIPT_KEYS,
            )
        return asset


def preview_delete_asset(*, actor: User, asset: Asset) -> dict[str, object]:
    if actor.role != User.Role.ADMIN:
        raise AssetAuthorizationError("FORBIDDEN")
    blockers = blocking_children(asset)
    if blockers:
        raise ValueError("DEPENDENCY_CONFLICT")
    token = create_delete_confirmation(actor=actor, asset=asset)
    return {
        "id": str(asset.uuid),
        "asset_no": asset.asset_no,
        "name": asset.name,
        "version": asset.version,
        "confirmation_id": token,
        "blockers": [],
    }


def delete_asset(
    *,
    actor: User,
    asset: Asset,
    version: int,
    confirmation: str,
    idempotency_key: str | None = None,
    receipt_payload: dict[str, object] | None = None,
) -> None:
    if actor.role != User.Role.ADMIN:
        raise AssetAuthorizationError("FORBIDDEN")
    with transaction.atomic():
        asset = Asset.objects.select_for_update().select_related("identity", "host", "host__identity").prefetch_related("addresses").get(pk=asset.pk)
        if asset.version != version:
            raise ValueError("STALE_VERSION")
        if blocking_children(asset):
            raise ValueError("DEPENDENCY_CONFLICT")
        used_confirmation = consume_delete_confirmation(raw=confirmation, actor=actor, asset=asset)
        before = audit_payload(asset_to_values(asset))
        operation_uuid = uuid.uuid4()
        asset_uuid = asset.uuid
        asset_no = asset.asset_no
        asset_name = asset.name
        identity = asset.identity
        asset.delete()
        identity.last_deleted_at = timezone.now()
        identity.save(update_fields=["last_deleted_at"])
        record_asset_event(
            action="deleted",
            result="success",
            actor=actor,
            operation_uuid=operation_uuid,
            asset_uuid=asset_uuid,
            asset_no=asset_no,
            asset_name=asset_name,
            before=before,
            after=None,
        )
        if idempotency_key and receipt_payload is not None:
            save_receipt(
                actor_uuid=actor.uuid,
                idempotency_key=idempotency_key,
                payload=receipt_payload,
                operation_uuid=operation_uuid,
                confirmation_uuid=used_confirmation.uuid,
                result_ref={"deleted": True},
                allowed_keys=ASSET_RECEIPT_KEYS,
            )


def _constraint_code(exc: IntegrityError) -> str:
    message = str(exc)
    if "assets_assetaddress.ip_key" in message:
        return "IP_CONFLICT"
    if "assets_asset.serial_key" in message:
        return "SERIAL_CONFLICT"
    if "assets_asset.hostname_key" in message:
        return "HOSTNAME_CONFLICT"
    if "assets_assetidentity" in message:
        return "ASSET_NO_CONFLICT"
    if "INVALID_HOST" in message:
        return "INVALID_HOST"
    if "DEPENDENCY_CONFLICT" in message:
        return "DEPENDENCY_CONFLICT"
    return "ASSET_CONSTRAINT_FAILED"
