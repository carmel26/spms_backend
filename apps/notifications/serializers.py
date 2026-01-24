from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    related_user_name = serializers.CharField(source='related_user.get_full_name', read_only=True)
    presentation_title = serializers.CharField(source='presentation.research_title', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'recipient_name', 'notification_type',
            'title', 'message', 'presentation', 'presentation_title',
            'related_user', 'related_user_name', 'is_read', 'read_at',
            'created_at', 'priority'
        ]
        read_only_fields = [
            'id', 'created_at', 'recipient', 'notification_type',
            'title', 'message', 'presentation', 'related_user'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for NotificationPreference model"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'email_enabled', 'push_enabled', 'sms_enabled',
            'presentation_updates', 'examiner_assignments', 'date_changes',
            'assessment_updates', 'system_messages', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
