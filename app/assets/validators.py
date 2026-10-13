from __future__ import annotations

from datetime import date
from typing import Any

from common.normalization import normalized_ip, normalized_text

from .lifecycle import ALL_STATUSES, ALL_TYPES

ASSET_WRITE_FIELDS = {
    "name",
    "asset_no",
    "type",
    "purpose",
    "environment",
    "owner",
    "status",
    "room",
    "region",
    "hardware_text",
    "serial",
    "hostname",
    "supplier",
    "purchase_date",
    "rack_date",
    "warranty_end",
    "expires_on",
    "credential_ref",
    "host_asset_no",
    "internal_ips",
    "external_ips",
}
COMMON_REQUIRED = {"name", "asset_no", "type", "purpose", "environment", "owner", "status", "room", "region"}
OPTIONAL_TEXT_FIELDS = {"hardware_text", "serial", "hostname", "supplier", "credential_ref", "host_asset_no"}
DATE_FIELDS = {"purchase_date", "rack_date", "warranty_end", "expires_on"}
AUDIT_FIELDS = ASSET_WRITE_FIELDS - {"credential_ref"}

TEXT_LIMITS = {
    "name": 255,
    "asset_no": 255,
    "type": 16,
    "purpose": 4096,
    "environment": 128,
    "owner": 128,
    "status": 16,
    "room": 128,
    "region": 128,
    "hardware_text": 16384,
    "serial": 255,
    "hostname": 253,
    "supplier": 255,
    "credential_ref": 2048,
    "host_asset_no": 255,
}


def _clean_text(value: object, *, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{field.upper()}_REQUIRED")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field.upper()}_INVALID")
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise ValueError(f"{field.upper()}_REQUIRED")
        return None
    if len(cleaned) > TEXT_LIMITS[field]:
        raise ValueError(f"{field.upper()}_TOO_LONG")
    return cleaned


def _clean_date(value: object, *, field: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field.upper()}_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field.upper()}_INVALID") from exc


def _clean_ips(value: object, *, field: str) -> list[dict[str, str]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field.upper()}_INVALID")
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        try:
            key = normalized_ip(item)
        except ValueError as exc:
            raise ValueError("IP_INVALID") from exc
        if key in seen:
            raise ValueError("IP_DUPLICATE")
        seen.add(key)
        cleaned.append({"display": item.strip(), "key": key})
    return cleaned


def normalize_asset_payload(data: dict[str, object], *, partial: bool = False, current: dict[str, Any] | None = None) -> dict[str, Any]:
    unknown = set(data) - ASSET_WRITE_FIELDS - {"version"}
    if unknown:
        raise ValueError("ASSET_FIELDS_INVALID")
    values = dict(current or {})
    required = set() if partial else COMMON_REQUIRED
    for field in COMMON_REQUIRED:
        if field in data or field in required:
            values[field] = _clean_text(data.get(field), field=field, required=True)
    for field in OPTIONAL_TEXT_FIELDS:
        if field in data or (not partial and field not in values):
            values[field] = _clean_text(data.get(field), field=field)
    for field in DATE_FIELDS:
        if field in data or (not partial and field not in values):
            values[field] = _clean_date(data.get(field), field=field)
    if "internal_ips" in data or (not partial and "internal_ips" not in values):
        values["internal_ips"] = _clean_ips(data.get("internal_ips", []), field="internal_ips")
    if "external_ips" in data or (not partial and "external_ips" not in values):
        values["external_ips"] = _clean_ips(data.get("external_ips", []), field="external_ips")

    asset_type = values.get("type")
    status = values.get("status")
    if asset_type not in ALL_TYPES:
        raise ValueError("TYPE_INVALID")
    if status not in ALL_STATUSES:
        raise ValueError("STATUS_INVALID")
    if values["rack_date"] and values["purchase_date"] and values["rack_date"] < values["purchase_date"]:
        raise ValueError("DATE_ORDER_INVALID")
    if values["type"] == "physical":
        if not values.get("serial"):
            raise ValueError("SERIAL_REQUIRED")
        if not values.get("hostname"):
            raise ValueError("HOSTNAME_REQUIRED")
    elif values["type"] == "virtual":
        if not values.get("hostname"):
            raise ValueError("HOSTNAME_REQUIRED")
        if not values.get("host_asset_no"):
            raise ValueError("HOST_REQUIRED")
    elif values["type"] in {"network", "storage"} and not values.get("serial"):
        raise ValueError("SERIAL_REQUIRED")
    if values["type"] != "virtual" and values.get("host_asset_no"):
        raise ValueError("HOST_NOT_APPLICABLE")

    ip_keys = [item["key"] for item in values["internal_ips"]] + [item["key"] for item in values["external_ips"]]
    if len(ip_keys) != len(set(ip_keys)):
        raise ValueError("IP_DUPLICATE")
    values["asset_no_key"] = normalized_text(values["asset_no"])
    values["serial_key"] = normalized_text(values["serial"]) if values.get("serial") else None
    values["hostname_key"] = normalized_text(values["hostname"]) if values.get("hostname") else None
    values["host_asset_no_key"] = normalized_text(values["host_asset_no"]) if values.get("host_asset_no") else None
    return values


def audit_payload(values: dict[str, Any]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for field in sorted(AUDIT_FIELDS):
        value = values.get(field)
        if field in {"internal_ips", "external_ips"}:
            payload[field] = [item["key"] if isinstance(item, dict) else item for item in value or []]
        elif isinstance(value, date):
            payload[field] = value.isoformat()
        else:
            payload[field] = value
    return payload
