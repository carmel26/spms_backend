"""
Models for Users app - All user roles and authentication
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinLengthValidator
import hashlib


class UserGroup(models.Model):
    """User groups/roles table for better normalization"""
    
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Role name (e.g., student, supervisor, admin)"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Display name for the role"
    )
    description = models.TextField(blank=True)
    # Stored permissions for this user group as a list of permission codenames
    permissions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Blockchain fields for tamper-proof tracking
    blockchain_hash = models.CharField(max_length=256, blank=True, null=True)
    blockchain_timestamp = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_groups'
        ordering = ['name']
    
    def __str__(self):
        return self.display_name


USER_ROLE_CHOICES = (
    ('student', 'Student'),
    ('supervisor', 'Supervisor'),
    ('coordinator', 'Progress Coordinator'),
    ('moderator', 'Progress Moderator'),
    ('examiner', 'Examiner'),
    ('dean', 'Dean of School'),
    ('qa', 'Quality Assurance'),
    ('auditor', 'Auditor'),
    ('admission', 'Admission Officer'),
    ('vice_chancellor', 'Vice Chancellor'),
    ('admin', 'Admin'),
)

PROGRAMME_LEVEL_CHOICES = (
    ('masters', 'Masters'),
    ('phd', 'PhD'),
)

TITLE_CHOICES = (
    ('dr', 'Dr'),
    ('prof', 'Prof'),
    ('mr', 'Mr'),
    ('mrs', 'Mrs'),
    ('ms', 'Ms'),
    ('', 'None'),
)


class CustomUserManager(UserManager):
    """Custom user manager that sets roles using user_groups"""
    
    def create_superuser(self, username, email, password=None, **extra_fields):
        """Create a superuser with admin role"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        # Get or create admin user group
        admin_group, _ = UserGroup.objects.get_or_create(
            name='admin',
            defaults={
                'display_name': 'Administrator',
                'description': 'System administrator with full access'
            }
        )
        
        user = super().create_superuser(username, email, password, **extra_fields)
        # Add admin group to user
        user.user_groups.add(admin_group)
        
        return user


class CustomUser(AbstractUser):
    """Extended User model with multiple roles support via ManyToMany relationship"""
    
    # Override email field to make it unique and required
    email = models.EmailField(
        'email address',
        unique=True,
        error_messages={
            'unique': 'A user with this email already exists.',
        },
        help_text="User's email address (must be unique)"
    )
    
    # Title field (Dr, Prof, Mr, Mrs, Ms)
    title = models.CharField(
        max_length=10,
        choices=TITLE_CHOICES,
        blank=True,
        default='',
        help_text="User's title (Dr, Prof, Mr, Mrs, Ms)"
    )
    
    # Many-to-many relationship for multiple roles/groups
    # Users can have multiple roles (e.g., supervisor AND examiner)
    # Exception: Students can only be students
    user_groups = models.ManyToManyField(
        UserGroup,
        related_name='group_users',
        blank=True,
        help_text="User's roles/groups - can have multiple except students (students must be student-only)"
    )
    
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    middle_name = models.CharField(max_length=150, blank=True, null=True)
    registration_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Student registration number"
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    programme = models.ForeignKey(
        'schools.Programme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    is_verified = models.BooleanField(default=False, help_text="Email verified")
    is_approved = models.BooleanField(default=False, help_text="Profile approved by admin/admission")
    approved_date = models.DateTimeField(null=True, blank=True, help_text="Date when profile was approved")
    approved_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_users',
        help_text="Admin/Admission officer who approved this user"
    )
    password_changed = models.BooleanField(
        default=False,
        help_text="User has changed password from default"
    )
    date_created = models.DateTimeField(auto_now_add=True)
    last_login_date = models.DateTimeField(null=True, blank=True)
    
    # Soft delete fields
    is_deleted = models.BooleanField(
        default=False,
        help_text="User has been soft deleted"
    )
    deleted_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when user was deleted"
    )
    deleted_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_users',
        help_text="Admin who deleted this user"
    )
    
    # Blockchain hash for tamper proof
    blockchain_hash = models.CharField(max_length=256, blank=True, null=True)
    blockchain_timestamp = models.DateTimeField(null=True, blank=True)
    
    objects = CustomUserManager()
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_created']
    
    def __str__(self):
        title_display = f"{self.get_title_display()} " if self.title else ""
        roles = ', '.join(self.get_all_roles()) if self.get_all_roles() else 'No Role'
        return f"{title_display}{self.get_full_name()} - {roles}"
    
    def get_full_name_with_title(self):
        """Get full name including title"""
        title_display = f"{self.get_title_display()} " if self.title else ""
        return f"{title_display}{self.get_full_name()}"
    
    def get_all_roles(self):
        """Get all roles assigned to this user"""
        return list(self.user_groups.values_list('name', flat=True))
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return self.user_groups.filter(name=role_name).exists()
    
    def has_permission(self, permission_name):
        """
        Check if user has a specific permission through any of their user groups.
        Permissions are stored in UserGroup.permissions JSONField as a list of permission codenames.
        """
        # Superusers have all permissions
        if self.is_superuser:
            return True
        
        # Check if any of the user's groups have this permission
        for group in self.user_groups.all():
            if group.permissions and permission_name in group.permissions:
                return True
        return False
    
    def get_all_permissions(self):
        """Get all permissions from all user groups"""
        permissions = set()
        for group in self.user_groups.all():
            if group.permissions:
                permissions.update(group.permissions)
        return list(permissions)
    
    def is_student(self):
        """Check if user is a student"""
        return self.has_role('student')
    
    def is_admin(self):
        """Check if user is an admin"""
        return self.has_role('admin')
    
    def get_supervisor_profiles(self):
        """Get all supervisor profiles for this user"""
        return self.supervisor_profiles.filter(is_active=True)
    
    def get_examiner_profiles(self):
        """Get all examiner profiles for this user"""
        return self.examiner_profiles.filter(is_active=True)
    
    def get_coordinator_profiles(self):
        """Get all coordinator profiles for this user"""
        return self.coordinator_profiles.filter(is_active=True)
    
    def get_role_display_name(self):
        """Get human-readable role names (comma-separated if multiple)"""
        roles = self.user_groups.all()
        if roles.exists():
            return ', '.join([g.display_name for g in roles])
        return 'No Role'
    
    def get_role_name(self):
        """Get primary role name"""
        roles = self.get_all_roles()
        return roles[0] if roles else None
    
    def generate_blockchain_hash(self):
        """Generate blockchain hash for user data"""
        data = f"{self.id}{self.username}{self.email}{self.registration_number}{self.phone_number}"
        return hashlib.sha256(data.encode()).hexdigest()


class SystemSettings(models.Model):
    """System-wide settings stored in database"""
    
    # General Settings
    system_name = models.CharField(
        max_length=255,
        default='Secure Progress Management System'
    )
    system_email = models.EmailField(default='admin@nm-aist.ac.tz')
    system_url = models.URLField(default='http://localhost:4200')
    
    # Presentation Settings
    max_presentations = models.IntegerField(
        default=3,
        help_text='Maximum presentations per student'
    )
    presentation_duration = models.IntegerField(
        default=20,
        help_text='Presentation duration in minutes'
    )
    qa_duration = models.IntegerField(
        default=10,
        help_text='Q&A duration in minutes'
    )
    
    # Email Notification Settings
    email_on_registration = models.BooleanField(
        default=True,
        help_text='Send email on user registration'
    )
    email_on_presentation_request = models.BooleanField(
        default=True,
        help_text='Send email on presentation request'
    )
    email_on_approval = models.BooleanField(
        default=True,
        help_text='Send email on presentation approval'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settings_updates'
    )
    
    class Meta:
        db_table = 'system_settings'
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return f"System Settings (Updated: {self.updated_at})"
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance (singleton pattern)"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class StudentProfile(models.Model):
    """Extended profile for students - Only students can have this profile"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    programme_level = models.CharField(
        max_length=20,
        choices=PROGRAMME_LEVEL_CHOICES,
        default='masters'
    )
    admission_year = models.IntegerField()
    enrollment_year = models.IntegerField()
    expected_graduation = models.DateField()
    supervisor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_students'
    )
    is_active_student = models.BooleanField(default=True)
    is_admitted = models.BooleanField(
        default=False,
        help_text="Student has been admitted by admission officer"
    )
    progress_percentage = models.FloatField(default=0.0)
    total_presentations = models.IntegerField(default=0)
    completed_presentations = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'student_profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.programme_level}"


class SupervisorProfile(models.Model):
    """Metadata for users with supervisor role - Can be multiple roles per user"""
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='supervisor_profiles'
    )
    specialization = models.CharField(max_length=255, blank=True)
    department = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    total_supervised = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'supervisor_profiles'
        unique_together = ['user', 'specialization']  # One specialization per user
    
    def __str__(self):
        return f"Supervisor: {self.user.get_full_name()}"


class CoordinatorProfile(models.Model):
    """Metadata for users with coordinator role - Can be multiple roles per user"""
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='coordinator_profiles'
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='coordinators'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'coordinator_profiles'
        unique_together = ['user', 'school']  # One coordinator per user per school
    
    def __str__(self):
        return f"Coordinator: {self.user.get_full_name()}"


class ExaminerProfile(models.Model):
    """Metadata for users with examiner role - Can be multiple roles per user"""
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='examiner_profiles'
    )
    specialization = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    total_assessments = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'examiner_profiles'
        unique_together = ['user', 'specialization']  # One specialization per user
    
    def __str__(self):
        return f"Examiner: {self.user.get_full_name()}"


class PasswordReset(models.Model):
    """Model to track password reset requests"""
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'password_resets'


class AuditLog(models.Model):
    """Comprehensive audit log for all operations in the system"""
    
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('ASSIGN', 'Assign'),
        ('SUBMIT', 'Submit'),
        ('SCHEDULE', 'Schedule'),
        ('SEND', 'Send'),
        ('EXPORT', 'Export'),
    )
    
    # Who did it
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    
    # What was done
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, help_text="Name of the model affected")
    object_id = models.CharField(max_length=100, help_text="ID of the affected object")
    object_repr = models.CharField(max_length=255, help_text="String representation of the object")
    
    # Details
    description = models.TextField(blank=True, help_text="Human-readable description of the action")
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON of changes (before/after for updates)"
    )
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)  # GET, POST, PUT, DELETE
    
    # Result
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Blockchain reference
    blockchain_hash = models.CharField(max_length=256, blank=True, null=True)
    blockchain_block_number = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        user_display = self.user.get_full_name() if self.user else 'System'
        return f"{user_display} - {self.action} {self.model_name} at {self.timestamp}"
    
    @classmethod
    def log_action(cls, user, action, model_instance, description='', changes=None, 
                   ip_address=None, user_agent='', request_path='', request_method='',
                   success=True, error_message=''):
        """Helper method to create audit log entries"""
        return cls.objects.create(
            user=user,
            action=action,
            model_name=model_instance.__class__.__name__,
            object_id=str(model_instance.pk),
            object_repr=str(model_instance),
            description=description,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            success=success,
            error_message=error_message
        )
    
    def __str__(self):
        return f"Password reset for {self.user.email}"
