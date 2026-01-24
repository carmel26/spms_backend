"""
Management command to send presentation reminders.
Run this command every 1-5 minutes via cron or task scheduler.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta

from apps.presentations.models import PresentationRequest, PresentationSchedule


class Command(BaseCommand):
    help = 'Send email reminders for presentations (10 and 2 minutes before start)'

    def add_arguments(self, parser):
        parser.add_argument('--presentation-id', type=str, help='Presentation id to target or "last"')
        parser.add_argument('--force', action='store_true', help='Force send for the last presentation if no id provided')

    def handle(self, *args, **options):
        now = timezone.now()
        presentation_id = options.get('presentation_id')
        force_flag = options.get('force')

        # Sanitize FRONTEND_URL and build logo HTML
        frontend = getattr(settings, 'FRONTEND_URL', '') or ''
        if 'http' in frontend and frontend.count('http') > 1:
            idx = frontend.rfind('http')
            frontend = frontend[idx:]
        frontend = frontend.rstrip('/')
        logo_url = f"{frontend}/assets/logo/logo.png" if frontend else ''
        logo_url = 'https://upload.wikimedia.org/wikipedia/en/a/ab/NM-AIST_Logo.png?v=1' 
        logo_img_html = f'<img src="{logo_url}" alt="Logo" style="height:48px;width:auto;border-radius:6px;">' if logo_url else ''

        def build_and_send(presentation, minutes_remaining=None):
            # Ensure assignment exists
            if not hasattr(presentation, 'assignment') or not presentation.assignment:
                self.stdout.write(self.style.WARNING(f'Skipping presentation {getattr(presentation, "id", "?")}: no assignment'))
                return

            assignment = presentation.assignment
            student = presentation.student
            coordinator = assignment.coordinator
            moderator = assignment.session_moderator

            examiners = [ea.examiner for ea in assignment.examiner_assignments.filter(status__in=['assigned', 'accepted'])]
            supervisors = list(presentation.supervisors.all())

            # Prefer PresentationSchedule.start_time when available
            scheduled_dt = None
            try:
                sched = PresentationSchedule.objects.filter(presentation_request=presentation).first()
                if sched and getattr(sched, 'start_time', None):
                    scheduled_dt = sched.start_time
            except Exception:
                sched = None

            if not scheduled_dt:
                scheduled_dt = presentation.scheduled_date

            scheduled_time = scheduled_dt.strftime('%B %d, %Y at %I:%M %p') if scheduled_dt else 'TBA'
            presentation_mode = 'Online' if getattr(assignment, 'meeting_link', None) else 'Physical'
            location = assignment.meeting_link if getattr(assignment, 'meeting_link', None) else (assignment.venue or 'TBA')

            minutes_label = f"{minutes_remaining} Minutes" if minutes_remaining else 'Soon'
            subject = f'Reminder: Presentation Starting in {minutes_label} - {presentation.research_title[:50]}...'

            # HTML message (kept the design intact)
            html_message = f'''
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #0b63c5 0%, #0f3d91 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header i {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        .content {{
            background: #ffffff;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .alert-box {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .alert-box strong {{
            color: #856404;
            font-size: 18px;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .info-table th {{
            background: #f8f9fa;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
        }}
        .info-table td {{
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #0b63c5 0%, #0f3d91 100%);
            color: white !important;
            padding: 16px 40px;
            text-decoration: none;
            border-radius: 8px;
            margin: 25px 0;
            font-weight: 700;
            font-size: 18px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(11, 99, 197, 0.3);
            border: 2px solid #ffffff;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            border-radius: 0 0 8px 8px;
            border: 1px solid #e0e0e0;
            border-top: none;
            font-size: 14px;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    <div class="header" style="display:flex;align-items:center;gap:12px;">
        <div style="display:flex;align-items:center;">
            {logo_img_html}
            <i class="bi bi-alarm" style="font-size:28px;color:rgba(255,255,255,0.9);"></i>
        </div>
        <h1 style="flex:1;text-align:left;margin:0;padding-left:8px;">Presentation Reminder</h1>
    </div>
    
    <div class="content">
        <div class="alert-box">
            <strong><i class="bi bi-exclamation-triangle"></i> Starting in {minutes_label}!</strong>
        </div>
        
        <p>This is a friendly reminder that the following presentation will begin shortly:</p>
        
        <table class="info-table">
            <tr>
                <th>Research Title</th>
                <td>{presentation.research_title}</td>
            </tr>
            <tr>
                <th>Student</th>
                <td>{student.get_full_name()}</td>
            </tr>
            <tr>
                <th>Scheduled Time</th>
                <td>{scheduled_time}</td>
            </tr>
            <tr>
                <th>Presentation Mode</th>
                <td>{presentation_mode}</td>
            </tr>
            <tr>
                <th>{'Meeting Link' if assignment.meeting_link else 'Venue'}</th>
                <td>{'<a href="' + location + '">' + location + '</a>' if assignment.meeting_link else location}</td>
            </tr>
            <tr>
                <th>Coordinator</th>
                <td>{coordinator.get_full_name() if coordinator else 'N/A'}</td>
            </tr>
            <tr>
                <th>Moderator</th>
                <td>{moderator.get_full_name() if moderator else 'N/A'}</td>
            </tr>
            <tr>
                <th>Examiners</th>
                <td>{', '.join([e.get_full_name() for e in examiners]) if examiners else 'N/A'}</td>
            </tr>
            <tr>
                <th>Supervisors</th>
                <td>{', '.join([s.get_full_name() for s in supervisors]) if supervisors else 'N/A'}</td>
            </tr>
        </table>
        
        {'<a href="' + location + '" class="button">Join Meeting Now</a>' if assignment.meeting_link else ''}
        
        <p style="margin-top: 20px;"><strong>Please ensure you are ready to begin at the scheduled time.</strong></p>
    </div>
    
    <div class="footer">
        <p>This is an automated reminder from Secure Progress Management System</p>
        <p>&copy; 2026 Secure Progress Management System. All rights reserved.</p>
    </div>
</body>
</html>
            '''

            # Plain text version
            text_message = f'''
PRESENTATION REMINDER - STARTING IN {minutes_label}!

Research Title: {presentation.research_title}
Student: {student.get_full_name()}
Scheduled Time: {scheduled_time}

Presentation Mode: {presentation_mode}
{'Meeting Link: ' + location if assignment.meeting_link else 'Venue: ' + location}

Coordinator: {coordinator.get_full_name() if coordinator else 'N/A'}
Moderator: {moderator.get_full_name() if moderator else 'N/A'}
Examiners: {', '.join([e.get_full_name() for e in examiners]) if examiners else 'N/A'}
Supervisors: {', '.join([s.get_full_name() for s in supervisors]) if supervisors else 'N/A'}

Please ensure you are ready to begin at the scheduled time.

---
Secure Progress Management System
            '''

            # Collect recipients
            recipients = []
            if student and getattr(student, 'email', None):
                recipients.append(student.email)
            if coordinator and getattr(coordinator, 'email', None):
                recipients.append(coordinator.email)
            if moderator and getattr(moderator, 'email', None):
                recipients.append(moderator.email)
            for examiner in examiners:
                if getattr(examiner, 'email', None):
                    recipients.append(examiner.email)
            for supervisor in supervisors:
                if getattr(supervisor, 'email', None):
                    recipients.append(supervisor.email)

            # Deduplicate
            recipients = list(set(recipients))

            if not recipients:
                self.stdout.write(self.style.WARNING(f'No recipients found for presentation "{presentation.research_title}"'))
                return

            try:
                send_mail(
                    subject=subject,
                    message=text_message,
                    html_message=html_message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None),
                    recipient_list=recipients,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Sent reminder for presentation "{presentation.research_title}" to {len(recipients)} recipients'))
                for i, recipient in enumerate(sorted(recipients), 1):
                    self.stdout.write(f'  {i}. {recipient}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send reminder for presentation "{presentation.research_title}": {str(e)}'))

        # If targeted or forced, handle that first
        if presentation_id or force_flag:
            presentations_to_process = []
            if presentation_id == 'last' or (force_flag and not presentation_id):
                last_req = PresentationRequest.objects.order_by('-scheduled_date').first()
                if last_req:
                    presentations_to_process = [last_req]
            else:
                try:
                    pid = int(presentation_id)
                    pr = PresentationRequest.objects.filter(id=pid).first()
                    if pr:
                        presentations_to_process = [pr]
                except Exception:
                    self.stderr.write(self.style.ERROR(f'Invalid presentation id: {presentation_id}'))
                    return

            for presentation in presentations_to_process:
                build_and_send(presentation, minutes_remaining=None)
            return

        # Scheduled run: check both 10- and 2-minute windows (±1 minute)
        windows = [10, 2]
        tol = timedelta(minutes=1)
        processed = set()
        for minutes in windows:
            start = now + timedelta(minutes=minutes) - tol
            end = now + timedelta(minutes=minutes) + tol

            schedules = PresentationSchedule.objects.filter(start_time__gte=start, start_time__lte=end)
            presentations = [s.presentation_request for s in schedules if getattr(s, 'presentation_request', None)]

            requests = PresentationRequest.objects.filter(scheduled_date__gte=start, scheduled_date__lte=end)
            for r in requests:
                if any((getattr(s, 'presentation_request', None) and getattr(s, 'presentation_request').id == r.id) for s in schedules):
                    continue
                presentations.append(r)

            if not presentations:
                self.stdout.write(self.style.SUCCESS(f'No presentations found for the {minutes}-minute window'))
                continue

            for presentation in presentations:
                if not presentation or presentation.id in processed:
                    continue
                build_and_send(presentation, minutes_remaining=minutes)
                processed.add(presentation.id)

        self.stdout.write(self.style.SUCCESS('Finished reminder run'))