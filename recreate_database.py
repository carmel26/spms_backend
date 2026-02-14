#!/usr/bin/env python3
"""
Database Recreation Script for SPMS
This script completely recreates the database with fresh UUID-based schema
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(message, color):
    """Print colored message to terminal"""
    print(f"{color}{message}{Colors.NC}")

def print_header(message):
    """Print a header message"""
    print("\n" + "=" * 60)
    print_colored(message, Colors.BLUE)
    print("=" * 60 + "\n")

def run_command(command, description, check=True):
    """Run a shell command and print the result"""
    print_colored(f"⚙️  {description}...", Colors.YELLOW)
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_colored(f"✓ {description} completed", Colors.GREEN)
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print_colored(f"✗ {description} failed", Colors.RED)
            if result.stderr:
                print(result.stderr)
            return False
    except subprocess.CalledProcessError as e:
        print_colored(f"✗ {description} failed: {e}", Colors.RED)
        return False

def backup_database():
    """Backup existing database if it exists"""
    db_file = Path("db.sqlite3")
    if db_file.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"db.sqlite3.backup.{timestamp}"
        print_colored(f"📦 Backing up existing database to {backup_name}...", Colors.YELLOW)
        shutil.copy2(db_file, backup_name)
        print_colored(f"✓ Backup created: {backup_name}", Colors.GREEN)
        return backup_name
    else:
        print_colored("ℹ️  No existing database found, skipping backup", Colors.BLUE)
        return None

def remove_database():
    """Remove existing database files"""
    print_colored("🗑️  Removing existing database files...", Colors.YELLOW)
    db_files = ["db.sqlite3", "db.sqlite3-shm", "db.sqlite3-wal"]
    removed = []
    for db_file in db_files:
        if Path(db_file).exists():
            os.remove(db_file)
            removed.append(db_file)
    
    if removed:
        print_colored(f"✓ Removed: {', '.join(removed)}", Colors.GREEN)
    else:
        print_colored("ℹ️  No database files to remove", Colors.BLUE)

def clean_cache():
    """Remove Python cache files"""
    print_colored("🧹 Cleaning Python cache files...", Colors.YELLOW)
    
    # Remove __pycache__ directories
    for pycache_dir in Path(".").rglob("__pycache__"):
        shutil.rmtree(pycache_dir, ignore_errors=True)
    
    # Remove .pyc files
    for pyc_file in Path(".").rglob("*.pyc"):
        pyc_file.unlink(missing_ok=True)
    
    print_colored("✓ Cache cleaned", Colors.GREEN)

def verify_venv():
    """Check if we're in a virtual environment"""
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_colored("⚠️  Warning: Not running in a virtual environment!", Colors.YELLOW)
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print_colored("❌ Aborted by user", Colors.RED)
            sys.exit(1)
    else:
        print_colored("✓ Virtual environment detected", Colors.GREEN)

def main():
    """Main execution function"""
    print_header("SPMS Database Recreation Script")
    
    # Change to script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}\n")
    
    # Verify virtual environment
    verify_venv()
    
    # Backup existing database
    backup_name = backup_database()
    
    # Confirm action
    print_colored("\n⚠️  WARNING: This will PERMANENTLY delete the current database!", Colors.YELLOW)
    print_colored("All data will be lost unless you have a backup.", Colors.YELLOW)
    
    if backup_name:
        print_colored(f"Backup created: {backup_name}", Colors.BLUE)
    
    response = input("\nContinue with database recreation? (yes/NO): ")
    if response.lower() != 'yes':
        print_colored("❌ Operation cancelled by user", Colors.YELLOW)
        sys.exit(0)
    
    print_header("Starting Database Recreation")
    
    # Remove database
    remove_database()
    
    # Clean cache
    clean_cache()
    
    # Run migrations
    print_header("Running Database Migrations")
    if not run_command("python manage.py migrate --run-syncdb", "Creating database schema"):
        print_colored("\n❌ Migration failed! Database may be in inconsistent state.", Colors.RED)
        sys.exit(1)
    
    # Create superuser (optional)
    print_header("Create Superuser (Optional)")
    print_colored("You can create a superuser now or skip this step.", Colors.BLUE)
    print("To skip, press Ctrl+C or type 'skip' when prompted.\n")
    
    try:
        run_command("python manage.py createsuperuser", "Creating superuser", check=False)
    except KeyboardInterrupt:
        print_colored("\n⏭️  Superuser creation skipped", Colors.YELLOW)
    
    # Success message
    print_header("Database Recreation Completed Successfully! ✅")
    
    print("\n📋 Next Steps:")
    print("  1. Run development server: python manage.py runserver")
    print("  2. Or run setup admin script: python setup_admin.py")
    print("  3. Or restore data from backup if needed")
    
    if backup_name:
        print(f"\n💾 Database backup: {backup_name}")
        print("   To restore: cp {backup_name} db.sqlite3")
    
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n❌ Operation cancelled by user", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n❌ Unexpected error: {e}", Colors.RED)
        sys.exit(1)
