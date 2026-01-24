from django.db import models


class Report(models.Model):
    """Report model for various dashboard reports"""
    
    REPORT_TYPE_CHOICES = (
        ('student_progress', 'Student Progress Report'),
        ('supervisor_overview', 'Supervisor Overview'),
        ('presentation_statistics', 'Presentation Statistics'),
        ('examiner_performance', 'Examiner Performance'),
        ('school_overview', 'School Overview'),
        ('system_audit', 'System Audit Report'),
    )
    
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Data
    report_data = models.JSONField()
    generated_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'reports'
        ordering = ['-generated_at']
    
    def __str__(self):
        return self.name


class DashboardWidget(models.Model):
    """Dashboard widgets for user dashboards"""
    
    WIDGET_TYPE_CHOICES = (
        ('progress_chart', 'Progress Chart'),
        ('statistics_card', 'Statistics Card'),
        ('timeline', 'Timeline'),
        ('recent_activities', 'Recent Activities'),
        ('notifications', 'Notifications'),
        ('quick_actions', 'Quick Actions'),
    )
    
    name = models.CharField(max_length=255)
    widget_type = models.CharField(max_length=50, choices=WIDGET_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Display settings
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=7, default='#000000', help_text="Hex color code")
    position = models.IntegerField(default=0, help_text="Display order")
    
    # Permissions
    role = models.CharField(
        max_length=50,
        choices=[
            ('student', 'Student'),
            ('supervisor', 'Supervisor'),
            ('coordinator', 'Coordinator'),
            ('moderator', 'Moderator'),
            ('examiner', 'Examiner'),
            ('dean', 'Dean'),
            ('qa', 'Quality Assurance'),
            ('auditor', 'Auditor'),
            ('admission', 'Admission Officer'),
            ('vice_chancellor', 'Vice Chancellor'),
            ('admin', 'Admin'),
        ]
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'dashboard_widgets'
        ordering = ['role', 'position']
    
    def __str__(self):
        return f"{self.name} - {self.role}"


class Audit(models.Model):
    """System audit log"""
    
    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('download', 'Download'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    )
    
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100)
    resource_id = models.BigIntegerField(null=True, blank=True)
    details = models.TextField(blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audits'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"
