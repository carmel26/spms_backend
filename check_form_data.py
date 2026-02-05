#!/usr/bin/env python
"""Check form data to see if selected_supervisor is present"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.presentations.models import Form as PresentationForm

# Get form ID 16
form_id = 16
try:
    form = PresentationForm.objects.get(id=form_id)
    print("="*60)
    print(f"Form ID: {form.id}")
    print(f"Created by: {form.created_by.get_full_name()}")
    print(f"Form role: {form.form_role}")
    print("="*60)
    print("\nDATA OBJECT:")
    data = form.data or {}
    print(f"Type: {type(data)}")
    print(f"Keys: {list(data.keys())}")
    print("\n")
    
    # Check for selected_supervisor
    sel = data.get('selected_supervisor')
    print(f"selected_supervisor value: {sel}")
    print(f"Type: {type(sel)}")
    
    # Check alternative keys
    sel2 = data.get('selected_supervisors')
    print(f"selected_supervisors value: {sel2}")
    
    # Print full data object
    print("\n" + "="*60)
    print("FULL DATA OBJECT:")
    print("="*60)
    import json
    print(json.dumps(data, indent=2, default=str))
    
    # Check if supervisor exists
    if sel:
        from apps.users.models import CustomUser
        try:
            sup = CustomUser.objects.get(id=int(sel))
            print(f"\n✓ Supervisor found: {sup.get_full_name()} ({sup.email})")
        except Exception as e:
            print(f"\n✗ Supervisor NOT found: {e}")
    else:
        print(f"\n⚠️ No supervisor selected in form data")
        
except PresentationForm.DoesNotExist:
    print(f"Form {form_id} not found")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
