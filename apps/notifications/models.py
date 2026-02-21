import uuid

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.presentations.models import PresentationRequest


class Notification(models.Model):
    """
    Global notification model that can reference ANY backend model
    (presentations, profiles, assessments, system events, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    NOTIFICATION_TYPE_CHOICES = (
        ('presentation_request', 'Presentation Request'),
        ('presentation_accepted', 'Presentation Accepted'),
        ('presentation_declined', 'Presentation Declined'),
        ('examiner_assignment', 'Examiner Assignment'),
        ('date_changed', 'Presentation Date Changed'),
        ('time_warning', 'Presentation Starting Soon'),
        ('assessment_submitted', 'Assessment Submitted'),
        ('new_profile', 'New Profile Awaiting Approval'),
        ('profile_approved', 'Profile Approved'),
        ('profile_rejected', 'Profile Rejected'),
        ('presentation_completed', 'Presentation Completed'),
        ('new_student_registration', 'New Student Registration'),
        ('system_message', 'System Message'),
    )

 
    recipient = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPE_CHOICES
    )
    title = models.CharField(max_length=255)
    message = models.TextField()

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

  
    related_user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_notifications'
    )


    action_url = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Angular route to open when user clicks 'See more'"
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
 
    priority = models.IntegerField(
        default=0,
        help_text="Higher number = higher priority"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'is_archived']),
        ]

    def __str__(self):
        return f"{self.title} → {self.recipient.username}"

    def mark_as_read(self):
        """Mark notification as read safely"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class ReminderLog(models.Model):
    """
    Logs reminders sent to users about presentations.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    presentation = models.ForeignKey(PresentationRequest, on_delete=models.CASCADE)
    minutes_before = models.IntegerField()
    channel = models.CharField(max_length=20, help_text="Email or in-app")
    status = models.CharField(max_length=20, default='sent', help_text="sent or failed")
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reminder_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Reminder {self.channel} → {self.recipient.username} for {self.presentation}"


class NotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'

    def __str__(self):
        return f"Preferences for {self.user.username}"
