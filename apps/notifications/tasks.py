import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import ReminderLog
from apps.presentations.models import PresentationRequest, PresentationSchedule
from .utils import send_presentation_reminders_to_all_actors

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def send_upcoming_reminders(self, minutes_before=30):
    """
    Celery beat task — runs every 60 s.
    Finds presentations starting in *minutes_before* minutes (±59 s window)
    using **both** PresentationSchedule.start_time and
    PresentationRequest.actual_date so reminders fire regardless of which
    date field is populated.

    Skips presentations that already received a reminder for this window
    (checked via ReminderLog).
    """
    now = timezone.now()
    window_start = now + timezone.timedelta(minutes=minutes_before)
    window_end = window_start + timezone.timedelta(seconds=59)

    # ---------- collect presentation ids from both schedule & actual_date ----------
    schedule_pr_ids = list(
        PresentationSchedule.objects
        .filter(start_time__gte=window_start, start_time__lt=window_end)
        .values_list('presentation_id', flat=True)
    )

    actual_date_pr_ids = list(
        PresentationRequest.objects
        .filter(actual_date__gte=window_start, actual_date__lt=window_end)
        .values_list('id', flat=True)
    )

    all_pr_ids = set(schedule_pr_ids) | set(actual_date_pr_ids)

    if not all_pr_ids:
        return f'No presentations in the {minutes_before}-min window'

    # ---------- skip already-reminded presentations ----------
    already_reminded = set(
        ReminderLog.objects
        .filter(
            presentation_id__in=all_pr_ids,
            minutes_before=minutes_before,
            status='sent',
        )
        .values_list('presentation_id', flat=True)
    )
    pending_ids = all_pr_ids - already_reminded

    total = 0
    for pr in PresentationRequest.objects.filter(id__in=pending_ids).select_related('student'):
        try:
            send_presentation_reminders_to_all_actors(pr, minutes_before=minutes_before)
            total += 1
        except Exception:
            logger.exception('Failed to send reminders for presentation id %s', pr.id)
            continue

    return f'Sent reminders for {total} presentation(s) (minutes_before={minutes_before})'
