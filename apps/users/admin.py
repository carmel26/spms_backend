from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from .models import CustomUser, StudentProfile, SupervisorProfile, CoordinatorProfile, ExaminerProfile, PasswordReset, UserGroup, SystemSettings, AuditLog


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'blockchain_hash_short', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']
    readonly_fields = ['blockchain_hash', 'blockchain_timestamp', 'created_at', 'updated_at']
    
    def blockchain_hash_short(self, obj):
        """Display shortened blockchain hash"""
        if obj.blockchain_hash:
            return f"{obj.blockchain_hash[:16]}..."
        return "-"
    blockchain_hash_short.short_description = 'Blockchain Hash'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active')
        }),
        ('Blockchain', {
            'fields': ('blockchain_hash', 'blockchain_timestamp'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['system_name', 'system_email', 'updated_at', 'updated_by']
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not SystemSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False


class SupervisorProfileInline(admin.TabularInline):
    """Inline admin for supervisor profiles"""
    model = SupervisorProfile
    extra = 1
    fields = ['specialization', 'department', 'is_active']


class ExaminerProfileInline(admin.TabularInline):
    """Inline admin for examiner profiles"""
    model = ExaminerProfile
    extra = 1
    fields = ['specialization', 'is_active']


class CoordinatorProfileInline(admin.TabularInline):
    """Inline admin for coordinator profiles"""
    model = CoordinatorProfile
    extra = 1
    fields = ['school', 'is_active']


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ['username', 'get_full_name', 'email', 'get_roles_display', 'is_active', 'is_approved', 'date_created']
    list_filter = ['is_active', 'is_approved', 'date_created', 'user_groups']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    inlines = [SupervisorProfileInline, ExaminerProfileInline, CoordinatorProfileInline]
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'middle_name', 'last_name', 'email')}),
        ('Profile Information', {
            'fields': ('title', 'phone_number', 'registration_number', 'school', 'programme', 'profile_picture')
        }),
        ('User Roles & Groups', {
            'fields': ('user_groups',),
            'description': 'Select multiple roles for this user (students must have only student role)'
        }),
        ('Approval & Status', {
            'fields': ('is_verified', 'is_approved', 'approved_date', 'approved_by'),
            'description': 'Approve user for system access'
        }),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Security', {
            'fields': ('password_changed', 'blockchain_hash', 'blockchain_timestamp'),
            'classes': ('collapse',)
        }),
        ('Account Timestamps', {
            'fields': ('date_created', 'last_login', 'last_login_date'),
            'classes': ('collapse',)
        }),
    )
    
    def get_roles_display(self, obj):
        """Display all roles assigned to user"""
        roles = obj.get_all_roles()
        if roles:
            return format_html('<br>'.join(roles))
        return '-'
    get_roles_display.short_description = 'Roles'
    
    def get_full_name(self, obj):
        """Display full name with title"""
        return obj.get_full_name_with_title()
    get_full_name.short_description = 'Full Name'


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'programme_level', 'admission_year', 'supervisor', 'is_active_student']
    list_filter = ['programme_level', 'admission_year', 'is_active_student']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('user',)
        }),
        ('Academic Details', {
            'fields': ('programme_level', 'admission_year', 'enrollment_year', 'expected_graduation')
        }),
        ('Supervisor & Status', {
            'fields': ('supervisor', 'is_active_student', 'is_admitted')
        }),
        ('Progress Tracking', {
            'fields': ('progress_percentage', 'total_presentations', 'completed_presentations')
        }),
    )


@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'department', 'is_active', 'total_supervised']
    list_filter = ['is_active', 'department']
    search_fields = ['user__username', 'user__email', 'specialization']
    
    fieldsets = (
        ('Supervisor Information', {
            'fields': ('user', 'specialization', 'department')
        }),
        ('Status', {
            'fields': ('is_active', 'total_supervised')
        }),
    )


@admin.register(CoordinatorProfile)
class CoordinatorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'is_active']
    list_filter = ['school', 'is_active']
    search_fields = ['user__username', 'user__email']
    
    fieldsets = (
        ('Coordinator Information', {
            'fields': ('user', 'school')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(ExaminerProfile)
class ExaminerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'is_active', 'total_assessments']
    list_filter = ['is_active']
    search_fields = ['user__username', 'user__email', 'specialization']
    
    fieldsets = (
        ('Examiner Information', {
            'fields': ('user', 'specialization')
        }),
        ('Status', {
            'fields': ('is_active', 'total_assessments')
        }),
    )
@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'expires_at', 'is_used']
    list_filter = ['created_at', 'is_used']
    search_fields = ['user__username', 'user__email']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog - read-only"""
    list_display = ['timestamp', 'user_display', 'action', 'model_name', 'object_repr', 'success', 'ip_address']
    list_filter = ['action', 'model_name', 'success', 'timestamp']
    search_fields = ['user__username', 'user__email', 'model_name', 'object_repr', 'description', 'ip_address']
    readonly_fields = [
        'user', 'action', 'model_name', 'object_id', 'object_repr',
        'description', 'changes', 'ip_address', 'user_agent',
        'request_path', 'request_method', 'success', 'error_message',
        'timestamp', 'blockchain_hash', 'blockchain_block_number'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        """Prevent manual creation"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion (audit logs should be permanent)"""
        return False
    
    def user_display(self, obj):
        """Display user's full name or 'System'"""
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'System'
    user_display.short_description = 'User'
    
    fieldsets = (
        ('Action Details', {
            'fields': ('user', 'action', 'timestamp', 'success')
        }),
        ('Object Information', {
            'fields': ('model_name', 'object_id', 'object_repr', 'description')
        }),
        ('Changes', {
            'fields': ('changes',),
            'classes': ('collapse',)
        }),
        ('Request Context', {
            'fields': ('ip_address', 'user_agent', 'request_path', 'request_method'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Blockchain Reference', {
            'fields': ('blockchain_hash', 'blockchain_block_number'),
            'classes': ('collapse',)
        }),
    )
