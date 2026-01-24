from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
import datetime
from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer
from django.db.models import Q
from django.utils.dateformat import format as dateformat
from apps.presentations.models import (
    PresentationRequest,
    PresentationAssignment,
    SupervisorAssignment,
    ExaminerAssignment,
    PresentationSchedule,
)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for notifications - shows notifications for all authenticated users
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        """
        Return notifications for the current authenticated user
        """
        user = self.request.user
        
        # Return notifications for this user
        return Notification.objects.filter(
            recipient=user
        ).select_related('presentation', 'related_user').order_by('-created_at')

    @action(detail=False, methods=['get'])
    def aggregated_from_presentations(self, request):
        """Aggregate notification-like items from presentation-related tables.

        Returns a flat list of simple dicts with keys: id, label, created_at,
        category, to_user_id, attached (presentation id), status.
        """
        user = request.user
        now = timezone.now()
        items = []

        # Presentation requests (target the student primarily)
        prs = PresentationRequest.objects.exclude(status='draft').select_related('presentation_type', 'student')
        for pr in prs:
            items.append({
                'id': f'presentation_request:{pr.id}',
                'label': str(pr),
                'created_at': pr.created_at.isoformat() if getattr(pr, 'created_at', None) else None,
                'category': 'presentation_request',
                'to_user_id': pr.student.id if pr.student else None,
                'attached': {'presentation_id': pr.id, 'presentation_type': getattr(pr.presentation_type, 'name', None)},
                'status': pr.status,
            })

        # Presentation assignments (coordinators)
        pas = PresentationAssignment.objects.select_related('coordinator', 'presentation')
        for pa in pas:
            items.append({
                'id': f'presentation_assignment:{pa.id}',
                'label': f'Assignment for {pa.presentation.id}',
                'created_at': pa.created_at.isoformat() if getattr(pa, 'created_at', None) else None,
                'category': 'presentation_assignment',
                'to_user_id': pa.coordinator.id if pa.coordinator else None,
                'attached': {'presentation_id': pa.presentation.id},
                'status': None,
            })

        # Supervisor assignments
        sas = SupervisorAssignment.objects.select_related('supervisor', 'assignment__presentation')
        for sa in sas:
            items.append({
                'id': f'supervisor_assignment:{sa.id}',
                'label': f'Supervisor assignment for {sa.assignment.presentation.id}',
                'created_at': sa.acceptance_date.isoformat() if getattr(sa, 'acceptance_date', None) else None,
                'category': 'supervisor_assignment',
                'to_user_id': sa.supervisor.id if sa.supervisor else None,
                'attached': {'presentation_id': sa.assignment.presentation.id, 'assignment_id': sa.assignment.id},
                'status': sa.status,
            })

        # Examiner assignments
        eas = ExaminerAssignment.objects.select_related('examiner', 'assignment__presentation')
        for ea in eas:
            items.append({
                'id': f'examiner_assignment:{ea.id}',
                'label': f'Examiner assignment for {ea.assignment.presentation.id}',
                'created_at': ea.acceptance_date.isoformat() if getattr(ea, 'acceptance_date', None) else None,
                'category': 'examiner_assignment',
                'to_user_id': ea.examiner.id if ea.examiner else None,
                'attached': {'presentation_id': ea.assignment.presentation.id, 'assignment_id': ea.assignment.id},
                'status': ea.status,
            })

        # Presentation schedules (upcoming or recent)
        schedules = PresentationSchedule.objects.filter(start_time__gte=(now - datetime.timedelta(days=1))).select_related('presentation')
        for s in schedules:
            # Notify the student for the schedule
            student = getattr(s.presentation, 'student', None)
            items.append({
                'id': f'presentation_schedule:{s.id}',
                'label': f'Schedule for {s.presentation.id} at {s.start_time.isoformat()}',
                'created_at': s.start_time.isoformat() if getattr(s, 'start_time', None) else None,
                'category': 'presentation_schedule',
                'to_user_id': student.id if student else None,
                'attached': {'presentation_id': s.presentation.id, 'start_time': s.start_time.isoformat()},
                'status': None,
            })

        # Filter items addressed to current user (or return all for staff)
        if not user.is_staff:
            items = [it for it in items if it.get('to_user_id') == user.id]

        # Order by created_at descending when possible
        def sort_key(it):
            ca = it.get('created_at')
            return ca or ''

        items.sort(key=sort_key, reverse=True)

        return Response({'items': items})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications for current user"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'notification marked as read'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read for current user"""
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'status': f'{updated} notifications marked as read'})


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for notification preferences - for all users
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer
    
    def get_queryset(self):
        """
        Return preferences only for student users
        """
        user = self.request.user
        
        # Check if user has student profile
        if not hasattr(user, 'studentprofile'):
            return NotificationPreference.objects.none()
        
        return NotificationPreference.objects.filter(user=user)

