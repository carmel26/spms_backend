from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer
from .utils import send_presentation_time_reminder
from apps.presentations.models import PresentationSchedule


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
        # Trigger reminders for presentations starting soon.
        minutes = request.data.get('minutes', 15)
        try:
            minutes = int(minutes)
        except Exception:
            minutes = 15

        now = timezone.now()
        start_min = now + timezone.timedelta(minutes=minutes)
        end_min = start_min + timezone.timedelta(seconds=59)

        schedules = PresentationSchedule.objects.filter(start_time__gte=start_min, start_time__lt=end_min)
        total = 0
        for sched in schedules:
            send_presentation_time_reminder(sched.presentation, minutes_before=minutes)
            total += 1

        return Response({"status": "reminders sent", "count": total})