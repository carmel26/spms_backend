#!/usr/bin/env python3
"""
Script to create/update admin user with all proper roles in the multi-role system
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.users.models import UserGroup

User = get_user_model()

def create_user_groups():
    """Create all necessary user groups"""
    print("\n📋 Creating User Groups...")
    
    groups_data = [
        {'name': 'admin', 'display_name': 'Admin', 'description': 'System Administrator'},
        {'name': 'student', 'display_name': 'Student', 'description': 'Student User'},
        {'name': 'supervisor', 'display_name': 'Supervisor', 'description': 'Thesis Supervisor'},
        {'name': 'examiner', 'display_name': 'Examiner', 'description': 'Thesis Examiner'},
        {'name': 'coordinator', 'display_name': 'Coordinator', 'description': 'Programme Coordinator'},
        {'name': 'dean', 'display_name': 'Dean', 'description': 'School Dean'},
        {'name': 'admission', 'display_name': 'Admission', 'description': 'Admission Officer'},
        {'name': 'moderator', 'display_name': 'Moderator', 'description': 'Content Moderator'},
        {'name': 'qa', 'display_name': 'QA Officer', 'description': 'Quality Assurance Officer'},
        {'name': 'auditor', 'display_name': 'Auditor', 'description': 'System Auditor'},
    ]
    
    created_groups = {}
    for group_data in groups_data:
        group, created = UserGroup.objects.get_or_create(
            name=group_data['name'],
            defaults={
                'display_name': group_data['display_name'],
                'description': group_data['description'],
                'is_active': True
            }
        )
        created_groups[group.name] = group
        status = "✅ Created" if created else "ℹ️  Exists"
        print(f"{status}: {group.display_name} ({group.name})")
    
    return created_groups

def create_admin_user(groups):
    """Create or update admin user with all proper roles"""
    print("\n👤 Setting up Admin User...")
    
    admin_data = {
        'username': 'admin',
        'email': 'admin@spms.edu',
        'first_name': 'System',
        'last_name': 'Administrator',
        'title': 'mr',
    }
    
    # Check if admin exists
    try:
        admin = User.objects.get(username=admin_data['username'])
        print(f"ℹ️  Admin user already exists: {admin.username}")
        
        # Update admin details
        admin.first_name = admin_data['first_name']
        admin.last_name = admin_data['last_name']
        admin.email = admin_data['email']
        admin.title = admin_data['title']
        admin.is_superuser = True
        admin.is_staff = True
        admin.is_active = True
        admin.is_approved = True
        admin.save()
        print("✅ Admin user updated")
        
    except User.DoesNotExist:
        # Create new admin
        admin = User.objects.create_superuser(
            username=admin_data['username'],
            email=admin_data['email'],
            password='admin123',  # Default password
            first_name=admin_data['first_name'],
            last_name=admin_data['last_name'],
        )
        admin.title = admin_data['title']
        admin.is_approved = True
        admin.save()
        print("✅ Admin user created")
        print("📧 Username: admin")
        print("🔑 Password: admin123")
        print("⚠️  Please change password after first login!")
    
    # Assign admin role via user_groups
    admin_group = groups.get('admin')
    if admin_group:
        if admin_group not in admin.user_groups.all():
            admin.user_groups.add(admin_group)
            print("✅ Admin role assigned to user_groups")
        else:
            print("ℹ️  Admin already has admin role in user_groups")
    
    return admin

def setup_test_users(groups):
    """Create test users for different roles"""
    print("\n👥 Setting up Test Users...")
    
    test_users = [
        {
            'username': 'supervisor1',
            'email': 'supervisor1@spms.edu',
            'first_name': 'Dr. Jane',
            'last_name': 'Smith',
            'title': 'dr',
            'password': 'supervisor123',
            'groups': ['supervisor']
        },
        {
            'username': 'examiner1',
            'email': 'examiner1@spms.edu',
            'first_name': 'Prof. John',
            'last_name': 'Doe',
            'title': 'prof',
            'password': 'examiner123',
            'groups': ['examiner']
        },
        {
            'username': 'student1',
            'email': 'student1@spms.edu',
            'first_name': 'Alice',
            'last_name': 'Johnson',
            'password': 'student123',
            'groups': ['student']
        },
    ]
    
    for user_data in test_users:
        try:
            user = User.objects.get(username=user_data['username'])
            print(f"ℹ️  User exists: {user.username}")
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
            )
            user.title = user_data.get('title', '')
            user.is_approved = True
            user.is_active = True
            user.save()
            print(f"✅ Created: {user.username}")
        
        # Assign groups
        for group_name in user_data['groups']:
            group = groups.get(group_name)
            if group and group not in user.user_groups.all():
                user.user_groups.add(group)
                print(f"   ✅ Assigned role: {group.display_name}")

def verify_admin_setup():
    """Verify admin is properly configured"""
    print("\n🔍 Verifying Admin Configuration...")
    
    try:
        admin = User.objects.get(username='admin')
        print(f"✅ Admin user found: {admin.get_full_name()}")
        print(f"   • Email: {admin.email}")
        print(f"   • Is Superuser: {admin.is_superuser}")
        print(f"   • Is Staff: {admin.is_staff}")
        print(f"   • Is Active: {admin.is_active}")
        print(f"   • Is Approved: {admin.is_approved}")
        
        # Check roles
        all_roles = admin.get_all_roles()
        print(f"   • Roles: {', '.join(all_roles) if all_roles else 'None'}")
        
        # Check helper methods
        print(f"   • is_admin(): {admin.is_admin()}")
        print(f"   • has_role('admin'): {admin.has_role('admin')}")
        
        if not all_roles or 'admin' not in all_roles:
            print("\n⚠️  WARNING: Admin user does not have 'admin' role in user_groups!")
            print("   This may cause issues with menu access.")
            return False
        
        return True
        
    except User.DoesNotExist:
        print("❌ Admin user not found!")
        return False

def main():
    """Main setup function"""
    print("=" * 60)
    print("🚀 SPMS Admin Setup - Multi-Role System")
    print("=" * 60)
    
    try:
        # Step 1: Create user groups
        groups = create_user_groups()
        
        # Step 2: Create/update admin user
        admin = create_admin_user(groups)
        
        # Step 3: Create test users (optional)
        response = input("\n❓ Do you want to create test users? (y/n): ").lower()
        if response == 'y':
            setup_test_users(groups)
        
        # Step 4: Verify setup
        if verify_admin_setup():
            print("\n" + "=" * 60)
            print("✅ Setup completed successfully!")
            print("=" * 60)
            print("\n📝 Login Credentials:")
            print("   Username: admin")
            print("   Password: admin123")
            print("\n⚠️  Remember to change the password after first login!")
            print("\n🌐 Access the system at: http://localhost:4200")
            print("=" * 60)
        else:
            print("\n⚠️  Setup completed with warnings. Please check the admin configuration.")
            
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
