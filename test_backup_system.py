#!/usr/bin/env python
"""
Backup System Diagnostic Script for PythonAnywhere

Run this script to diagnose backup issues:
    python test_backup_system.py
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add Django project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.management import call_command
from django.db import connection
from apps.users.models import CustomUser

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")

def check_database_connection():
    """Test database connectivity"""
    print_section("1. DATABASE CONNECTION")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_name = connection.settings_dict['NAME']
            db_engine = connection.settings_dict['ENGINE']
            print(f"✅ Database connected: {db_name}")
            print(f"   Engine: {db_engine}")
            
            # Get table count
            if 'mysql' in db_engine:
                cursor.execute("SHOW TABLES")
            elif 'postgresql' in db_engine:
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            elif 'sqlite' in db_engine:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            
            tables = cursor.fetchall()
            print(f"   Tables: {len(tables)}")
            
            # Get user count
            user_count = CustomUser.objects.count()
            print(f"   Users: {user_count}")
            
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_backup_directory():
    """Check if backup directory exists and is writable"""
    print_section("2. BACKUP DIRECTORY")
    backup_dir = BASE_DIR / 'backups'
    
    print(f"   Path: {backup_dir}")
    
    if not backup_dir.exists():
        print(f"⚠️  Directory does not exist, creating...")
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created backup directory")
        except Exception as e:
            print(f"❌ Failed to create directory: {e}")
            return False
    else:
        print(f"✅ Directory exists")
    
    # Check permissions
    if os.access(backup_dir, os.W_OK):
        print(f"✅ Directory is writable")
    else:
        print(f"❌ Directory is not writable")
        return False
    
    # List existing backups
    backups = list(backup_dir.glob('spms-*.*'))
    print(f"   Existing backups: {len(backups)}")
    if backups:
        print(f"   Latest: {backups[-1].name}")
    
    return True

def check_commands():
    """Check availability of database dump commands"""
    print_section("3. DATABASE DUMP COMMANDS")
    
    import shutil
    commands = ['mysqldump', 'pg_dump', 'sqlite3']
    found = []
    
    for cmd in commands:
        path = shutil.which(cmd)
        if path:
            print(f"✅ {cmd}: {path}")
            found.append(cmd)
        else:
            print(f"⚠️  {cmd}: Not found in PATH")
            
            # Check common paths
            common_paths = [
                f'/usr/bin/{cmd}',
                f'/usr/local/bin/{cmd}',
                f'/usr/local/mysql/bin/{cmd}',
                f'/opt/homebrew/bin/{cmd}',
            ]
            for common_path in common_paths:
                if os.path.exists(common_path):
                    print(f"   Found at: {common_path}")
                    found.append(cmd)
                    break
    
    if not found:
        print(f"\n⚠️  No database dump commands found")
        print(f"   Will use Django dumpdata (JSON format)")
    
    return True

def test_django_dumpdata():
    """Test Django's dumpdata command"""
    print_section("4. DJANGO DUMPDATA TEST")
    
    backup_dir = BASE_DIR / 'backups'
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    test_file = backup_dir / f'test-{timestamp}.json'
    
    print(f"Creating test backup: {test_file.name}")
    
    try:
        # Create backup using dumpdata
        with open(test_file, 'w') as f:
            call_command(
                'dumpdata',
                '--natural-foreign',
                '--natural-primary',
                '--indent', '2',
                stdout=f,
                exclude=['contenttypes', 'auth.permission']
            )
        
        # Check file
        if test_file.exists():
            size = test_file.stat().st_size
            print(f"✅ Backup created successfully")
            print(f"   Size: {size:,} bytes ({size / 1024:.2f} KB)")
            
            # Parse JSON to verify
            with open(test_file, 'r') as f:
                data = json.load(f)
                print(f"   Records: {len(data)}")
                
                # Count by model
                models = {}
                for obj in data:
                    model = obj['model']
                    models[model] = models.get(model, 0) + 1
                
                print(f"   Models exported:")
                for model, count in sorted(models.items()):
                    print(f"      - {model}: {count}")
            
            return True, test_file
        else:
            print(f"❌ File was not created")
            return False, None
            
    except Exception as e:
        print(f"❌ Dumpdata failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_backup_restoration(backup_file):
    """Test if backup can be loaded (dry run)"""
    print_section("5. BACKUP RESTORATION TEST (DRY RUN)")
    
    if not backup_file or not backup_file.exists():
        print(f"⚠️  No backup file to test")
        return False
    
    try:
        # Just validate JSON, don't actually load
        with open(backup_file, 'r') as f:
            data = json.load(f)
        
        print(f"✅ Backup file is valid JSON")
        print(f"   Can be restored with: python manage.py loaddata {backup_file.name}")
        return True
        
    except Exception as e:
        print(f"❌ Backup file is invalid: {e}")
        return False

def cleanup_test_files():
    """Remove test backup files"""
    print_section("6. CLEANUP")
    
    backup_dir = BASE_DIR / 'backups'
    test_files = list(backup_dir.glob('test-*.*'))
    
    if test_files:
        print(f"Found {len(test_files)} test files")
        for test_file in test_files:
            try:
                test_file.unlink()
                print(f"   Deleted: {test_file.name}")
            except Exception as e:
                print(f"   Failed to delete {test_file.name}: {e}")
    else:
        print(f"No test files to clean up")

def main():
    """Run all diagnostic tests"""
    print("\n" + "=" * 60)
    print("  SPMS BACKUP SYSTEM DIAGNOSTICS")
    print("=" * 60)
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Platform: {sys.platform}")
    print(f"  Python: {sys.version.split()[0]}")
    print("=" * 60)
    
    results = {
        'database': False,
        'directory': False,
        'commands': False,
        'dumpdata': False,
        'restoration': False
    }
    
    # Run tests
    results['database'] = check_database_connection()
    results['directory'] = check_backup_directory()
    results['commands'] = check_commands()
    results['dumpdata'], backup_file = test_django_dumpdata()
    if backup_file:
        results['restoration'] = test_backup_restoration(backup_file)
    
    # Summary
    print_section("SUMMARY")
    all_passed = all(results.values())
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test.replace('_', ' ').title()}")
    
    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("Your backup system is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("Review the output above to identify issues.")
    
    # Cleanup
    if results['dumpdata']:
        cleanup_test_files()
    
    print("\n" + "=" * 60 + "\n")

if __name__ == '__main__':
    main()
