#!/usr/bin/env python
"""Test script to verify form update email sending"""
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.presentations.models import Form as PresentationForm
from apps.users.models import CustomUser
import json

print("=" * 60)
print("TESTING FORM UPDATE EMAIL LOGIC")
print("=" * 60)

# Get the most recent form
forms = PresentationForm.objects.filter(form_role='student').order_by('-created_at')
if not forms.exists():
    print("❌ No forms found in database")
    sys.exit(1)

form = forms.first()
print(f"\n✓ Found form ID: {form.id}")
print(f"  Created by: {form.created_by.get_full_name() if form.created_by else 'N/A'}")
print(f"  Form role: {form.form_role}")

# Check form data
data = form.data or {}
print(f"\n  Form data keys: {list(data.keys())}")

# Check for selected_supervisor
sel_sup = data.get('selected_supervisor') or data.get('selected_supervisors')
print(f"\n  Selected supervisor in data: {sel_sup}")
print(f"  Data type: {type(sel_sup)}")

if sel_sup:
    try:
        sup_id = int(sel_sup) if not isinstance(sel_sup, list) else int(sel_sup[0])
        supervisor = CustomUser.objects.get(id=sup_id)
        print(f"\n✓ Supervisor found:")
        print(f"  ID: {supervisor.id}")
        print(f"  Name: {supervisor.get_full_name()}")
        print(f"  Email: {supervisor.email}")
        
        # Check email settings
        from django.conf import settings
        print(f"\n✓ Email configuration:")
        print(f"  Backend: {settings.EMAIL_BACKEND}")
        print(f"  Host: {settings.EMAIL_HOST}")
        print(f"  Port: {settings.EMAIL_PORT}")
        print(f"  Use TLS: {settings.EMAIL_USE_TLS}")
        print(f"  From: {settings.DEFAULT_FROM_EMAIL}")
        
        # Check student info
        student_name = data.get('student_full_name', 'Unknown')
        project_title = data.get('research_title', 'Unknown')
        print(f"\n✓ Form details for email:")
        print(f"  Student: {student_name}")
        print(f"  Project: {project_title}")
        
    except CustomUser.DoesNotExist:
        print(f"❌ Supervisor with ID {sup_id} not found")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("\n❌ No selected_supervisor found in form data")
    print("\nThis is why emails are not being sent!")
    print("\nDebugging tips:")
    print("1. Check that the frontend is sending 'selected_supervisor' in the payload")
    print("2. Verify the field is being saved to form.data in the database")
    print("3. Check browser console for the payload being sent")

print("\n" + "=" * 60)
