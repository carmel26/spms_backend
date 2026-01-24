#!/usr/bin/env python
"""
Script to test and populate audit logs for testing
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import AuditLog, CustomUser
from django.utils import timezone
from datetime import timedelta

def check_audit_logs():
    """Check if there are any audit logs"""
    count = AuditLog.objects.count()
    print(f"✓ Total audit logs in database: {count}")
    
    if count > 0:
        print("\n✓ Recent audit logs:")
        for log in AuditLog.objects.all().order_by('-timestamp')[:5]:
            print(f"  - #{log.id}: {log.action} on {log.model_name} by {log.user_display} at {log.timestamp}")
    else:
        print("\n⚠ No audit logs found!")
    
    return count

def create_sample_audit_logs():
    """Create sample audit logs for testing"""
    print("\n📝 Creating sample audit logs...")
    
    # Get a user (preferably admin)
    try:
        user = CustomUser.objects.filter(is_superuser=True).first()
        if not user:
            user = CustomUser.objects.first()
        
        if not user:
            print("❌ No users found! Please create a user first.")
            return
        
        # Create various sample logs
        sample_logs = [
            {
                'action': 'VIEW',
                'model_name': 'PresentationRequest',
                'description': 'Viewed presentation list',
                'success': True
            },
            {
                'action': 'CREATE',
                'model_name': 'PresentationRequest',
                'description': 'Created new presentation request',
                'success': True
            },
            {
                'action': 'UPDATE',
                'model_name': 'PresentationRequest',
                'description': 'Updated presentation status to approved',
                'success': True
            },
            {
                'action': 'DELETE',
                'model_name': 'StudentProfile',
                'description': 'Attempted to delete student profile',
                'success': False,
                'error_message': 'Permission denied'
            },
            {
                'action': 'VIEW',
                'model_name': 'BlockchainRecord',
                'description': 'Viewed blockchain dashboard',
                'success': True
            },
            {
                'action': 'VERIFY',
                'model_name': 'BlockchainRecord',
                'description': 'Verified blockchain integrity',
                'success': True
            },
            {
                'action': 'UPDATE',
                'model_name': 'SystemSettings',
                'description': 'Updated system settings',
                'success': True
            },
            {
                'action': 'VIEW',
                'model_name': 'CustomUser',
                'description': 'Viewed user profile',
                'success': True
            },
            {
                'action': 'LOGIN',
                'model_name': 'CustomUser',
                'description': 'User logged in successfully',
                'success': True
            },
            {
                'action': 'LOGIN',
                'model_name': 'CustomUser',
                'description': 'Failed login attempt',
                'success': False,
                'error_message': 'Invalid credentials'
            }
        ]
        
        created_count = 0
        for i, log_data in enumerate(sample_logs):
            # Create log with different timestamps
            timestamp = timezone.now() - timedelta(hours=i)
            
            AuditLog.objects.create(
                user=user,
                user_role=user.role if hasattr(user, 'role') else 'admin',
                action=log_data['action'],
                model_name=log_data['model_name'],
                object_id=str(100 + i),
                object_repr=f"Sample Object {i}",
                description=log_data['description'],
                changes={},
                ip_address='127.0.0.1',
                user_agent='Test Script',
                request_path=f'/api/test/{i}',
                request_method='GET',
                success=log_data['success'],
                error_message=log_data.get('error_message', ''),
                timestamp=timestamp
            )
            created_count += 1
        
        print(f"✓ Created {created_count} sample audit logs")
        
    except Exception as e:
        print(f"❌ Error creating sample logs: {e}")

def main():
    print("=" * 60)
    print("AUDIT LOG TEST & POPULATION SCRIPT")
    print("=" * 60)
    
    # Check current state
    count = check_audit_logs()
    
    # Ask if user wants to create sample data
    if count == 0:
        print("\n" + "=" * 60)
        create_sample_audit_logs()
        print("\n" + "=" * 60)
        check_audit_logs()
    else:
        response = input("\n✓ Audit logs exist. Create additional sample logs? (y/n): ")
        if response.lower() == 'y':
            create_sample_audit_logs()
            print("\n" + "=" * 60)
            check_audit_logs()
    
    print("\n" + "=" * 60)
    print("✓ Script completed!")
    print("=" * 60)

if __name__ == '__main__':
    main()
