#!/usr/bin/env python
"""
Test script to verify email sending functionality in SPMS
Tests email to: nkeshimanac@nm-aist.ac.tz
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

# Test email address
TEST_EMAIL = 'nkeshimanac@nm-aist.ac.tz'

def test_simple_email():
    """Test sending a simple text email"""
    print('\n' + '='*60)
    print('Test 1: Simple Text Email')
    print('='*60)
    print(f'Email Backend: {settings.EMAIL_BACKEND}')
    print(f'From Email: {settings.DEFAULT_FROM_EMAIL}')
    print(f'To Email: {TEST_EMAIL}')
    
    try:
        result = send_mail(
            subject='SPMS Test Email - Simple',
            message='This is a test message from the Scholar Progress Management System.\n\nIf you receive this, email sending is working correctly.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[TEST_EMAIL],
            fail_silently=False,
        )
        print(f'✓ Email sent successfully. Result: {result}')
        return True
    except Exception as e:
        print(f'✗ Error sending email: {e}')
        import traceback
        traceback.print_exc()
        return False


def test_html_email():
    """Test sending an HTML email"""
    print('\n' + '='*60)
    print('Test 2: HTML Email')
    print('='*60)
    
    try:
        subject = 'SPMS Test Email - HTML'
        text_body = 'This is the plain text version of the email.'
        html_body = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #0b6b2e;">SPMS Email Test</h2>
            <p>This is a test HTML email from the Scholar Progress Management System.</p>
            <p>If you can see this formatted message, HTML email sending is working correctly.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">This is an automated test email.</p>
        </body>
        </html>
        """
        
        msg = EmailMultiAlternatives(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [TEST_EMAIL]
        )
        msg.attach_alternative(html_body, 'text/html')
        result = msg.send(fail_silently=False)
        
        print(f'✓ HTML email sent successfully. Result: {result}')
        return True
    except Exception as e:
        print(f'✗ Error sending HTML email: {e}')
        import traceback
        traceback.print_exc()
        return False


def test_supervisor_notification_email():
    """Test the actual supervisor notification email format"""
    print('\n' + '='*60)
    print('Test 3: Supervisor Notification Email')
    print('='*60)
    
    try:
        student_name = 'John Doe (Test Student)'
        project_title = 'Machine Learning Applications in Healthcare (Test Project)'
        supervisor_name = 'Dr. Test Supervisor'
        
        subject = f'Action Required: Sign Form for {student_name}'
        message = f'''Dear {supervisor_name},

{student_name} has submitted a Research Progress Report for the project "{project_title}".

You are requested to log in to the system, review the report, and complete Part B (Supervisor Section) with your signature.

Please log in at your earliest convenience to complete this task.

Thank you.

---
Scholar Progress Management System
The Nelson Mandela African Institution of Science and Technology'''
        
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[TEST_EMAIL],
            fail_silently=False,
        )
        
        print(f'✓ Supervisor notification email sent successfully. Result: {result}')
        print(f'\nEmail Preview:')
        print('-'*60)
        print(f'Subject: {subject}')
        print(f'To: {TEST_EMAIL}')
        print(f'\n{message}')
        print('-'*60)
        return True
    except Exception as e:
        print(f'✗ Error sending supervisor notification: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    print('\n' + '='*60)
    print('SPMS Email Sending Tests')
    print('='*60)
    print(f'Testing email delivery to: {TEST_EMAIL}')
    
    results = []
    
    # Run all tests
    results.append(('Simple Email', test_simple_email()))
    results.append(('HTML Email', test_html_email()))
    results.append(('Supervisor Notification', test_supervisor_notification_email()))
    
    # Summary
    print('\n' + '='*60)
    print('Test Results Summary')
    print('='*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = '✓ PASS' if result else '✗ FAIL'
        print(f'{test_name}: {status}')
    
    print(f'\nTotal: {passed}/{total} tests passed')
    print('='*60 + '\n')
    
    return all(result for _, result in results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
