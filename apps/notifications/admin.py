from django.contrib import admin
from .models import Notification, NotificationPreference, ReminderLog
from django.contrib.contenttypes.admin import GenericTabularInline


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'recipient', 'notification_type', 'is_read', 'related_object_link', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'created_at', 'priority']
    search_fields = ['recipient__username', 'title', 'message']

    def related_object_link(self, obj):
        """Display a link to the related object if it exists"""
        if obj.content_object:
            return str(obj.content_object)
        return '-'
    related_object_link.short_description = 'Related Object'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'email_notifications', 'in_app_notifications',
    ]
    list_filter = [
        'email_notifications', 'in_app_notifications', 
    ]
    search_fields = ['user__username', 'user__email']


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = [
        'presentation', 'recipient', 'minutes_before', 'channel', 'status', 'created_at'
    ]
    list_filter = ['minutes_before', 'channel', 'status', 'created_at']
    search_fields = ['recipient__username', 'presentation__research_title']
