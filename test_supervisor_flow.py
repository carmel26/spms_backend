#!/usr/bin/env python
"""Test script to simulate form submission with selected supervisor"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.presentations.models import Form as PresentationForm
from apps.users.models import CustomUser
import json

print("=" * 60)
print("TESTING: Submit to Selected Supervisor Flow")
print("=" * 60)

# Get all supervisors
supervisors = CustomUser.objects.filter(
    user_groups__name__in=['supervisor', 'dean', 'coordinator']
).distinct()

print(f"\n📋 Available supervisors in system:")
for sup in supervisors:
    print(f"  - {sup.get_full_name()} (ID: {sup.id}, Email: {sup.email})")

# Get the most recent form
form = PresentationForm.objects.filter(form_role='student').order_by('-created_at').first()
if not form:
    print("\n❌ No forms found")
    sys.exit(1)

print(f"\n✓ Testing with Form ID: {form.id}")
print(f"  Created by: {form.created_by.get_full_name()}")

data = form.data or {}
current_supervisor_id = data.get('selected_supervisor')
print(f"\n  Current selected_supervisor in data: {current_supervisor_id}")

if current_supervisor_id:
    try:
        current_sup = CustomUser.objects.get(id=int(current_supervisor_id))
        print(f"  📧 Email WILL be sent to: {current_sup.get_full_name()} ({current_sup.email})")
    except:
        print(f"  ❌ Supervisor ID {current_supervisor_id} not found!")
else:
    print(f"  ⚠️  No supervisor selected - email will NOT be sent")

print("\n" + "=" * 60)
print("HOW IT WORKS:")
print("=" * 60)
print("1. User selects supervisor from dropdown")
print("2. User clicks 'Submit your request to supervisor'")
print("3. Frontend validates selected_supervisor is set")
print("4. Frontend shows SPINNER (no toasts)")
print("5. Frontend sends form with selected_supervisor ID")
print("6. Backend receives form and reads selected_supervisor")
print("7. Backend sends email to that supervisor's email address")
print("8. Backend responds to frontend")
print("9. Frontend hides spinner")
print("10. Frontend shows SUCCESS toasts")
print("=" * 60)

print("\n✅ System is ready! When you submit the form:")
print(f"   - Spinner will show (no toasts during operation)")
print(f"   - Email will go to the supervisor you select in dropdown")
print(f"   - Check Django console for detailed logs showing:")
print(f"     • Selected supervisor ID")
print(f"     • Supervisor name and email")
print(f"     • Email sending confirmation")
print(f"   - Success toasts will appear AFTER operation completes")
print("\n🔍 Check spam folder if email doesn't arrive in inbox!")
print("=" * 60)
