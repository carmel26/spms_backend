#!/usr/bin/env python
"""
Script to check users and assign supervisor/examiner roles
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import CustomUser, UserGroup

def main():
    print("\n=== Checking User Roles ===\n")
    
    # Get or create supervisor and examiner groups
    supervisor_group, created = UserGroup.objects.get_or_create(
        name='supervisor',
        defaults={
            'display_name': 'Supervisor',
            'description': 'Can supervise student presentations'
        }
    )
    if created:
        print(f"Created supervisor group")
    
    examiner_group, created = UserGroup.objects.get_or_create(
        name='examiner',
        defaults={
            'display_name': 'Examiner',
            'description': 'Can examine student presentations'
        }
    )
    if created:
        print(f"Created examiner group")
    
    # Check all active, approved users
    all_users = CustomUser.objects.filter(is_active=True, is_approved=True).exclude(user_groups__name='student')
    
    print(f"\nFound {all_users.count()} active, approved non-student users\n")
    
    for user in all_users:
        roles = user.get_all_roles()
        print(f"User: {user.email}")
        print(f"  Name: {user.get_full_name()}")
        print(f"  Current roles: {roles}")
        
        if not roles or (len(roles) == 1 and 'student' in roles):
            # User has no roles or only student role
            # Ask to assign supervisor or examiner
            response = input(f"  Assign as [S]upervisor, [E]xaminer, [B]oth, or [N]one? ").strip().upper()
            
            if response == 'S':
                user.user_groups.add(supervisor_group)
                print(f"  ✓ Added supervisor role")
            elif response == 'E':
                user.user_groups.add(examiner_group)
                print(f"  ✓ Added examiner role")
            elif response == 'B':
                user.user_groups.add(supervisor_group, examiner_group)
                print(f"  ✓ Added both supervisor and examiner roles")
            else:
                print(f"  - Skipped")
        print()
    
    # Summary
    print("\n=== Summary ===")
    supervisor_count = CustomUser.objects.filter(user_groups__name='supervisor', is_active=True, is_approved=True).distinct().count()
    examiner_count = CustomUser.objects.filter(user_groups__name='examiner', is_active=True, is_approved=True).distinct().count()
    
    print(f"Total Supervisors: {supervisor_count}")
    print(f"Total Examiners: {examiner_count}")
    print()

if __name__ == '__main__':
    main()
