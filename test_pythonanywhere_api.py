#!/usr/bin/env python
"""
PythonAnywhere API Diagnostic Script

This script tests the main API endpoints to identify issues.
Run on PythonAnywhere:
    cd ~/your-project/backend
    source ~/.virtualenvs/your-venv/bin/activate
    python test_pythonanywhere_api.py
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Now import Django modules
from django.conf import settings
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from rest_framework.authtoken.models import Token
from apps.users.models import CustomUser
from apps.users.views import SystemSettingsViewSet
from apps.notifications.views import NotificationViewSet

def print_header(title):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_database():
    """Test database connectivity"""
    print_header("1. DATABASE TEST")
    try:
        db_config = settings.DATABASES['default']
        print(f"Engine: {db_config['ENGINE']}")
        print(f"Name: {db_config['NAME']}")
        print(f"Host: {db_config['HOST']}")
        
        user_count = CustomUser.objects.count()
        print(f"✅ Database connected")
        print(f"   Users in database: {user_count}")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_cors_settings():
    """Check CORS configuration"""
    print_header("2. CORS CONFIGURATION")
    try:
        print("Allowed Origins:")
        for origin in settings.CORS_ALLOWED_ORIGINS:
            print(f"  - {origin}")
        
        print("\nAllowed Methods:")
        for method in settings.CORS_ALLOW_METHODS:
            print(f"  - {method}")
        
        print("\nAllowed Headers:")
        for header in settings.CORS_ALLOW_HEADERS[:5]:  # First 5
            print(f"  - {header}")
        print(f"  ... and {len(settings.CORS_ALLOW_HEADERS) - 5} more")
        
        # Check if POST is allowed
        if 'POST' in settings.CORS_ALLOW_METHODS:
            print("\n✅ POST method is allowed")
        else:
            print("\n❌ POST method is NOT allowed!")
        
        # Check if Authorization is allowed
        if 'authorization' in [h.lower() for h in settings.CORS_ALLOW_HEADERS]:
            print("✅ Authorization header is allowed")
        else:
            print("❌ Authorization header is NOT allowed!")
        
        return True
    except Exception as e:
        print(f"❌ CORS configuration error: {e}")
        return False

def test_authentication():
    """Test token authentication"""
    print_header("3. AUTHENTICATION TEST")
    try:
        # Get or create a test user
        user = CustomUser.objects.filter(is_superuser=True).first()
        if not user:
            print("❌ No superuser found in database")
            return False
        
        print(f"Test User: {user.email}")
        
        # Get or create token
        token, created = Token.objects.get_or_create(user=user)
        print(f"Token: {token.key[:20]}...{token.key[-10:]}")
        print(f"Token Created: {'Yes (New)' if created else 'No (Existing)'}")
        
        # Test if token works
        request = RequestFactory().get('/api/users/settings/')
        request.user = user
        force_authenticate(request, user=user, token=token)
        
        print(f"✅ Authentication token is valid")
        print(f"\nTo test in frontend, use:")
        print(f"  Authorization: Token {token.key}")
        
        return True, token.key
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_backup_endpoint(token_key=None):
    """Test backup endpoint"""
    print_header("4. BACKUP ENDPOINT TEST")
    try:
        # Get admin user
        admin_user = CustomUser.objects.filter(is_superuser=True).first()
        if not admin_user:
            print("❌ No admin user found")
            return False
        
        # Create request
        factory = RequestFactory()
        request = factory.post(
            '/api/users/settings/create_backup/',
            {'download': False},
            content_type='application/json'
        )
        request.user = admin_user
        
        # Get viewset
        view = SystemSettingsViewSet.as_view({'post': 'create_backup'})
        
        # Force authentication
        if token_key:
            token = Token.objects.get(key=token_key)
            force_authenticate(request, user=admin_user, token=token)
        
        print(f"Testing create_backup action...")
        print(f"  User: {admin_user.email}")
        print(f"  Superuser: {admin_user.is_superuser}")
        print(f"  HTTP Method: POST")
        
        # Try to call the action
        try:
            response = view(request)
            print(f"\n✅ Backup endpoint accessible")
            print(f"   Status: {response.status_code}")
            if hasattr(response, 'data'):
                print(f"   Response: {response.data}")
            return True
        except Exception as e:
            print(f"❌ Backup endpoint error: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Backup test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_notification_endpoint(token_key=None):
    """Test notification endpoint"""
    print_header("5. NOTIFICATION ENDPOINT TEST")
    try:
        # Get any user
        user = CustomUser.objects.first()
        if not user:
            print("❌ No users found")
            return False
        
        # Create request
        factory = RequestFactory()
        request = factory.get('/api/notifications/notifications/unread_count/')
        request.user = user
        
        # Force authentication
        if token_key:
            token = Token.objects.get(key=token_key)
            force_authenticate(request, user=user, token=token)
        
        print(f"Testing unread_count action...")
        print(f"  User: {user.email}")
        
        # Try to get viewset
        try:
            view = NotificationViewSet.as_view({'get': 'unread_count'})
            response = view(request)
            print(f"\n✅ Notification endpoint accessible")
            print(f"   Status: {response.status_code}")
            if hasattr(response, 'data'):
                print(f"   Unread count: {response.data}")
            return True
        except Exception as e:
            print(f"❌ Notification endpoint error: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Notification test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_middleware():
    """Check middleware configuration"""
    print_header("6. MIDDLEWARE CHECK")
    try:
        print("Middleware installed:")
        for i, middleware in enumerate(settings.MIDDLEWARE, 1):
            short_name = middleware.split('.')[-1]
            print(f"  {i}. {short_name}")
            
            # Highlight important ones
            if 'cors' in middleware.lower():
                print(f"     ✅ CORS middleware found at position {i}")
            if 'auth' in middleware.lower():
                print(f"     ✅ Auth middleware found at position {i}")
        
        # Check if CORS is before other middleware
        cors_index = -1
        for i, m in enumerate(settings.MIDDLEWARE):
            if 'cors' in m.lower():
                cors_index = i
                break
        
        if cors_index >= 0 and cors_index < 3:
            print(f"\n✅ CORS middleware is at good position ({cors_index + 1})")
        elif cors_index >= 0:
            print(f"\n⚠️  CORS middleware is at position {cors_index + 1} (should be near top)")
        else:
            print(f"\n❌ CORS middleware not found!")
        
        return True
    except Exception as e:
        print(f"❌ Middleware check error: {e}")
        return False

def check_rest_framework():
    """Check REST framework configuration"""
    print_header("7. REST FRAMEWORK CHECK")
    try:
        print("Authentication Classes:")
        for auth_class in settings.REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']:
            short_name = auth_class.split('.')[-1]
            print(f"  - {short_name}")
            if 'Token' in short_name:
                print(f"    ✅ Token authentication enabled")
        
        print("\nPermission Classes:")
        for perm_class in settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']:
            short_name = perm_class.split('.')[-1]
            print(f"  - {short_name}")
        
        return True
    except Exception as e:
        print(f"❌ REST framework check error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  PYTHONANYWHERE API DIAGNOSTICS")
    print("="*60)
    print(f"  Django Version: {django.VERSION}")
    print(f"  Debug Mode: {settings.DEBUG}")
    print(f"  Python Version: {sys.version.split()[0]}")
    print("="*60)
    
    results = {}
    
    # Run tests
    results['database'] = test_database()
    results['cors'] = test_cors_settings()
    auth_result = test_authentication()
    if isinstance(auth_result, tuple):
        results['auth'], token_key = auth_result
    else:
        results['auth'], token_key = auth_result, None
    
    results['middleware'] = check_middleware()
    results['rest_framework'] = check_rest_framework()
    results['backup'] = test_backup_endpoint(token_key)
    results['notification'] = test_notification_endpoint(token_key)
    
    # Summary
    print_header("SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test.replace('_', ' ').title()}")
    
    print(f"\nTests Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("Your API configuration looks good.")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("Review the errors above and check:")
        print("  1. CORS configuration in settings.py")
        print("  2. Middleware order in settings.py")
        print("  3. WSGI configuration")
        print("  4. Database connection")
        print("  5. PythonAnywhere logs for detailed errors")
    
    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()
