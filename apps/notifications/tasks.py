from celery import shared_task
from django.utils import timezone

from apps.presentations.models import PresentationSchedule
from .utils import send_presentation_time_reminder


@shared_task(bind=True)
def send_upcoming_reminders(self, minutes_before=15):
    """Celery task to find presentations starting in `minutes_before` minutes and send reminders."""
    now = timezone.now()
    start_min = now + timezone.timedelta(minutes=minutes_before)
    end_min = start_min + timezone.timedelta(seconds=59)

    schedules = PresentationSchedule.objects.filter(start_time__gte=start_min, start_time__lt=end_min)
    for sched in schedules:
        try:
            send_presentation_time_reminder(sched.presentation, minutes_before=minutes_before)
        except Exception:
            # Task should not fail entirely for single errors
            continue
