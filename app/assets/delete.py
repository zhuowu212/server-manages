from __future__ import annotations

from datetime import timedelta

from accounts.models import User
from common.confirmations import issue_token, token_digest
from common.models import ChangeConfirmation
from django.db import transaction
from django.utils import timezone
from operations.gate import current_epoch

from .models import Asset


def create_delete_confirmation(*, actor: User, asset: Asset) -> str:
    raw, digest = issue_token()
    with transaction.atomic():
        ChangeConfirmation.objects.create(
            token_digest=digest,
            actor_uuid=actor.uuid,
            actor_auth_version=actor.auth_version,
            session_epoch=current_epoch(),
            target_kind="asset",
            target_uuid=asset.uuid,
            target_version=asset.version,
            actions=["delete"],
            proposed_changes={},
            expires_at=timezone.now() + timedelta(minutes=5),
        )
    return raw


def consume_delete_confirmation(*, raw: str, actor: User, asset: Asset) -> ChangeConfirmation:
    confirmation = ChangeConfirmation.objects.select_for_update().filter(token_digest=token_digest(raw)).first()
    if not confirmation or confirmation.consumed_at or confirmation.expires_at <= timezone.now():
        raise ValueError("CONFIRMATION_INVALID")
    if (
        confirmation.actor_uuid != actor.uuid
        or confirmation.actor_auth_version != actor.auth_version
        or confirmation.session_epoch != current_epoch()
        or confirmation.target_kind != "asset"
        or confirmation.target_uuid != asset.uuid
        or confirmation.target_version != asset.version
        or confirmation.actions != ["delete"]
        or confirmation.proposed_changes != {}
    ):
        raise ValueError("CONFIRMATION_MISMATCH")
    confirmation.consumed_at = timezone.now()
    confirmation.save(update_fields=["consumed_at"])
    return confirmation
