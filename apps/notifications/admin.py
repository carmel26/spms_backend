from django.contrib import admin
from .models import Notification, NotificationPreference
from .models import ReminderLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'title']


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_notifications', 'in_app_notifications']
    list_filter = ['email_notifications', 'in_app_notifications']


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ['presentation', 'recipient', 'minutes_before', 'channel', 'status', 'created_at']
    list_filter = ['minutes_before', 'channel', 'status', 'created_at']
    search_fields = ['recipient__username', 'presentation__research_title']
