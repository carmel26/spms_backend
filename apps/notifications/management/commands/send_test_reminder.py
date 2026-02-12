from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.presentations.models import PresentationRequest, PresentationSchedule
from apps.notifications.utils import send_presentation_reminders_to_all_actors


class Command(BaseCommand):
    help = 'Send a reminder for a specific presentation id (or latest) to ALL actors'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=str, dest='presentation_id', help='PresentationRequest id to target')
        parser.add_argument('--minutes', type=int, default=1, help='Minutes before start to send reminder')

    def handle(self, *args, **options):
        pid = options.get('presentation_id')
        minutes = options.get('minutes', 1)

        if pid:
            try:
                p = PresentationRequest.objects.get(id=pid)
            except PresentationRequest.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Presentation with id {pid} not found'))
                return
        else:
            p = PresentationRequest.objects.order_by('-created_at').first()
            if not p:
                self.stderr.write(self.style.ERROR('No presentations found'))
                return

        # Optionally, verify there's a schedule matching the minutes window
        now = timezone.now()
        start_min = now + timezone.timedelta(minutes=minutes)
        end_min = start_min + timezone.timedelta(seconds=59)

        has_schedule = PresentationSchedule.objects.filter(presentation=p, start_time__gte=start_min, start_time__lt=end_min).exists()
        if not has_schedule:
            self.stdout.write(self.style.WARNING(f'Presentation {p.id} does not have a schedule within the {minutes}-minute window; sending reminder anyway.'))

        send_presentation_reminders_to_all_actors(p, minutes_before=minutes)
        self.stdout.write(self.style.SUCCESS(f'Reminder invoked for presentation id {p.id} to ALL actors (minutes_before={minutes})'))

