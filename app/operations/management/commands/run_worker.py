from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run one durable background worker iteration"

    def handle(self, *args, **options):
        from operations.jobs import WorkerBusy, run_once
        try:
            job = run_once()
        except WorkerBusy:
            self.stdout.write("worker busy")
            return
        self.stdout.write("worker idle" if job is None else f"claimed {job.uuid}")
