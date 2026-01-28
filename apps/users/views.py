from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db.models import Q
from django.utils import timezone
from .models import CustomUser, StudentProfile, SupervisorProfile, ExaminerProfile, CoordinatorProfile, UserGroup, SystemSettings, AuditLog
from .serializers import (
    CustomUserSerializer, StudentProfileSerializer, LoginSerializer, 
    PasswordChangeSerializer, UserGroupSerializer, SystemSettingsSerializer, AuditLogSerializer
)
from apps.presentations.models import PresentationRequest, ExaminerAssignment
import logging


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for user operations"""
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    def get_queryset(self):
        """Allow filtering by role and approval status for admin views. Exclude deleted users."""
        qs = CustomUser.objects.filter(is_deleted=False)  # Filter out deleted users
        role = self.request.query_params.get('role')
        status_param = self.request.query_params.get('status')

        if role:
            # Filter by user_groups instead of role field
            qs = qs.filter(user_groups__name=role)

        if status_param:
            if status_param == 'pending':
                qs = qs.filter(is_approved=False)
            elif status_param == 'approved':
                qs = qs.filter(is_approved=True)

        return qs
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete user instead of hard delete to preserve blockchain integrity"""
        instance = self.get_object()
        
        # Capture user data before deletion
        deleted_data = {
            'id': instance.id,
            'username': instance.username,
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'title': instance.title or 'N/A',
            'phone_number': instance.phone_number or 'N/A',
            'roles': [g.display_name for g in instance.user_groups.all()],
            'is_approved': instance.is_approved,
            'is_active': instance.is_active,
            'date_joined': str(instance.date_joined),
        }
        
        # Log the deletion with full data
        AuditLog.log_action(
            user=request.user,
            action='DELETE',
            model_instance=instance,
            description=f'Deleted user: {instance.get_full_name()}',
            changes=deleted_data,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            request_path=request.path,
            request_method='DELETE',
            success=True
        )
        
        # Mark user as deleted (soft delete)
        instance.is_deleted = True
        instance.deleted_date = timezone.now()
        instance.deleted_by = request.user if request.user.is_authenticated else None
        instance.is_active = False  # Also deactivate the account
        instance.save()
        
        return Response(
            {'message': 'User successfully deleted'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    def get_permissions(self):
        if self.action in ['create', 'login', 'register', 'forgot_password', 'verify_reset_token', 'reset_password']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """Register new student"""
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(request.data.get('password'))
            
            # Add student role to user
            try:
                student_group = UserGroup.objects.get(name='student')
                user.user_groups.add(student_group)
            except UserGroup.DoesNotExist:
                # Create student group if it doesn't exist
                student_group = UserGroup.objects.create(
                    name='student',
                    display_name='Student',
                    description='Student user role'
                )
                user.user_groups.add(student_group)
            
            user.save()
            
            # Create token
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'message': 'Registration successful',
                'token': token.key,
                'user': CustomUserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """Login endpoint - accepts email or username"""
        try:
            email_or_username = request.data.get('email') or request.data.get('username')
            password = request.data.get('password')

            if not email_or_username or not password:
                return Response({'error': 'Email and password required'}, status=status.HTTP_400_BAD_REQUEST)

            # Try to authenticate with email first, then with username
            user = None
            try:
                # Try email first
                user_by_email = CustomUser.objects.get(email=email_or_username)
                user = authenticate(username=user_by_email.username, password=password)
            except CustomUser.DoesNotExist:
                # Try username if email doesn't exist
                user = authenticate(username=email_or_username, password=password)

            if user:
                # Block deleted accounts
                if user.is_deleted:
                    return Response(
                        {'detail': 'This account has been deleted. Please contact the administrator.'},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Block inactive accounts
                if not user.is_active:
                    return Response(
                        {'detail': 'Your account is inactive. Please contact the admission office.'},
                        status=status.HTTP_403_FORBIDDEN
                    )

                student_profile = None

                # Check if student is approved and admitted/active
                if user.is_student():
                    if not user.is_approved:
                        return Response(
                            {'detail': 'Your account is pending approval. Please contact the admission office.'},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    student_profile = StudentProfile.objects.filter(user=user).first()
                    if student_profile:
                        if not student_profile.is_admitted:
                            return Response(
                                {'detail': 'Your account has not been admitted yet. Please contact the admission office.'},
                                status=status.HTTP_403_FORBIDDEN
                            )
                        if not student_profile.is_active_student:
                            return Response(
                                {'detail': 'Your student profile is inactive. Please contact the admission office.'},
                                status=status.HTTP_403_FORBIDDEN
                            )
                    # If no profile exists but the user is approved/active, allow login (avoid hard block)

                token, created = Token.objects.get_or_create(user=user)
                user_data = CustomUserSerializer(user).data

                # Add student profile admission status if student
                if user.is_student():
                    user_data['student_profile'] = (
                        StudentProfileSerializer(student_profile).data if student_profile else None
                    )

                # Check if user must change password
                must_change_password = not user.password_changed

                # Update last login date for analytics and dashboard
                try:
                    user.last_login_date = timezone.now()
                    user.save(update_fields=['last_login_date'])
                except Exception:
                    # don't block login if saving last_login_date fails
                    pass

                return Response({
                    'message': 'Login successful',
                    'token': token.key,
                    'user': user_data,
                    'must_change_password': must_change_password
                })

            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as exc:
            logger = logging.getLogger(__name__)
            logger.exception('Unhandled exception during login')
            # Return a minimal, non-sensitive error to the client
            return Response({'detail': 'An internal error occurred while processing login. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout endpoint"""
        request.user.auth_token.delete()
        return Response({'message': 'Logout successful'})
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change password"""
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response({'error': 'Both passwords required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.check_password(old_password):
            return Response({'error': 'Invalid old password'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.password_changed = True  # Mark password as changed
        user.save()
        return Response({'message': 'Password changed successfully'})
    
    @action(detail=False, methods=['post'], permission_classes=[])
    def forgot_password(self, request):
        """Request password reset token"""
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = CustomUser.objects.get(email=email, is_active=True)
        except CustomUser.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response({'message': 'If this email exists, a password reset link has been sent.'})
        
        # Generate reset token
        import secrets
        from datetime import timedelta
        from django.utils import timezone
        from apps.users.models import PasswordReset
        from django.core.mail import send_mail
        from django.conf import settings
        
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=1)  # Token valid for 1 hour
        
        # Invalidate any existing tokens for this user
        PasswordReset.objects.filter(user=user, is_used=False).update(is_used=True)
        
        # Create new reset token
        PasswordReset.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )
        
        # Build reset link
        frontend_url = settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else request.build_absolute_uri('/').rstrip('/').replace('/api', '')
        reset_link = f"{frontend_url}/reset-password?token={token}"
        
        # Send email
        email_sent = False
        try:
            print(f"Attempting to send email to: {user.email}")
            print(f"From email: {settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com'}")
            print(f"Reset link: {reset_link}")
            
            # HTML Email Template
            html_message = f'''
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #0b63c5 0%, #0f3d91 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header i {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        .content {{
            background: #ffffff;
            padding: 40px 30px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .alert-box {{
            background: #e7f3ff;
            border-left: 4px solid #0b63c5;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .alert-box strong {{
            color: #0f3d91;
            font-size: 16px;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #0b63c5 0%, #0f3d91 100%);
            color: white !important;
            padding: 14px 40px;
            text-decoration: none;
            border-radius: 6px;
            margin: 25px 0;
            font-weight: 600;
            font-size: 16px;
            text-align: center;
        }}
        .button:hover {{
            background: linear-gradient(135deg, #0a57b0 0%, #0d3780 100%);
        }}
        .info-box {{
            background: #f8f9fa;
            padding: 15px;
            margin: 20px 0;
            border-radius: 6px;
            border: 1px solid #dee2e6;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 25px;
            text-align: center;
            border-radius: 0 0 8px 8px;
            border: 1px solid #e0e0e0;
            border-top: none;
            font-size: 14px;
            color: #6c757d;
        }}
        .footer p {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <i class="bi bi-shield-lock"></i>
        <h1>Password Reset Request</h1>
    </div>
    
    <div class="content">
        <p style="font-size: 16px;">Hello <strong>{user.get_full_name()}</strong>,</p>
        
        <p>You have requested to reset your password for the <strong>Secure Progress Management System</strong>.</p>
        
        <div class="alert-box">
            <strong><i class="bi bi-key"></i> Reset your password by clicking the button below:</strong>
        </div>
        
        <div style="text-align: center;">
            <a href="{reset_link}" class="button">Reset Password</a>
        </div>
        
        <div class="info-box">
            <p style="margin: 5px 0;"><strong><i class="bi bi-clock-history"></i> This link will expire in 1 hour</strong></p>
            <p style="margin: 5px 0; font-size: 14px;">For security reasons, password reset links are only valid for a limited time.</p>
        </div>
        
        <p style="margin-top: 25px; font-size: 14px; color: #6c757d;">
            If you did not request this password reset, please ignore this email. Your password will remain unchanged.
        </p>
        
        <p style="margin-top: 20px;">
            Best regards,<br>
            <strong>Secure Progress Management System Team</strong>
        </p>
    </div>
    
    <div class="footer">
        <p>This is an automated email from Secure Progress Management System</p>
        <p>&copy; 2026 Secure Progress Management System. All rights reserved.</p>
        <p style="font-size: 12px; margin-top: 10px;">If you're having trouble clicking the button, copy and paste this URL into your browser:<br>
        <span style="color: #0b63c5;">{reset_link}</span></p>
    </div>
</body>
</html>
            '''
            
            # Plain text version
            text_message = f'''
Hello {user.get_full_name()},

You have requested to reset your password for the Secure Progress Management System.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.

Best regards,
Secure Progress Management System Team
            '''
            
            send_mail(
                subject='Password Reset Request - Secure Progress Management System',
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
                recipient_list=[user.email],
                fail_silently=False,
            )
            email_sent = True
            print(f"Email sent successfully to: {user.email}")
        except Exception as e:
            import traceback
            print(f"Failed to send email: {e}")
            print(f"Full error: {traceback.format_exc()}")
        
        return Response({
            'message': 'If this email exists, a password reset link has been sent.',
            'token': token,  # Remove this in production, send via email only
            'email_sent': email_sent  # For debugging
        })
    
    @action(detail=False, methods=['post'], permission_classes=[])
    def reset_password(self, request):
        """Reset password using token"""
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        if not token or not new_password:
            return Response({'error': 'Token and new password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.users.models import PasswordReset
        from django.utils import timezone
        
        try:
            reset_request = PasswordReset.objects.get(
                token=token,
                is_used=False,
                expires_at__gt=timezone.now()
            )
        except PasswordReset.DoesNotExist:
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset the password
        user = reset_request.user
        user.set_password(new_password)
        user.password_changed = True
        user.save()
        
        # Mark token as used
        reset_request.is_used = True
        reset_request.save()
        
        return Response({'message': 'Password reset successfully. You can now login with your new password.'})
    
    @action(detail=False, methods=['post'], permission_classes=[])
    def verify_reset_token(self, request):
        """Verify if a reset token is valid"""
        token = request.data.get('token')
        
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.users.models import PasswordReset
        from django.utils import timezone
        
        try:
            reset_request = PasswordReset.objects.get(
                token=token,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            return Response({
                'valid': True,
                'email': reset_request.user.email
            })
        except PasswordReset.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Invalid or expired token'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def student_dashboard(self, request):
        """Get student dashboard stats"""
        if not request.user.is_student():
            return Response({'error': 'Not a student'}, status=status.HTTP_403_FORBIDDEN)
        
        student_profile = StudentProfile.objects.filter(user=request.user).first()
        if not student_profile:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        requests = PresentationRequest.objects.filter(student=request.user)
        
        return Response({
            'total_requests': requests.count(),
            'pending_requests': requests.filter(status='pending').count(),
            'scheduled_presentations': requests.filter(status='approved').count(),
            'completed_presentations': requests.filter(status='completed').count(),
        })
    
    @action(detail=False, methods=['get'])
    def supervisor_dashboard(self, request):
        """Get supervisor dashboard stats"""
        if not request.user.has_role('supervisor'):
            return Response({'error': 'Not a supervisor'}, status=status.HTTP_403_FORBIDDEN)
        
        students = StudentProfile.objects.filter(supervisor=request.user)
        total_students = students.count()
        
        all_requests = PresentationRequest.objects.filter(student__in=students)
        
        return Response({
            'total_students': total_students,
            'pending_presentations': all_requests.filter(status='pending').count(),
            'scheduled_presentations': all_requests.filter(status='approved').count(),
            'completed_presentations': all_requests.filter(status='completed').count(),
        })
    @action(detail=False, methods=['post'])
    def create_user_with_profiles(self, request):
        """Create a new user with multiple profiles (except students)
        
        Request body:
        {
            "username": "john.doe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "securepass123",
            "phone_number": "+255...",
            "user_groups": [1, 2],  # IDs of roles/groups
            "supervisor_profile": {
                "specialization": "Computer Science",
                "department": "CS"
            },
            "examiner_profile": {
                "specialization": "AI"
            },
            "coordinator_profile": {
                "school": 1
            }
        }
        """
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(request.data.get('password'))
            user.save()
            
            # Create supervisor profile if provided
            supervisor_data = request.data.get('supervisor_profile')
            if supervisor_data:
                SupervisorProfile.objects.create(user=user, **supervisor_data)
            
            # Create examiner profile if provided
            examiner_data = request.data.get('examiner_profile')
            if examiner_data:
                ExaminerProfile.objects.create(user=user, **examiner_data)
            
            # Create coordinator profile if provided
            coordinator_data = request.data.get('coordinator_profile')
            if coordinator_data:
                CoordinatorProfile.objects.create(user=user, **coordinator_data)
            
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'message': 'User created successfully with profiles',
                'token': token.key,
                'user': CustomUserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def coordinator_dashboard(self, request):
        """Get coordinator dashboard stats"""
        # Check if user has coordinator role
        if not request.user.has_role('coordinator'):
            return Response({'error': 'Not a coordinator'}, status=status.HTTP_403_FORBIDDEN)
        
        requests = PresentationRequest.objects.all()
        
        return Response({
            'pending_requests': requests.filter(status='pending').count(),
            'assigned_presentations': requests.filter(status='assigned').count(),
            'scheduled_presentations': requests.filter(status='approved').count(),
            'completed_presentations': requests.filter(status='completed').count(),
        })
    
    @action(detail=False, methods=['get'])
    def examiner_dashboard(self, request):
        """Get examiner dashboard stats"""
        # Check if user has examiner role
        if not request.user.has_role('examiner'):
            return Response({'error': 'Not an examiner'}, status=status.HTTP_403_FORBIDDEN)
        
        assignments = ExaminerAssignment.objects.filter(examiner=request.user)
        
        return Response({
            'pending_assignments': assignments.filter(status='pending').count(),
            'accepted_assignments': assignments.filter(status='accepted').count(),
            'declined_assignments': assignments.filter(status='declined').count(),
            'completed_assessments': 0,
        })
    
    @action(detail=False, methods=['get'])
    def admin_dashboard(self, request):
        """Get admin dashboard stats"""
        # Check if user has admin role
        if not request.user.is_admin():
            return Response({'error': 'Not admin'}, status=status.HTTP_403_FORBIDDEN)
        
        from apps.schools.models import School, Programme
        
        return Response({
            'total_users': CustomUser.objects.count(),
            'total_schools': School.objects.count(),
            'total_programmes': Programme.objects.count(),
            'total_presentations': PresentationRequest.objects.count(),
        })
    
    @action(detail=False, methods=['get'])
    def supervised_students(self, request):
        """Get list of students supervised by current user"""
        # Check if user has supervisor role
        if not request.user.has_role('supervisor'):
            return Response({'error': 'Not a supervisor'}, status=status.HTTP_403_FORBIDDEN)
        
        students = StudentProfile.objects.filter(supervisor=request.user)
        from .serializers import StudentProfileDetailSerializer
        serializer = StudentProfileDetailSerializer(students, many=True)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Update user with proper error handling"""
        partial = kwargs.pop('partial', True)  # Default to partial update
        instance = self.get_object()
        data = request.data.copy()

        # If approving a user, set approved_date and approved_by
        if 'is_approved' in data:
            is_approved_value = data.get('is_approved')
            is_approved_bool = (is_approved_value is True) or (isinstance(is_approved_value, str) and is_approved_value.lower() in ['true', '1', 'yes'])
            if is_approved_bool:
                from django.utils import timezone
                data['approved_date'] = timezone.now()
                if request.user and request.user.is_authenticated:
                    data['approved_by'] = request.user.id

        serializer = self.get_serializer(instance, data=data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return Response(serializer.data)
        else:
            print(f"User update validation errors: {serializer.errors}")
            print(f"Request data: {request.data}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def partial_update(self, request, *args, **kwargs):
        """Ensure partial update is used"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


class StudentProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for student profiles"""
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [IsAuthenticated]


class UserGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for user groups/roles"""
    queryset = UserGroup.objects.all().order_by('name')
    serializer_class = UserGroupSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    
    def get_queryset(self):
        """Allow filtering by is_active status"""
        queryset = UserGroup.objects.all().order_by('name')
        is_active = self.request.query_params.get('is_active')
        
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=is_active_bool)
        
        return queryset
    
    def get_permissions(self):
        """Allow read access to all authenticated users, write for authenticated (admin check can be added)"""
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        """Create a new user group with proper error handling"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            # Attach user for signal tracking
            instance._current_user = request.user
            instance.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            # Log validation errors for debugging
            print(f"UserGroup validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update user group with proper error handling"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        # Attach user for signal tracking
        instance._current_user = request.user
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return Response(serializer.data)
        else:
            print(f"UserGroup update validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to prevent deletion of roles with assigned users and log deleted data"""
        instance = self.get_object()
        
        # Check if any users have this role
        if instance.group_users.exists():
            user_count = instance.group_users.count()
            return Response(
                {'error': f'Cannot delete role. {user_count} user(s) are currently assigned this role.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Capture data before deletion for audit log
        deleted_data = {
            'id': instance.id,
            'name': instance.name,
            'display_name': instance.display_name,
            'description': instance.description or 'N/A',
            'permissions': list(instance.permissions.values_list('codename', flat=True)) if hasattr(instance, 'permissions') else [],
            'created_at': str(instance.created_at) if hasattr(instance, 'created_at') else 'N/A',
        }
        
        # Log the deletion with full data
        AuditLog.log_action(
            user=request.user,
            action='DELETE',
            model_instance=instance,
            description=f'Deleted user group: {instance.display_name}',
            changes=deleted_data,  # Store complete data before deletion
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            request_path=request.path,
            request_method='DELETE',
            success=True
        )
        
        return super().destroy(request, *args, **kwargs)


class SystemSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for system settings (singleton)"""
    queryset = SystemSettings.objects.all()
    serializer_class = SystemSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Always return the singleton settings instance"""
        return SystemSettings.get_settings()
    
    def list(self, request):
        """Return the singleton settings instance"""
        settings = SystemSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Update the singleton settings instance"""
        settings = SystemSettings.get_settings()
        # Attach current user for signal tracking
        settings._current_user = request.user
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current system settings"""
        settings = SystemSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing audit logs (read-only)"""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Allow filtering audit logs"""
        qs = AuditLog.objects.all().order_by('-timestamp')
        
        # Filter by user
        user_id = self.request.query_params.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)
        
        # Filter by model
        model_name = self.request.query_params.get('model')
        if model_name:
            qs = qs.filter(model_name=model_name)
        
        # Filter by object ID
        object_id = self.request.query_params.get('object_id')
        if object_id:
            qs = qs.filter(object_id=object_id)
        
        # Filter by success/failure
        success = self.request.query_params.get('success')
        if success is not None:
            qs = qs.filter(success=success.lower() == 'true')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(timestamp__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(timestamp__lte=end_date)
        
        return qs.select_related('user')
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent audit logs (last 100)"""
        logs = self.get_queryset().order_by('-timestamp')[:100]
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_activity(self, request):
        """Get current user's activity logs"""
        logs = AuditLog.objects.filter(user=request.user).order_by('-timestamp')[:100]
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get audit log statistics"""
        from django.db.models import Count
        
        # Total logs
        total = AuditLog.objects.count()
        
        # By action
        by_action = AuditLog.objects.values('action').annotate(count=Count('id')).order_by('-count')
        
        # By model
        by_model = AuditLog.objects.values('model_name').annotate(count=Count('id')).order_by('-count')[:10]
        
        # Success vs failure
        success_count = AuditLog.objects.filter(success=True).count()
        failure_count = AuditLog.objects.filter(success=False).count()
        
        # Most active users
        by_user = AuditLog.objects.exclude(user__isnull=True).values(
            'user__first_name', 'user__last_name', 'user__username'
        ).annotate(count=Count('id')).order_by('-count')[:10]
        
        return Response({
            'total': total,
            'by_action': list(by_action),
            'by_model': list(by_model),
            'success_count': success_count,
            'failure_count': failure_count,
            'success_rate': (success_count / total * 100) if total > 0 else 0,
            'most_active_users': list(by_user)
        })
