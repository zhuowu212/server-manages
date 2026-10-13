from __future__ import annotations

from datetime import date
from typing import Any

from .models import Asset, AssetAddress


def _date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def asset_to_values(asset: Asset) -> dict[str, Any]:
    addresses = list(asset.addresses.all())
    return {
        "name": asset.name,
        "asset_no": asset.asset_no,
        "type": asset.type,
        "purpose": asset.purpose,
        "environment": asset.environment,
        "owner": asset.owner,
        "status": asset.status,
        "room": asset.room,
        "region": asset.region,
        "hardware_text": asset.hardware_text,
        "serial": asset.serial,
        "hostname": asset.hostname,
        "supplier": asset.supplier,
        "purchase_date": asset.purchase_date,
        "rack_date": asset.rack_date,
        "warranty_end": asset.warranty_end,
        "expires_on": asset.expires_on,
        "credential_ref": asset.credential_ref,
        "host_asset_no": asset.host.asset_no if asset.host else None,
        "internal_ips": [{"display": item.ip_display, "key": item.ip_key} for item in addresses if item.scope == AssetAddress.Scope.INTERNAL],
        "external_ips": [{"display": item.ip_display, "key": item.ip_key} for item in addresses if item.scope == AssetAddress.Scope.EXTERNAL],
    }


def public_asset(asset: Asset) -> dict[str, object]:
    values = asset_to_values(asset)
    return {
        "id": str(asset.uuid),
        "asset_no": asset.asset_no,
        "name": asset.name,
        "type": asset.type,
        "purpose": asset.purpose,
        "environment": asset.environment,
        "owner": asset.owner,
        "status": asset.status,
        "room": asset.room,
        "region": asset.region,
        "hardware_text": asset.hardware_text,
        "serial": asset.serial,
        "hostname": asset.hostname,
        "supplier": asset.supplier,
        "purchase_date": _date(asset.purchase_date),
        "rack_date": _date(asset.rack_date),
        "warranty_end": _date(asset.warranty_end),
        "expires_on": _date(asset.expires_on),
        "credential_ref": asset.credential_ref,
        "host_asset_no": asset.host.asset_no if asset.host else None,
        "internal_ips": [item["key"] for item in values["internal_ips"]],
        "external_ips": [item["key"] for item in values["external_ips"]],
        "version": asset.version,
    }
