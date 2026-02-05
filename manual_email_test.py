#!/usr/bin/env python
"""Manually trigger email sending for latest form"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.presentations.models import Form as PresentationForm
from apps.users.models import CustomUser
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 60)
print("MANUALLY SENDING EMAIL FOR FORM UPDATE")
print("=" * 60)

# Get the most recent form
form = PresentationForm.objects.filter(form_role='student').order_by('-created_at').first()
if not form:
    print("❌ No forms found")
    sys.exit(1)

print(f"\n✓ Form ID: {form.id}")

data = form.data or {}
sel = data.get('selected_supervisor')
print(f"  Selected supervisor: {sel}")

if not sel:
    print("❌ No supervisor selected")
    sys.exit(1)

try:
    sup = CustomUser.objects.get(id=int(sel))
    print(f"\n✓ Supervisor: {sup.get_full_name()}")
    print(f"  Email: {sup.email}")
    
    student_name = data.get('student_full_name', form.created_by.get_full_name())
    project_title = data.get('research_title', 'Research Progress Report')
    
    print(f"\n  Student: {student_name}")
    print(f"  Project: {project_title}")
    
    title = f'Action Required: Sign Form for {student_name}'
    message = f'Dear {sup.get_full_name()},\n\n{student_name} has updated and submitted a Research Progress Report for the project "{project_title}".\n\nYou are requested to log in to the system, review the updated report, and complete Part B (Supervisor Section) with your signature.\n\nPlease log in at your earliest convenience to complete this task.\n\nThank you.'
    
    context = {
        'presentation': None,
        'recipient': sup,
        'assigned_by': form.created_by,
        'student_name': student_name,
        'project_title': project_title,
        'role_label': 'Supervisor',
        'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
        'honorific': ''
    }
    
    try:
        html_body = render_to_string('emails/examiner_assignment.html', context)
    except Exception as e:
        print(f"⚠ Could not load HTML template: {e}")
        html_body = None
    
    try:
        text_body = render_to_string('emails/examiner_assignment.txt', context)
    except Exception as e:
        print(f"⚠ Could not load text template: {e}")
        text_body = message
    
    from_email = settings.DEFAULT_FROM_EMAIL
    to_emails = [sup.email]
    
    print(f"\n📧 Attempting to send email...")
    print(f"  From: {from_email}")
    print(f"  To: {to_emails}")
    print(f"  Subject: {title}")
    
    msg = EmailMultiAlternatives(title, text_body, from_email, to_emails)
    if html_body:
        msg.attach_alternative(html_body, 'text/html')
    
    result = msg.send(fail_silently=False)
    
    print(f"\n✅ Email sent successfully!")
    print(f"   Return value: {result}")
    print(f"\n⏳ Please check inbox for: {sup.email}")
    print(f"   Also check SPAM folder if not in inbox")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
