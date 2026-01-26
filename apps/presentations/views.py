from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.presentations.models import (
    PresentationRequest, 
    PresentationAssignment, 
    ExaminerAssignment,
    ExaminerChangeHistory,
    PresentationAssessment,
    PresentationSchedule
)
from apps.presentations.serializers import (
    PresentationRequestSerializer,
    PresentationTypeSerializer,
    BasicUserSerializer,
    ExaminerAssignmentSerializer,
    ExaminerChangeHistorySerializer,
)
from apps.schools.models import PresentationType
from apps.users.models import CustomUser, StudentProfile
from apps.notifications.utils import send_examiner_assignment_notification, send_examiner_response_notification, send_presentation_completed_notification, send_presentation_submitted_notification


class PresentationRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing student presentation requests"""

    serializer_class = PresentationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = PresentationRequest.objects.select_related(
            'student', 
            'presentation_type'
        ).prefetch_related(
            'supervisors', 
            'proposed_examiners',
            'assignment',
            'assignment__session_moderator',
            'assignment__examiner_assignments',
            'assignment__examiner_assignments__examiner'
        )

        # Students see only their own requests; admins/others see all
        if user.is_student():
            qs = qs.filter(student=user)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        instance._current_user = self.request.user
        instance.save()
    
    def perform_update(self, serializer):
        instance = serializer.save()
        instance._current_user = self.request.user
        instance.save()
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance._current_user = request.user
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='available-types')
    def available_types(self, request):
        """Return presentation types available for the current student"""
        student = request.user
        if not student.is_student():
            return Response({'detail': 'Only students can request presentations.'}, status=status.HTTP_403_FORBIDDEN)

        profile = StudentProfile.objects.filter(user=student).first()
        if not profile:
            return Response({'detail': 'Student profile not found. Please contact the admission office.'}, status=status.HTTP_400_BAD_REQUEST)

        blocked_type_ids = PresentationRequest.objects.filter(
            student=student
        ).exclude(status__in=['rejected', 'cancelled']).values_list('presentation_type_id', flat=True)

        type_qs = PresentationType.objects.filter(is_active=True).filter(
            Q(programme_type='both') | Q(programme_type=profile.programme_level)
        ).exclude(id__in=blocked_type_ids)

        data = {
            'programme_level': profile.programme_level,
            'available_types': PresentationTypeSerializer(type_qs, many=True).data,
            'blocked_type_ids': list(blocked_type_ids)
        }
        return Response(data)

    @action(detail=False, methods=['get'], url_path='options')
    def options(self, request):
        """Provide all data needed to build the request form in one call"""
        user = request.user
        
        # Get users with supervisor or examiner roles (always available)
        supervisors = CustomUser.objects.filter(
            user_groups__name='supervisor', 
            is_active=True, 
            is_approved=True
        ).distinct()
        
        examiners = CustomUser.objects.filter(
            user_groups__name='examiner', 
            is_active=True, 
            is_approved=True
        ).distinct()
        
        # Get moderators for session moderation
        moderators = CustomUser.objects.filter(
            user_groups__name='moderator',
            is_active=True,
            is_approved=True
        ).distinct()
        
        # For coordinators, return supervisors, examiners, and moderators
        if user.user_groups.filter(name='coordinator').exists():
            return Response({
                'supervisors': BasicUserSerializer(supervisors, many=True).data,
                'examiners': BasicUserSerializer(examiners, many=True).data,
                'moderators': BasicUserSerializer(moderators, many=True).data,
            })
        
        # For students, return full form data
        if not user.is_student():
            return Response({'detail': 'Only students and coordinators can access this information.'}, status=status.HTTP_403_FORBIDDEN)

        profile = StudentProfile.objects.filter(user=user).first()
        if not profile:
            return Response({'detail': 'Student profile not found. Please contact the admission office.'}, status=status.HTTP_400_BAD_REQUEST)

        blocked_type_ids = PresentationRequest.objects.filter(
            student=user
        ).exclude(status__in=['rejected', 'cancelled']).values_list('presentation_type_id', flat=True)

        type_qs = PresentationType.objects.filter(is_active=True).filter(
            Q(programme_type='both') | Q(programme_type=profile.programme_level)
        ).exclude(id__in=blocked_type_ids)

        existing_requests = PresentationRequest.objects.filter(student=user)

        return Response({
            'programme_level': profile.programme_level,
            'available_types': PresentationTypeSerializer(type_qs, many=True).data,
            'blocked_type_ids': list(blocked_type_ids),
            'supervisors': BasicUserSerializer(supervisors, many=True).data,
            'examiners': BasicUserSerializer(examiners, many=True).data,
            'existing_requests': PresentationRequestSerializer(existing_requests, many=True, context=self.get_serializer_context()).data,
            'student_supervisor_id': profile.supervisor.id if profile.supervisor else None
        })

    @action(detail=True, methods=['post'], url_path='confirm-examiners')
    def confirm_examiners(self, request, pk=None):
        """Confirm examiners for a presentation (coordinator only)"""
        user = request.user
        
        # Check if user is a coordinator
        if not user.user_groups.filter(name='coordinator').exists():
            return Response(
                {'detail': 'Only coordinators can confirm examiners.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        presentation = self.get_object()
        examiner_ids = request.data.get('examiner_ids', [])
        change_reason = request.data.get('change_reason', '')
        meeting_link = request.data.get('meeting_link', '')
        venue = request.data.get('venue', '')
        session_moderator_id = request.data.get('session_moderator_id', None)
        scheduled_date = request.data.get('scheduled_date', None)
        
        if not examiner_ids:
            return Response(
                {'detail': 'At least one examiner must be selected.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate examiners
        examiners = CustomUser.objects.filter(
            id__in=examiner_ids,
            user_groups__name='examiner',
            is_active=True
        )
        
        if examiners.count() != len(examiner_ids):
            return Response(
                {'detail': 'One or more invalid examiner IDs provided.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate session moderator if provided
        session_moderator = None
        if session_moderator_id:
            try:
                session_moderator = CustomUser.objects.get(
                    id=session_moderator_id,
                    is_active=True
                )
            except CustomUser.DoesNotExist:
                return Response(
                    {'detail': 'Invalid session moderator ID provided.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Save current examiners to history before making changes
        previous_examiners = list(presentation.proposed_examiners.all())
        
        # Create history record
        history = ExaminerChangeHistory.objects.create(
            presentation=presentation,
            changed_by=user,
            change_reason=change_reason or 'Coordinator confirmation'
        )
        
        # Set previous and new examiners
        if previous_examiners:
            history.previous_examiners.set(previous_examiners)
        history.new_examiners.set(examiners)
        
        # Create or get presentation assignment
        assignment, created = PresentationAssignment.objects.get_or_create(
            presentation=presentation,
            defaults={'coordinator': user}
        )
        
        # Update meeting link, venue, and session moderator
        # Use coordinator's link if provided, otherwise use student's submitted link
        assignment.meeting_link = meeting_link or presentation.meeting_link or ''
        assignment.venue = venue or ''
        assignment.session_moderator = session_moderator
        assignment.save()
        
        # Update scheduled_date and status based on whether date is provided
        if scheduled_date:
            from dateutil import parser
            from datetime import timedelta
            try:
                parsed_dt = parser.parse(scheduled_date)
                presentation.scheduled_date = parsed_dt
                presentation.status = 'scheduled'

                # Create or update a PresentationSchedule so schedule-related flows persist
                try:
                    # Default end_time = start_time + 1 hour
                    end_time = parsed_dt + timedelta(hours=1)
                    PresentationSchedule.objects.update_or_create(
                        presentation=presentation,
                        defaults={
                            'start_time': parsed_dt,
                            'end_time': end_time,
                            'meeting_link': assignment.meeting_link or presentation.meeting_link or '',
                            'venue': assignment.venue or ''
                        }
                    )
                except Exception:
                    # non-fatal: continue even if schedule update fails
                    pass
            except Exception as e:
                return Response(
                    {'detail': f'Invalid date format: {str(e)}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            presentation.status = 'accepted'
        
        # Keep declined examiners for audit trail, only remove non-declined assignments
        # This preserves the history of who declined and why
        assignment.examiner_assignments.exclude(status='declined').delete()
        
        # Create new examiner assignments and send notifications
        created_assignments = []
        for examiner in examiners:
            # Check if this examiner already has an assignment (e.g., previously declined)
            existing_assignment = assignment.examiner_assignments.filter(examiner=examiner).first()
            
            if existing_assignment:
                # Skip if they already have a declined assignment
                if existing_assignment.status == 'declined':
                    continue
                # Update existing assignment
                existing_assignment._current_user = user
                existing_assignment.status = 'assigned'
                existing_assignment.save()
                created_assignments.append(existing_assignment)
            else:
                # Create new assignment
                examiner_assignment = ExaminerAssignment.objects.create(
                    assignment=assignment,
                    examiner=examiner,
                    status='assigned'
                )
                examiner_assignment._current_user = user
                examiner_assignment.save()
                created_assignments.append(examiner_assignment)
            
            # Send notification to examiner
            try:
                send_examiner_assignment_notification(
                    examiner=examiner,
                    presentation_request=presentation,
                    assigned_by=user
                )
            except Exception as e:
                print(f"Failed to send notification to examiner {examiner.id}: {e}")
        
        # Update presentation to confirmed examiners
        presentation.proposed_examiners.set(examiners)
        presentation.save()
        
        status_message = f"Status set to '{presentation.status}'."
        return Response({
            'message': f'Successfully assigned {len(created_assignments)} examiner(s) and sent notifications. {status_message}',
            'assignments': ExaminerAssignmentSerializer(created_assignments, many=True).data,
            'status': presentation.status,
            'scheduled_date': presentation.scheduled_date
        })

    @action(detail=False, methods=['get'], url_path='my-assignments')
    def my_examiner_assignments(self, request):
        """Get examiner assignments for the current user"""
        user = request.user
        
        # Check if user is an examiner
        if not user.user_groups.filter(name='examiner').exists():
            return Response(
                {'detail': 'Only examiners can view their assignments.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all examiner assignments for this user
        assignments = ExaminerAssignment.objects.filter(
            examiner=user
        ).select_related('assignment__presentation', 'examiner')
        
        serializer = ExaminerAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='respond-assignment')
    def respond_to_assignment(self, request, pk=None):
        """Accept or decline an examiner assignment"""
        user = request.user
        
        # Check if user is an examiner
        if not user.user_groups.filter(name='examiner').exists():
            return Response(
                {'detail': 'Only examiners can respond to assignments.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the examiner assignment
        try:
            assignment = ExaminerAssignment.objects.get(
                id=pk,
                examiner=user
            )
        except ExaminerAssignment.DoesNotExist:
            return Response(
                {'detail': 'Assignment not found.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        response_status = request.data.get('status')
        decline_reason = request.data.get('decline_reason', '')
        
        if response_status not in ['accepted', 'declined']:
            return Response(
                {'detail': 'Status must be either "accepted" or "declined".'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if response_status == 'declined' and not decline_reason:
            return Response(
                {'detail': 'Decline reason is required when declining an assignment.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update assignment
        assignment.status = response_status
        if response_status == 'accepted':
            assignment.acceptance_date = timezone.now()
            assignment.decline_reason = None
        else:
            assignment.decline_reason = decline_reason
            assignment.acceptance_date = None
        
        assignment.save()
        
        # Mark the examiner's notification for this assignment as read
        from apps.notifications.models import Notification
        try:
            Notification.objects.filter(
                recipient=user,
                presentation=presentation,
                notification_type='examiner_assignment',
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
        except Exception as e:
            print(f"Failed to mark notification as read: {e}")
        
        # Send notification to coordinator about examiner's response
        presentation = assignment.assignment.presentation
        coordinator = assignment.assignment.coordinator
        
        # Send notification to the coordinator who created the assignment
        if coordinator:
            try:
                send_examiner_response_notification(
                    coordinator=coordinator,
                    presentation_request=presentation,
                    examiner=user,
                    status=response_status,
                    decline_reason=decline_reason if response_status == 'declined' else None
                )
            except Exception as e:
                print(f"Failed to send notification to coordinator {coordinator.id}: {e}")
        
        # If declined, also notify all other coordinators so they can reassign
        if response_status == 'declined':
            try:
                # Get all coordinators except the one who already got notified
                all_coordinators = CustomUser.objects.filter(
                    user_groups__name='coordinator',
                    is_active=True
                ).exclude(id=coordinator.id if coordinator else None).distinct()
                
                for coord in all_coordinators:
                    try:
                        send_examiner_response_notification(
                            coordinator=coord,
                            presentation_request=presentation,
                            examiner=user,
                            status=response_status,
                            decline_reason=decline_reason
                        )
                    except Exception as e:
                        print(f"Failed to send notification to coordinator {coord.id}: {e}")
            except Exception as e:
                print(f"Failed to notify additional coordinators: {e}")
        
        return Response({
            'message': f'Assignment {response_status} successfully.',
            'assignment': ExaminerAssignmentSerializer(assignment).data
        })

    @action(detail=True, methods=['post'], url_path='submit-assessment')
    def submit_assessment(self, request, pk=None):
        """Submit assessment/feedback for a presentation (examiner only)"""
        user = request.user
        
        # Check if user is an examiner
        if not user.user_groups.filter(name='examiner').exists():
            return Response(
                {'detail': 'Only examiners can submit assessments.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the examiner assignment for this presentation and user
        try:
            presentation = self.get_object()
            assignment = presentation.assignment
            examiner_assignment = ExaminerAssignment.objects.get(
                assignment=assignment,
                examiner=user,
                status='accepted'
            )
        except (PresentationAssignment.DoesNotExist, ExaminerAssignment.DoesNotExist):
            return Response(
                {'detail': 'You are not assigned as an examiner for this presentation or have not accepted the assignment.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get assessment data
        grade = request.data.get('grade')
        comments = request.data.get('comments')
        recommendations = request.data.get('recommendations', '')
        
        if not grade or not comments:
            return Response(
                {'detail': 'Grade and comments are required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update assessment
        assessment, created = PresentationAssessment.objects.update_or_create(
            examiner_assignment=examiner_assignment,
            defaults={
                'grade': grade,
                'comments': comments,
                'recommendations': recommendations
            }
        )
        
        # Mark examiner assignment as completed
        examiner_assignment.status = 'completed'
        examiner_assignment.save()
        
        # Check if all examiners have submitted their assessments
        all_examiners_completed = not assignment.examiner_assignments.exclude(
            status='completed'
        ).exists()
        
        # If all examiners have submitted, mark presentation as completed
        if all_examiners_completed:
            presentation.status = 'completed'
            presentation.actual_date = timezone.now()
            presentation.save()
            
            # Send notification to coordinator and student
            try:
                send_presentation_completed_notification(
                    presentation_request=presentation,
                    coordinator=assignment.coordinator
                )
            except Exception as e:
                print(f"Failed to send completion notification: {e}")
        
        action_text = 'updated' if not created else 'submitted'
        status_message = 'Presentation marked as completed.' if all_examiners_completed else 'Waiting for other examiners to submit their assessments.'
        
        return Response({
            'message': f'Assessment {action_text} successfully. {status_message}',
            'assessment_id': assessment.id,
            'presentation_status': presentation.status,
            'all_completed': all_examiners_completed
        })

    @action(detail=True, methods=['get'], url_path='examiner-history')
    def examiner_history(self, request, pk=None):
        """Get examiner change history for a presentation"""
        presentation = self.get_object()
        
        # Get history records for this presentation
        history = ExaminerChangeHistory.objects.filter(
            presentation=presentation
        ).prefetch_related('previous_examiners', 'new_examiners', 'changed_by')
        
        serializer = ExaminerChangeHistorySerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Get count of unread/unseen presentation requests for coordinators"""
        user = request.user
        
        # Check if user is a coordinator
        if not user.user_groups.filter(name='coordinator').exists():
            return Response(
                {'detail': 'Only coordinators can access this endpoint.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Count presentations that are submitted but not viewed by this coordinator
        unread_count = PresentationRequest.objects.filter(
            status='submitted'
        ).exclude(
            viewed_by_coordinators=user
        ).count()
        
        return Response({
            'unread_count': unread_count
        })

    @action(detail=True, methods=['post'], url_path='mark-as-viewed')
    def mark_as_viewed(self, request, pk=None):
        """Mark a presentation as viewed by the current coordinator"""
        user = request.user
        
        # Check if user is a coordinator
        if not user.user_groups.filter(name='coordinator').exists():
            return Response(
                {'detail': 'Only coordinators can mark presentations as viewed.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        presentation = self.get_object()
        
        # Add coordinator to viewed_by_coordinators if not already there
        if user not in presentation.viewed_by_coordinators.all():
            presentation.viewed_by_coordinators.add(user)
        
        return Response({
            'message': 'Presentation marked as viewed.',
            'presentation_id': presentation.id
        })
