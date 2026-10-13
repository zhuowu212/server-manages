from __future__ import annotations

from common.normalization import normalized_text

from .lifecycle import VALID_HOST_STATUSES
from .models import Asset


def resolve_host(host_asset_no: str | None, *, self_uuid=None) -> Asset | None:
    if not host_asset_no:
        return None
    host = Asset.objects.select_related("identity").filter(
        identity__normalized_asset_no=normalized_text(host_asset_no)
    ).first()
    if host is None:
        raise ValueError("INVALID_HOST")
    if self_uuid is not None and host.uuid == self_uuid:
        raise ValueError("INVALID_HOST")
    if host.type != Asset.Type.PHYSICAL or host.status not in VALID_HOST_STATUSES:
        raise ValueError("INVALID_HOST")
    return host


def ensure_host_can_change(asset: Asset, *, new_type: str, new_status: str) -> None:
    if asset.virtual_children.exists() and (new_type != Asset.Type.PHYSICAL or new_status not in VALID_HOST_STATUSES):
        raise ValueError("DEPENDENCY_CONFLICT")


def blocking_children(asset: Asset) -> list[Asset]:
    return list(asset.virtual_children.select_related("identity").order_by("identity__normalized_asset_no"))
