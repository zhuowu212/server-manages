from django.core.management.base import BaseCommand
from operations.control_models import RestoreOperation, SessionEpoch


class Command(BaseCommand):
    help = "Show the non-secret recovery control state"

    def handle(self, *args, **options):
        state = SessionEpoch.objects.using("control").filter(singleton=True).first()  # type: ignore[attr-defined]
        latest = RestoreOperation.objects.using("control").order_by("-uuid").first()  # type: ignore[attr-defined]
        self.stdout.write({
            "maintenance": bool(state and state.maintenance),
            "epoch": int(state.epoch) if state else None,
            "status": "ready" if state else "not_ready",
            "phase": latest.phase if latest else None,
            "operation_id": str(latest.uuid) if latest else None,
        }.__repr__())
