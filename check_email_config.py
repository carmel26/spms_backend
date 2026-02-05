#!/usr/bin/env python
"""Check email configuration and send test email"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print('=' * 60)
print('Email Configuration Check')
print('=' * 60)
print(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
print(f'EMAIL_HOST: {settings.EMAIL_HOST}')
print(f'EMAIL_PORT: {settings.EMAIL_PORT}')
print(f'EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}')
print(f'EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
print(f'EMAIL_HOST_PASSWORD: {"Set" if settings.EMAIL_HOST_PASSWORD else "Not Set"}')
print(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
print()
print('Testing email to: nkeshimanac@nm-aist.ac.tz')
print('=' * 60)

try:
    result = send_mail(
        'SPMS - Email Configuration Test - Please Check',
        '''This email confirms that the SPMS email system is properly configured.

If you received this email, the system is working correctly.

Please reply to confirm receipt.

---
Scholar Progress Management System
The Nelson Mandela African Institution of Science and Technology''',
        settings.DEFAULT_FROM_EMAIL,
        ['nkeshimanac@nm-aist.ac.tz'],
        fail_silently=False,
    )
    print(f'✓ Email sent successfully!')
    print(f'Return value: {result}')
    print()
    print('IMPORTANT: Please check the inbox at: nkeshimanac@nm-aist.ac.tz')
    print('Also check:')
    print('  - Spam/Junk folder')
    print('  - Promotions tab (if using Gmail)')
    print('  - Social tab (if using Gmail)')
    print()
    print(f'Email sent from: {settings.DEFAULT_FROM_EMAIL}')
    print(f'Subject: SPMS - Email Configuration Test - Please Check')
except Exception as e:
    print(f'✗ ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
