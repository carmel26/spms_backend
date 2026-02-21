from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import Notification, NotificationPreference

class NotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(
        source='recipient.get_full_name',
        read_only=True
    )

    related_user_name = serializers.CharField(
        source='related_user.get_full_name',
        read_only=True
    )

    related_user_school = serializers.CharField(
        source='related_user.school.name',
        read_only=True,
        allow_null=True
    )

    related_user_programme = serializers.CharField(
        source='related_user.programme.name',
        read_only=True,
        allow_null=True
    )

    # Generic object info (Angular-friendly)
    related_object = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
 
            'recipient',
            'recipient_name',
 
            'related_user',
            'related_user_name',
            'related_user_school',
            'related_user_programme',
 
            'related_object',
 
            'action_url',
 
            'is_read',
            'read_at',
            'is_archived',
 
            'priority',
            'created_at',
        ]

        read_only_fields = [
            'id',
            'recipient',
            'notification_type',
            'title',
            'message',
            'related_user',
            'created_at',
            'priority',
        ]

    def get_related_object(self, obj):
        """
        Return minimal, safe info about the related object
        (works for ANY table)
        """
        if not obj.content_type or not obj.object_id:
            return None

        return {
            'type': obj.content_type.model,     # e.g. "presentationrequest"
            'app': obj.content_type.app_label,  # e.g. "presentations"
            'id': str(obj.object_id)
        }

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['id', 'user', 'email_notifications', 'in_app_notifications']
        read_only_fields = ['id', 'user']