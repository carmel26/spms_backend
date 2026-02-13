from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer
from .utils import send_presentation_reminders_to_all_actors
from apps.presentations.models import PresentationRequest, PresentationSchedule


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
        """
        Manually trigger reminders.

        If `presentation_id` is provided, force-send reminders for that
        specific presentation regardless of its scheduled time.

        Otherwise fall back to the time-window sweep (presentations
        starting within `minutes` from now).
        """
        presentation_id = request.data.get('presentation_id')
        minutes = request.data.get('minutes', 15)
        try:
            minutes = int(minutes)
        except Exception:
            minutes = 15

        # ---- Force-send for a specific presentation ----
        if presentation_id:
            try:
                pr = PresentationRequest.objects.select_related('student').get(id=presentation_id)
            except PresentationRequest.DoesNotExist:
                return Response(
                    {"detail": "Presentation not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            send_presentation_reminders_to_all_actors(pr, minutes_before=minutes)
            return Response({"status": "reminders sent", "count": 1})

        # ---- Fallback: time-window sweep ----
        now = timezone.now()
        window_start = now + timezone.timedelta(minutes=minutes)
        window_end = window_start + timezone.timedelta(seconds=59)

        schedule_pr_ids = list(
            PresentationSchedule.objects
            .filter(start_time__gte=window_start, start_time__lt=window_end)
            .values_list('presentation_id', flat=True)
        )
        actual_pr_ids = list(
            PresentationRequest.objects
            .filter(actual_date__gte=window_start, actual_date__lt=window_end)
            .values_list('id', flat=True)
        )
        all_ids = set(schedule_pr_ids) | set(actual_pr_ids)

        total = 0
        for pr in PresentationRequest.objects.filter(id__in=all_ids).select_related('student'):
            send_presentation_reminders_to_all_actors(pr, minutes_before=minutes)
            total += 1

        return Response({"status": "reminders sent", "count": total})