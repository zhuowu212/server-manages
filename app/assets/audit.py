from __future__ import annotations

import uuid

from accounts.models import User
from audit.services import record_event
from common.errors import AuditUnavailable


def record_asset_event(
    *,
    action: str,
    result: str,
    actor: User,
    operation_uuid: uuid.UUID,
    asset_uuid,
    asset_no: str,
    asset_name: str,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
    summary: dict[str, object] | None = None,
):
    try:
        return record_event(
            category="asset",
            action=action,
            result=result,
            actor_uuid=actor.uuid,
            actor_name_snapshot=actor.display_name,
            asset_uuid=asset_uuid,
            asset_no_snapshot=asset_no,
            asset_name_snapshot=asset_name,
            operation_uuid=operation_uuid,
            before=before,
            after=after,
            summary=summary or {"changed": True, "target_kind": "asset", "target_uuid": str(asset_uuid)},
        )
    except Exception as exc:
        raise AuditUnavailable() from exc
