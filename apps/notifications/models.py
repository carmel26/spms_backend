from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """Notification model for all users"""
    
    NOTIFICATION_TYPE_CHOICES = (
        ('presentation_request', 'Presentation Request'),
        ('presentation_accepted', 'Presentation Accepted'),
        ('presentation_declined', 'Presentation Declined'),
        ('examiner_assignment', 'Examiner Assignment'),
        ('date_changed', 'Presentation Date Changed'),
        ('time_warning', 'Time Warning - Presentation Starting Soon'),
        ('assessment_submitted', 'Assessment Submitted'),
        ('new_profile', 'New Profile Awaiting Approval'),
        ('profile_approved', 'Profile Approved'),
        ('profile_rejected', 'Profile Rejected'),
        ('system_message', 'System Message'),
        ('presentation_completed', 'Presentation Completed'),
    )
    
    recipient = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related objects
    presentation = models.ForeignKey(
        'presentations.PresentationRequest',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_notifications'
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    priority = models.IntegerField(default=0, help_text="Higher number = higher priority")
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class NotificationPreference(models.Model):
    """User notification preferences"""
    
    user = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='notification_preference'
    )
    
    # Notification channels
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    # Notification types
    notify_presentation_request = models.BooleanField(default=True)
    notify_examiner_assignment = models.BooleanField(default=True)
    notify_date_changes = models.BooleanField(default=True)
    notify_time_warnings = models.BooleanField(default=True)
    notify_assessment_submitted = models.BooleanField(default=True)
    notify_new_profiles = models.BooleanField(default=True)
    
    # Time warning (minutes before presentation)
    time_warning_minutes = models.IntegerField(default=30)
    
    # Do not disturb
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
