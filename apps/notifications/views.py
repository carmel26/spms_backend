from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    queryset = NotificationPreference.objects.all()
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return only preferences for the logged-in user
        return self.queryset.filter(user=self.request.user)


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return (
            Notification.objects
            .filter(
                recipient=self.request.user,
                is_archived=False
            )
            .select_related('recipient', 'related_user', 'content_type')
            .order_by('-created_at')
        )

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        return Response({
            'unread_count': self.get_queryset().filter(is_read=False).count()
        })

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'updated': updated})

    @action(detail=False, methods=['get'])
    def aggregated_from_presentations(self, request):
        # Simply return all notifications for this user
        notifications = self.get_queryset()
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

# --------
class SendReminderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Example: trigger reminders for all presentations starting soon
        send_presentation_time_reminder()
        return Response({"status": "reminders sent"})