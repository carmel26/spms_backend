from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.presentations.models import PresentationRequest, PresentationSchedule
from apps.notifications.utils import send_presentation_reminders_to_all_actors


class Command(BaseCommand):
    help = 'Scan upcoming presentations and send reminders to ALL actors (default: 15 minutes)'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=15, help='Minutes before start to send reminders')

    def handle(self, *args, **options):
        minutes = options.get('minutes', 15)
        now = timezone.now()
        window_start = now + timezone.timedelta(minutes=minutes)
        window_end = window_start + timezone.timedelta(seconds=59)

        # Collect from schedule
        schedule_pr_ids = list(
            PresentationSchedule.objects
            .filter(start_time__gte=window_start, start_time__lt=window_end)
            .values_list('presentation_id', flat=True)
        )
        # Collect from actual_date
        actual_pr_ids = list(
            PresentationRequest.objects
            .filter(actual_date__gte=window_start, actual_date__lt=window_end)
            .values_list('id', flat=True)
        )
        all_ids = set(schedule_pr_ids) | set(actual_pr_ids)

        total = 0
        for pr in PresentationRequest.objects.filter(id__in=all_ids).select_related('student'):
            send_presentation_reminders_to_all_actors(pr, minutes_before=minutes)
            total += 1

        self.stdout.write(self.style.SUCCESS(f'Sent reminders for {total} presentation(s) (minutes_before={minutes})'))
