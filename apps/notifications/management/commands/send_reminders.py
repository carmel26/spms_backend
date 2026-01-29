from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.presentations.models import PresentationSchedule
from apps.notifications.utils import send_presentation_time_reminder


class Command(BaseCommand):
    help = 'Scan upcoming presentations and send reminders (default: 15 minutes)'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=15, help='Minutes before start to send reminders')

    def handle(self, *args, **options):
        minutes = options.get('minutes', 15)
        now = timezone.now()
        start_min = now + timezone.timedelta(minutes=minutes)
        end_min = start_min + timezone.timedelta(seconds=59)

        schedules = PresentationSchedule.objects.filter(start_time__gte=start_min, start_time__lt=end_min)
        total = 0
        for sched in schedules:
            send_presentation_time_reminder(sched.presentation, minutes_before=minutes)
            total += 1

        self.stdout.write(self.style.SUCCESS(f'Sent reminders for {total} presentation(s) (minutes_before={minutes})'))
