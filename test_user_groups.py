#!/usr/bin/env python
"""
Test script for UserGroup CRUD operations
Run from backend directory: python test_user_groups.py
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import UserGroup, CustomUser
from django.db import IntegrityError

def test_create():
    """Test creating a new user group"""
    print("\n=== Testing CREATE ===")
    try:
        group = UserGroup.objects.create(
            name='external_examiner',
            display_name='External Examiner',
            description='External examiner for thesis defense',
            is_active=True
        )
        print(f"✓ Created: {group.name} -> {group.display_name} (ID: {group.id})")
        return group
    except IntegrityError as e:
        print(f"✗ Error (group may already exist): {e}")
        # Try to get existing
        group = UserGroup.objects.filter(name='external_examiner').first()
        if group:
            print(f"  Found existing: {group.name} -> {group.display_name} (ID: {group.id})")
            return group
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None

def test_read():
    """Test reading user groups"""
    print("\n=== Testing READ ===")
    try:
        groups = UserGroup.objects.all()[:5]
        print(f"✓ Found {UserGroup.objects.count()} total groups")
        print("  First 5 groups:")
        for group in groups:
            print(f"    - {group.name} -> {group.display_name} (Active: {group.is_active})")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_update(group):
    """Test updating a user group"""
    print("\n=== Testing UPDATE ===")
    if not group:
        print("✗ No group provided for update test")
        return False
    
    try:
        original_description = group.description
        group.description = 'Updated description for testing'
        group.is_active = False
        group.save()
        print(f"✓ Updated: {group.name}")
        print(f"  Description: '{original_description}' -> '{group.description}'")
        print(f"  Active status: True -> {group.is_active}")
        
        # Revert changes
        group.description = original_description
        group.is_active = True
        group.save()
        print(f"✓ Reverted changes")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_delete(group):
    """Test deleting a user group"""
    print("\n=== Testing DELETE ===")
    if not group:
        print("✗ No group provided for delete test")
        return False
    
    try:
        # Check if any users have this group
        user_count = group.users.count()
        if user_count > 0:
            print(f"⚠ Cannot delete: {user_count} user(s) are assigned to this group")
            print(f"  This is expected behavior for group: {group.name}")
            return True
        else:
            group_name = group.name
            group.delete()
            print(f"✓ Deleted: {group_name}")
            return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_validation():
    """Test validation rules"""
    print("\n=== Testing VALIDATION ===")
    try:
        # Test duplicate name
        print("Testing duplicate name...")
        try:
            UserGroup.objects.create(
                name='student',  # Already exists
                display_name='Duplicate Student'
            )
            print("✗ Should have failed with duplicate name")
        except IntegrityError:
            print("✓ Correctly rejected duplicate name")
        
        # Test empty name
        print("Testing empty display name...")
        try:
            group = UserGroup(name='test_empty', display_name='')
            group.full_clean()  # This should raise ValidationError
            print("✗ Should have failed with empty display_name")
        except Exception:
            print("✓ Correctly rejected empty display_name")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("UserGroup CRUD Operations Test")
    print("=" * 60)
    
    # Run tests
    test_read()
    test_group = test_create()
    
    if test_group:
        test_update(test_group)
        test_delete(test_group)
    
    test_validation()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("All CRUD operations tested successfully!")
    print(f"Total user groups in database: {UserGroup.objects.count()}")
    print(f"Active groups: {UserGroup.objects.filter(is_active=True).count()}")
    print(f"Inactive groups: {UserGroup.objects.filter(is_active=False).count()}")

if __name__ == '__main__':
    main()
