#!/usr/bin/env python3
"""
Script to reset database and setup fresh admin user
WARNING: This will delete ALL data in the database!
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.users.models import UserGroup, StudentProfile, SupervisorProfile, ExaminerProfile, CoordinatorProfile
from apps.presentations.models import PresentationRequest, PresentationType
from apps.schools.models import School, Programme

User = get_user_model()

def confirm_reset():
    """Confirm user wants to reset database"""
    print("\n" + "=" * 60)
    print("⚠️  WARNING: DATABASE RESET")
    print("=" * 60)
    print("\nThis will DELETE ALL DATA including:")
    print("• All users (except superuser)")
    print("• All presentations")
    print("• All student profiles")
    print("• All schools and programmes")
    print("• All user groups")
    print("\n❌ THIS CANNOT BE UNDONE!")
    print("=" * 60)
    
    response = input("\nType 'RESET' to confirm: ")
    return response == 'RESET'

def clear_data():
    """Clear all data from database"""
    print("\n🗑️  Clearing database...")
    
    try:
        # Clear presentations
        count = PresentationRequest.objects.all().delete()[0]
        print(f"✅ Deleted {count} presentation requests")
        
        # Clear profiles
        count = StudentProfile.objects.all().delete()[0]
        print(f"✅ Deleted {count} student profiles")
        
        count = SupervisorProfile.objects.all().delete()[0]
        print(f"✅ Deleted {count} supervisor profiles")
        
        count = ExaminerProfile.objects.all().delete()[0]
        print(f"✅ Deleted {count} examiner profiles")
        
        count = CoordinatorProfile.objects.all().delete()[0]
        print(f"✅ Deleted {count} coordinator profiles")
        
        # Clear non-superuser users
        count = User.objects.filter(is_superuser=False).delete()[0]
        print(f"✅ Deleted {count} regular users")
        
        # Clear superusers user_groups relationships
        for user in User.objects.filter(is_superuser=True):
            user.user_groups.clear()
        
        # Clear user groups
        count = UserGroup.objects.all().delete()[0]
        print(f"✅ Deleted {count} user groups")
        
        # Clear schools and programmes
        count = Programme.objects.all().delete()[0]
        print(f"✅ Deleted {count} programmes")
        
        count = School.objects.all().delete()[0]
        print(f"✅ Deleted {count} schools")
        
        print("\n✅ Database cleared successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error clearing database: {e}")
        import traceback
        traceback.print_exc()
        return False

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
        group = UserGroup.objects.create(
            name=group_data['name'],
            display_name=group_data['display_name'],
            description=group_data['description'],
            is_active=True
        )
        created_groups[group.name] = group
        print(f"✅ Created: {group.display_name} ({group.name})")
    
    return created_groups

def create_admin_user(groups):
    """Create admin user with proper roles"""
    print("\n👤 Creating Admin User...")
    
    # Delete existing admin if exists
    User.objects.filter(username='admin').delete()
    
    # Create new admin
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@spms.edu',
        password='admin123',
        first_name='System',
        last_name='Administrator',
    )
    admin.title = 'mr'
    admin.is_approved = True
    admin.is_active = True
    admin.save()
    
    # Assign admin role via user_groups
    admin_group = groups.get('admin')
    if admin_group:
        admin.user_groups.add(admin_group)
        print("✅ Admin role assigned to user_groups")
    
    print("✅ Admin user created successfully")
    print(f"   • Username: admin")
    print(f"   • Email: admin@spms.edu")
    print(f"   • Password: admin123")
    
    return admin

def create_sample_data(groups):
    """Create sample schools and programmes"""
    print("\n🏫 Creating Sample Data...")
    
    # Create schools
    schools_data = [
        {'name': 'School of Engineering', 'abbreviation': 'SOE'},
        {'name': 'School of Computing', 'abbreviation': 'SOC'},
        {'name': 'School of Business', 'abbreviation': 'SOB'},
    ]
    
    schools = []
    for school_data in schools_data:
        school = School.objects.create(**school_data)
        schools.append(school)
        print(f"✅ Created school: {school.name}")
    
    # Create programmes
    programmes_data = [
        {'school': schools[0], 'name': 'Master of Engineering', 'code': 'MENG', 'programme_type': 'masters'},
        {'school': schools[0], 'name': 'PhD in Engineering', 'code': 'PHDE', 'programme_type': 'phd'},
        {'school': schools[1], 'name': 'Master of Computer Science', 'code': 'MCS', 'programme_type': 'masters'},
        {'school': schools[1], 'name': 'PhD in Computer Science', 'code': 'PHDCS', 'programme_type': 'phd'},
    ]
    
    for prog_data in programmes_data:
        programme = Programme.objects.create(**prog_data)
        print(f"✅ Created programme: {programme.name}")
    
    # Create presentation types
    presentation_types = [
        {'name': 'Proposal Defense', 'programme_type': 'both', 'duration_minutes': 90, 'required_examiners': 2},
        {'name': 'Progress Report', 'programme_type': 'both', 'duration_minutes': 60, 'required_examiners': 1},
        {'name': 'Final Defense', 'programme_type': 'both', 'duration_minutes': 120, 'required_examiners': 3},
    ]
    
    for pt_data in presentation_types:
        PresentationType.objects.create(**pt_data)
        print(f"✅ Created presentation type: {pt_data['name']}")

def verify_setup():
    """Verify the setup"""
    print("\n🔍 Verifying Setup...")
    
    # Check admin user
    admin = User.objects.get(username='admin')
    print(f"✅ Admin user: {admin.get_full_name()}")
    print(f"   • Roles: {', '.join(admin.get_all_roles())}")
    print(f"   • is_admin(): {admin.is_admin()}")
    print(f"   • Is Superuser: {admin.is_superuser}")
    
    # Check groups
    groups_count = UserGroup.objects.count()
    print(f"✅ User groups: {groups_count}")
    
    # Check schools
    schools_count = School.objects.count()
    print(f"✅ Schools: {schools_count}")
    
    # Check programmes
    programmes_count = Programme.objects.count()
    print(f"✅ Programmes: {programmes_count}")

def main():
    """Main reset function"""
    print("=" * 60)
    print("🔄 SPMS Database Reset & Setup")
    print("=" * 60)
    
    # Confirm reset
    if not confirm_reset():
        print("\n❌ Reset cancelled.")
        return
    
    try:
        # Step 1: Clear existing data
        if not clear_data():
            print("\n❌ Failed to clear database. Exiting.")
            return
        
        # Step 2: Create user groups
        groups = create_user_groups()
        
        # Step 3: Create admin user
        admin = create_admin_user(groups)
        
        # Step 4: Create sample data
        response = input("\n❓ Create sample data (schools, programmes)? (y/n): ").lower()
        if response == 'y':
            create_sample_data(groups)
        
        # Step 5: Verify setup
        verify_setup()
        
        print("\n" + "=" * 60)
        print("✅ Database reset and setup completed!")
        print("=" * 60)
        print("\n📝 Admin Login:")
        print("   Username: admin")
        print("   Password: admin123")
        print("\n⚠️  Please change password after first login!")
        print("\n🌐 Access at: http://localhost:4200")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during reset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
