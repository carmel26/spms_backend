# Script to trigger a presentation reminder via Django shell
# Usage (from repo root):
#  cd backend
#  PRESENTATION_ID=11 MINUTES=1 python manage.py shell < backend/scripts/send_test_reminder.py
# If PRESENTATION_ID is not set, the script will pick the latest presentation.

import os

from apps.presentations.models import PresentationRequest
from apps.notifications.utils import send_presentation_time_reminder

pid = os.environ.get('PRESENTATION_ID')
minutes = int(os.environ.get('MINUTES', '1'))

if pid:
    try:
        p = PresentationRequest.objects.get(id=int(pid))
    except PresentationRequest.DoesNotExist:
        print(f"No presentation found with id {pid}")
        p = None
else:
    p = PresentationRequest.objects.order_by('-id').first()

if not p:
    print('No presentation found; exiting.')
else:
    print(f'Sending reminder for presentation id {p.id} (minutes_before={minutes})')
    send_presentation_time_reminder(p, minutes_before=minutes)
    print('Reminder invocation complete.')
