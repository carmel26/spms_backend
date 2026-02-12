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
    FormSerializer,
    PhdAssessmentItemSerializer,
)
from apps.schools.models import PresentationType
from apps.users.models import CustomUser, StudentProfile
from apps.notifications.utils import (
    send_examiner_assignment_notification,
    send_examiner_response_notification,
    send_presentation_completed_notification,
    send_presentation_submitted_notification,
    send_supervisor_assignment_notification,
    send_session_moderator_assignment_notification,
)

from rest_framework import permissions
from apps.presentations.models import Form as PresentationForm
from apps.presentations.models import PhdAssessmentItem


class IsOwnerOrCoordinator(permissions.BasePermission):
    """Allow access if the user is the owner (created_by) or a coordinator."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if hasattr(obj, 'created_by') and obj.created_by == user:
            return True
        return user.user_groups.filter(name='coordinator').exists()


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

        # Notify the session moderator (in-app + email) if one was assigned
        if session_moderator:
            try:
                send_session_moderator_assignment_notification(
                    moderator=session_moderator,
                    presentation_request=presentation,
                    assigned_by=user
                )
            except Exception as e:
                print(f"Failed to notify session moderator {getattr(session_moderator, 'id', 'N/A')}: {e}")
        
        # Update scheduled_date and status based on whether date is provided
        if scheduled_date:
            from dateutil import parser
            from datetime import timedelta
            try:
                parsed_dt = parser.parse(scheduled_date)
                presentation.scheduled_date = parsed_dt
                presentation.actual_date = parsed_dt  # Also set actual_date for evaluation forms
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
        """Get examiner assignments for the current user (or all for admin)"""
        user = request.user
        is_admin = user.is_admin() if hasattr(user, 'is_admin') else False
        is_admin = is_admin or user.is_superuser
        
        # Check if user is an examiner or admin
        if not user.user_groups.filter(name='examiner').exists() and not is_admin:
            return Response(
                {'detail': 'Only examiners can view their assignments.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Admin sees all assignments; examiners see only their own
        if is_admin:
            assignments = ExaminerAssignment.objects.all()
        else:
            assignments = ExaminerAssignment.objects.filter(examiner=user)
        
        assignments = assignments.select_related(
            'assignment__presentation', 
            'assignment__presentation__student',
            'assignment__presentation__student__school',
            'assignment__presentation__student__programme',
            'examiner'
        ).prefetch_related('assignment__presentation__supervisors')
        
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



class FormViewSet(viewsets.ModelViewSet):
    """CRUD for `Form` objects storing JSON data."""

    serializer_class = FormSerializer
    permission_classes = [IsAuthenticated]
    queryset = PresentationForm.objects.all().select_related('created_by', 'presentation', 'blockchain_record')

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        # Students see their own created forms; coordinators see all
        # Coordinators see all
        if user.user_groups.filter(name='coordinator').exists():
            return qs

        # Admin users see all as well
        try:
            if user.user_groups.filter(name='admin').exists() or getattr(user, 'role', '') == 'admin':
                return qs
        except Exception:
            pass

        # Check if user is supervisor
        is_supervisor = user.user_groups.filter(name='supervisor').exists()
        
        # Check if user is dean/chairman
        is_dean = user.user_groups.filter(name__in=['dean', 'chairman']).exists()
        
        # Handle dual-role users (supervisor + dean) or single-role users
        if is_supervisor or is_dean:
            try:
                from django.db.models import Q
                uid = str(user.id)
                q = Q()
                
                if is_supervisor:
                    # Forms where user is assigned as supervisor
                    q |= Q(created_by=user)
                    q |= Q(presentation__supervisors__id=user.id)
                    
                    # JSONField lookups for supervisor assignment
                    try:
                        q |= Q(data__selected_supervisors__contains=[uid])
                    except Exception:
                        pass
                    try:
                        q |= Q(data__selected_supervisor=uid)
                    except Exception:
                        pass
                    try:
                        # sometimes stored as string
                        q |= Q(data__selected_supervisor__contains=uid)
                    except Exception:
                        pass
                
                if is_dean:
                    # Forms where supervisor has completed Part B (ready for dean review)
                    # AND dean hasn't signed yet
                    try:
                        q |= Q(
                            data__supervisor_part_b__signature_hash__isnull=False
                        ) & ~Q(
                            data__dean_part_c__signature_hash__isnull=False
                        )
                    except Exception:
                        # Fallback: just check if supervisor signed
                        try:
                            q |= Q(data__supervisor_part_b__signature_hash__isnull=False)
                        except Exception:
                            pass
                
                return qs.filter(q).distinct()
            except Exception:
                # Fallback: return forms created by the user only
                return qs.filter(created_by=user)

        # Default: students and other roles see only forms they created
        return qs.filter(created_by=user)

    def perform_create(self, serializer):
        import logging
        logger = logging.getLogger(__name__)
        instance = serializer.save(created_by=self.request.user)

        # If the form payload included a selected supervisor, notify them to
        # complete the supervisor part of the form (Part B).
        email_sent = False
        try:
            data = getattr(instance, 'data', {}) or {}
            sel = data.get('selected_supervisor') or data.get('selected_supervisors')
            logger.info('='*60)
            logger.info(f'📋 FORM CREATED - Processing email notification')
            logger.info(f'RAW DATA OBJECT: {data}')
            logger.info(f'Selected supervisor ID from form: {sel}')
            logger.info(f'Type of sel: {type(sel)}')
            logger.info(f'Form ID: {instance.id}')
            logger.info(f'Created by: {instance.created_by.get_full_name()} (ID: {instance.created_by.id})')
            logger.info('='*60)
            if sel:
                # sel might be a single id or a list
                from apps.users.models import CustomUser
                from apps.notifications.models import Notification

                ids = sel if isinstance(sel, list) else [sel]
                for sid in ids:
                    try:
                        sup = CustomUser.objects.get(id=sid)
                        logger.info(f'✓ Found supervisor: {sup.get_full_name()} (ID: {sup.id}, Email: {sup.email})')
                    except Exception as e:
                        logger.warning(f'✗ Could not find supervisor with ID {sid}: {e}')
                        sup = None
                    if sup:
                        try:
                            # Prefer sending the backend's supervisor assignment email/template when we have
                            # a linked PresentationRequest. This sends an email using the same design as
                            # other supervisor assignment flows and is best-effort.
                            if getattr(instance, 'presentation', None):
                                send_supervisor_assignment_notification(sup, instance.presentation, assigned_by=instance.created_by)
                                email_sent = True
                            else:
                                # No presentation associated: send a simple email using same template files
                                try:
                                    from django.conf import settings
                                    from django.template.loader import render_to_string
                                    from django.core.mail import EmailMultiAlternatives
                                    import logging

                                    logger = logging.getLogger(__name__)
                                    
                                    # Get student name and project title from form data
                                    student_name = data.get('student_full_name', instance.created_by.get_full_name())
                                    project_title = data.get('research_title', 'Research Progress Report')
                                    
                                    title = f'Action Required: Sign Form for {student_name}'
                                    message = f'Dear {sup.get_full_name()},\n\n{student_name} has submitted a Research Progress Report for the project "{project_title}".\n\nYou are requested to log in to the system, review the report, and complete Part B (Supervisor Section) with your signature.\n\nPlease log in at your earliest convenience to complete this task.\n\nThank you.'
                                    context = {
                                        'presentation': None,
                                        'recipient': sup,
                                        'assigned_by': instance.created_by,
                                        'student_name': student_name,
                                        'project_title': project_title,
                                        'role_label': 'Supervisor',
                                        'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
                                        'honorific': ''
                                    }
                                    logger.info('📧 Rendering email templates (FORM CREATE) with context:')
                                    logger.info(f'  - Student: {student_name}')
                                    logger.info(f'  - Project: {project_title}')
                                    logger.info(f'  - Recipient: {sup.get_full_name()}')
                                    logger.info(f'  - Role: Supervisor')
                                    
                                    try:
                                        html_body = render_to_string('emails/supervisor_form_notification.html', context)
                                        logger.info('✓ HTML email template rendered successfully')
                                    except Exception as html_err:
                                        logger.warning(f'✗ Failed to render HTML template: {html_err}')
                                        html_body = None
                                    try:
                                        text_body = render_to_string('emails/supervisor_form_notification.txt', context)
                                        logger.info('✓ Text email template rendered successfully')
                                    except Exception as txt_err:
                                        logger.warning(f'✗ Failed to render text template: {txt_err}')
                                        text_body = message

                                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
                                    to_emails = [sup.email] if getattr(sup, 'email', None) else []
                                    if to_emails:
                                        msg = EmailMultiAlternatives(title, text_body, from_email, to_emails)
                                        if html_body:
                                            msg.attach_alternative(html_body, 'text/html')
                                        try:
                                            logger.info('=' * 60)
                                            logger.info('SENDING SUPERVISOR EMAIL (Form Create)')
                                            logger.info(f'To: {to_emails}')
                                            logger.info(f'From: {from_email}')
                                            logger.info(f'Subject: {title}')
                                            logger.info(f'Student: {student_name}')
                                            logger.info(f'Project: {project_title}')
                                            logger.info('=' * 60)
                                            msg.send(fail_silently=False)
                                            logger.info('✓ Supervisor email (form create) successfully sent to %s', to_emails)
                                            logger.info('Email may take a few moments to arrive. Check spam folder if not in inbox.')
                                            email_sent = True
                                        except Exception as send_err:
                                            logger.exception('✗ Failed to send supervisor email from form create: %s', send_err)
                                    else:
                                        logger.warning(f'No email address for supervisor {sup.id}')
                                except Exception as email_err:
                                    logger.exception(f'Error preparing email: {email_err}')
                        except Exception as sup_err:
                            logger.exception(f'Error notifying supervisor: {sup_err}')
            else:
                logger.warning('⚠️ No supervisor selected (sel is None or empty) in FORM CREATE')
                logger.warning(f'Available keys in data: {list(data.keys())}')
        except Exception as outer_err:
            # Non-fatal: don't block form creation on notification failures
            logger.exception(f'Error in supervisor notification process: {outer_err}')
        
        # Store email status in instance for serializer response
        if hasattr(instance, '__dict__'):
            instance._email_sent = email_sent
            instance._email_status = 'sent' if email_sent else 'not_sent'
    
    def update(self, request, *args, **kwargs):
        """Override update to ensure perform_update is called with email logic"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Call perform_update which contains our email logic
        self.perform_update(serializer)
        
        # Get updated instance with email status
        instance = serializer.instance
        
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        # Build response data with email status
        response_data = serializer.data
        response_data['email_sent'] = getattr(instance, '_email_sent', False)
        response_data['email_status'] = getattr(instance, '_email_status', 'not_sent')

        return Response(response_data)

    def perform_update(self, serializer):
        import logging
        logger = logging.getLogger(__name__)
        
        # Preserve created_by
        instance = serializer.save()
        
        # If supervisor selection changed on update, optionally notify newly selected supervisors
        email_sent = False
        
        try:
            data = getattr(instance, 'data', {}) or {}
            sel = data.get('selected_supervisor') or data.get('selected_supervisors')
            
            if sel:
                from apps.users.models import CustomUser
                from apps.notifications.models import Notification
                ids = sel if isinstance(sel, list) else [sel]
                
                for sid in ids:
                    try:
                        sup = CustomUser.objects.get(id=sid)
                        logger.info(f'Found supervisor: {sup.get_full_name()} ({sup.email})')
                    except Exception as e:
                        logger.warning(f'Could not find supervisor with ID {sid}: {e}')
                        sup = None
                    
                    if sup:
                        if getattr(instance, 'presentation', None):
                            send_supervisor_assignment_notification(sup, instance.presentation, assigned_by=instance.created_by)
                            email_sent = True
                        else:
                            # Send email fallback when presentation is not linked
                            try:
                                from django.conf import settings
                                from django.template.loader import render_to_string
                                from django.core.mail import EmailMultiAlternatives
                                
                                student_name = data.get('student_full_name', instance.created_by.get_full_name())
                                project_title = data.get('research_title', 'Research Progress Report')
                                
                                title = f'Action Required: Sign Form for {student_name}'
                                message = f'Dear {sup.get_full_name()},\n\n{student_name} has submitted a Research Progress Report for the project "{project_title}".\n\nPlease log in to complete Part B (Supervisor Section).\n\nThank you.'
                                
                                context = {
                                    'presentation': None,
                                    'recipient': sup,
                                    'assigned_by': instance.created_by,
                                    'student_name': student_name,
                                    'project_title': project_title,
                                    'role_label': 'Supervisor',
                                    'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
                                    'honorific': ''
                                }
                                
                                # Render templates
                                html_body = None
                                try:
                                    html_body = render_to_string('emails/supervisor_form_notification.html', context)
                                except Exception:
                                    pass
                                
                                text_body = message
                                try:
                                    text_body = render_to_string('emails/supervisor_form_notification.txt', context)
                                except Exception:
                                    pass
                                
                                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
                                to_emails = [sup.email] if getattr(sup, 'email', None) else []
                                
                                if to_emails:
                                    msg = EmailMultiAlternatives(title, text_body, from_email, to_emails)
                                    if html_body:
                                        msg.attach_alternative(html_body, 'text/html')
                                    
                                    try:
                                        msg.send(fail_silently=False)
                                        logger.info(f'Supervisor email sent to {to_emails}')
                                        email_sent = True
                                    except Exception as send_err:
                                        logger.exception(f'Failed to send supervisor email: {send_err}')
                                        
                            except Exception as email_err:
                                logger.exception(f'Error preparing email: {email_err}')
                
        except Exception as outer_err:
            logger.exception(f'Error in supervisor notification: {outer_err}')
        
        # Store email status in instance for serializer response
        if hasattr(instance, '__dict__'):
            instance._email_sent = email_sent
            instance._email_status = 'sent' if email_sent else 'not_sent'

        # Check if supervisor has completed Part B and notify the dean
        try:
            data = getattr(instance, 'data', {}) or {}
            supervisor_part_b = data.get('supervisor_part_b', {})
            
            # If supervisor has signed Part B, assign to dean
            if supervisor_part_b and supervisor_part_b.get('signature_hash'):
                # Get the school from the form data
                school_name = data.get('school') or data.get('degree_programme')
                
                if school_name:
                    from apps.users.models import CustomUser, School
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    try:
                        # Find the school
                        school = School.objects.filter(name__icontains=school_name).first()
                        
                        if school and school.dean:
                            dean = school.dean
                            
                            # Send notification to dean
                            try:
                                from apps.notifications.models import Notification
                                Notification.objects.create(
                                    user=dean,
                                    message=f'Action required: Complete Part C (Dean Response) for {data.get("student_full_name", "a student")}\'s Research Progress Report.',
                                    notification_type='form_assignment',
                                    related_object_id=instance.id,
                                    related_content_type='form'
                                )
                                logger.info(f'Notification sent to dean {dean.username} for form {instance.id}')
                            except Exception as notif_err:
                                logger.error(f'Failed to create notification for dean: {notif_err}')
                            
                            # Send email to dean
                            try:
                                from django.conf import settings
                                from django.template.loader import render_to_string
                                from django.core.mail import EmailMultiAlternatives
                                
                                title = 'Action required: Complete Part C (Dean Response)'
                                message = f'A supervisor has completed Part B of a Research Progress Report for {data.get("student_full_name", "a student")}. Please log in to complete Part C (Dean/Chairman Response).'
                                
                                context = {
                                    'presentation': None,
                                    'recipient': dean,
                                    'assigned_by': instance.created_by,
                                    'role_label': 'Dean/Chairman',
                                    'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
                                    'honorific': ''
                                }
                                
                                try:
                                    html_body = render_to_string('emails/examiner_assignment.html', context)
                                except Exception:
                                    html_body = None
                                    
                                try:
                                    text_body = render_to_string('emails/examiner_assignment.txt', context)
                                except Exception:
                                    text_body = message
                                
                                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
                                to_emails = [dean.email] if getattr(dean, 'email', None) else []
                                
                                if to_emails:
                                    msg = EmailMultiAlternatives(title, text_body, from_email, to_emails)
                                    if html_body:
                                        msg.attach_alternative(html_body, 'text/html')
                                    try:
                                        logger.info(f'Attempting to send dean email to {to_emails}')
                                        msg.send(fail_silently=False)
                                        logger.info(f'Dean email sent to {to_emails}')
                                    except Exception as send_err:
                                        logger.exception(f'Failed to send dean email: {send_err}')
                            except Exception as email_err:
                                logger.error(f'Failed to send dean email: {email_err}')
                        else:
                            logger.warning(f'No dean found for school: {school_name}')
                    except Exception as school_err:
                        logger.error(f'Failed to process dean assignment: {school_err}')
        except Exception as dean_err:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to notify dean: {dean_err}')

        return instance

    @action(detail=False, methods=['get'], url_path='my-forms')
    def my_forms(self, request):
        """Get all forms linked to the current user as supervisor or dean.
        
        This action returns forms where:
        - User is assigned as supervisor (in any supervisor field)
        - User is dean/chairman and supervisor has completed Part B (ready for dean signature)
        
        For dual-role users (supervisor + dean), returns both sets of forms.
        Response includes metadata indicating the user's role(s) for each form.
        """
        user = request.user
        uid = str(user.id)
        
        # Check if user is supervisor
        is_supervisor = user.user_groups.filter(name='supervisor').exists()
        
        # Check if user is dean/chairman
        is_dean = user.user_groups.filter(name__in=['dean', 'chairman']).exists()
        
        # If neither supervisor nor dean, return empty
        if not is_supervisor and not is_dean:
            return Response({
                'results': [],
                'count': 0,
                'is_supervisor': False,
                'is_dean': False,
                'message': 'User is neither supervisor nor dean'
            })
        
        from django.db.models import Q
        
        # Build query based on roles
        supervisor_q = Q()
        dean_q = Q()
        
        if is_supervisor:
            # Forms where user is assigned as supervisor
            try:
                # Check linked presentation supervisors
                supervisor_q |= Q(presentation__supervisors__id=user.id)
                
                # Check JSON data fields for supervisor assignment
                supervisor_q |= Q(data__selected_supervisors__contains=[uid])
                supervisor_q |= Q(data__selected_supervisor=uid)
                supervisor_q |= Q(data__selected_supervisor__contains=uid)
            except Exception:
                pass
        
        if is_dean:
            # Forms where supervisor has completed Part B (ready for dean review)
            # AND dean hasn't signed yet (to avoid showing already completed forms)
            try:
                dean_q = Q(
                    data__supervisor_part_b__signature_hash__isnull=False
                ) & ~Q(
                    data__dean_part_c__signature_hash__isnull=False
                )
            except Exception:
                # Fallback: just check if supervisor signed
                try:
                    dean_q = Q(data__supervisor_part_b__signature_hash__isnull=False)
                except Exception:
                    pass
        
        # Combine queries
        combined_q = Q()
        if is_supervisor:
            combined_q |= supervisor_q
        if is_dean:
            combined_q |= dean_q
        
        # Apply filter and get distinct results
        qs = self.get_queryset().filter(combined_q).distinct().order_by('-created_at')
        
        # Serialize and add role metadata to each form
        serializer = self.get_serializer(qs, many=True)
        results = serializer.data
        
        # Annotate each form with the user's role for that form
        for item in results:
            form_id = item.get('id')
            try:
                form = qs.get(id=form_id)
                data = getattr(form, 'data', {}) or {}
                
                # Check if user is assigned as supervisor for this specific form
                is_assigned_supervisor = False
                if is_supervisor:
                    try:
                        # Check various supervisor fields
                        selected_sups = data.get('selected_supervisors', [])
                        selected_sup = data.get('selected_supervisor')
                        
                        if isinstance(selected_sups, list) and uid in selected_sups:
                            is_assigned_supervisor = True
                        elif selected_sup and str(selected_sup) == uid:
                            is_assigned_supervisor = True
                        elif form.presentation and form.presentation.supervisors.filter(id=uid).exists():
                            is_assigned_supervisor = True
                    except Exception:
                        pass
                
                # Check if form needs dean signature
                needs_dean_signature = False
                if is_dean:
                    try:
                        supervisor_part = data.get('supervisor_part_b', {})
                        dean_part = data.get('dean_part_c', {})
                        
                        # Needs dean signature if supervisor signed but dean hasn't
                        if supervisor_part.get('signature_hash') and not dean_part.get('signature_hash'):
                            needs_dean_signature = True
                    except Exception:
                        pass
                
                # Add metadata
                item['user_role_for_form'] = {
                    'is_assigned_supervisor': is_assigned_supervisor,
                    'needs_dean_signature': needs_dean_signature,
                    'supervisor_completed': bool(data.get('supervisor_part_b', {}).get('signature_hash')),
                    'dean_completed': bool(data.get('dean_part_c', {}).get('signature_hash'))
                }
            except Exception:
                # If annotation fails, continue without metadata
                item['user_role_for_form'] = {
                    'is_assigned_supervisor': False,
                    'needs_dean_signature': False,
                    'supervisor_completed': False,
                    'dean_completed': False
                }
        
        return Response({
            'results': results,
            'count': len(results),
            'is_supervisor': is_supervisor,
            'is_dean': is_dean,
            'message': 'Success'
        })

    @action(detail=False, methods=['get'], url_path='last-supervisors')
    def last_supervisors(self, request):
        """Return supervisors from the current user's most recent form submission.

        This helps frontend pre-select supervisors the student used previously.
        """
        user = request.user
        try:
            # Get the most recent form the student submitted (may contain a selected_supervisor)
            last = PresentationForm.objects.filter(created_by=user).order_by('-created_at').first()

            # Also fetch the most recent PresentationRequest submitted by the student
            last_preq = PresentationRequest.objects.filter(student=user).order_by('-created_at').first()

            if not last and not last_preq:
                return Response({'presentation': None, 'supervisors': [], 'last_selected_supervisor': None})

            data = getattr(last, 'data', {}) or {}

            # Collect candidate supervisor ids from various possible shapes in stored data
            candidate_ids = set()

            def extract_id(x):
                # Try several ways to extract an id (UUID string) from x
                try:
                    if x is None:
                        return None
                    if isinstance(x, str):
                        return x.strip() or None
                    if isinstance(x, int):
                        # legacy integer id — convert to string
                        return str(x)
                    if isinstance(x, dict):
                        for k in ('id', 'value', 'user_id', 'supervisor_id'):
                            if k in x and x[k] is not None:
                                return str(x[k])
                        return None
                except Exception:
                    return None

            # Common keys that might hold the selection
            possible_keys = ['selected_supervisor', 'selected_supervisors', 'supervisors', 'selected', 'selected_ids']
            for k in possible_keys:
                if k in data and data[k] is not None:
                    val = data[k]
                    if isinstance(val, list):
                        for item in val:
                            iid = extract_id(item)
                            if iid:
                                candidate_ids.add(iid)
                    else:
                        iid = extract_id(val)
                        if iid:
                            candidate_ids.add(iid)

            # Prefer supervisors from the student's most recent PresentationRequest if available
            pres = None
            if last_preq is not None:
                try:
                    pres = last_preq
                    for sup in pres.supervisors.all():
                        candidate_ids.add(str(sup.id))
                except Exception:
                    pres = last_preq
            elif getattr(last, 'presentation', None):
                try:
                    pres = last.presentation
                    for sup in pres.supervisors.all():
                        candidate_ids.add(str(sup.id))
                except Exception:
                    pres = last.presentation

            from apps.users.models import CustomUser
            from apps.presentations.serializers import BasicUserSerializer

            # If we have no candidate ids and no presentation supervisors, return empty
            if not candidate_ids and pres is None:
                return Response({'presentation': None, 'supervisors': [], 'last_selected_supervisor': None})

            # If we have a linked presentation, prefer the supervisors from that relation
            if pres is not None:
                users_qs = pres.supervisors.all()
            else:
                users_qs = CustomUser.objects.filter(id__in=list(candidate_ids))

            # Extract last selected supervisor id from the last form's data (if present)
            last_selected = None
            try:
                ls = data.get('selected_supervisor') or data.get('selected') or data.get('selected_supervisors')
                if isinstance(ls, list) and ls:
                    last_selected = str(ls[-1])
                elif ls is not None:
                    last_selected = str(ls)
            except Exception:
                last_selected = None

            # Serialize and return
            response = {
                'presentation': {
                    'id': pres.id,
                    'research_title': getattr(pres, 'research_title', '')
                } if pres is not None else None,
                'supervisors': BasicUserSerializer(users_qs, many=True).data,
                'last_selected_supervisor': last_selected
            }
            try:
                print('last_supervisors response:', response)
            except Exception:
                pass
            return Response(response)
        except Exception:
            return Response({'supervisors': []})

    def create(self, request, *args, **kwargs):
        """Override create to provide clearer server-side logging on bad requests."""
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        if not serializer.is_valid():
            try:
                print('FormViewSet.create: validation failed for user', getattr(request.user, 'id', None))
                print('Request data snapshot:', request.data)
                print('Serializer errors:', serializer.errors)
            except Exception as e:
                print('Error logging create validation failure:', e)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # If valid, proceed with default handling (will call perform_create)
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Return a form instance and augment the response with supervisor details

        This performs a backend query for any supervisor id(s) stored in the
        form's JSON `data` so the frontend can display human-friendly names
        and titles instead of raw ids.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        resp_data = serializer.data

        try:
            form_data = (getattr(instance, 'data', {}) or {})

            # Look for various keys that may contain selected supervisor id(s)
            sel = None
            for k in ('selected_supervisor', 'selected', 'selected_supervisors', 'supervisors', 'selected_ids'):
                if k in form_data and form_data[k] is not None:
                    sel = form_data[k]
                    break

            ids = []
            if sel is not None:
                if isinstance(sel, list):
                    for v in sel:
                        try:
                            ids.append(str(v))
                        except Exception:
                            continue
                else:
                    try:
                        ids.append(str(sel))
                    except Exception:
                        pass

            # If we found any ids, query and serialize those users
            if ids:
                from apps.users.models import CustomUser
                from apps.presentations.serializers import BasicUserSerializer

                users_qs = CustomUser.objects.filter(id__in=ids)
                resp_data['supervisors'] = BasicUserSerializer(users_qs, many=True).data
                # also include a single detail field for convenience
                first = users_qs.first()
                if first:
                    resp_data['selected_supervisor_detail'] = BasicUserSerializer(first).data
        except Exception:
            # Non-fatal: return base serialized data if augmentation fails
            pass

        return Response(resp_data)


class SelfAssessmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Scholar's Self Assessment Progress Reports.
    
    This viewset handles CRUD operations for self-assessment forms which 
    include research objectives, presentations, linkages, and publications tracking.
    """

    serializer_class = FormSerializer
    permission_classes = [IsAuthenticated]
    queryset = PresentationForm.objects.filter(name='self_assessment').select_related('created_by')

    def get_queryset(self):
        user = self.request.user
        qs = PresentationForm.objects.filter(name='self_assessment').select_related('created_by')
        
        # Admin and coordinator can see all
        if user.user_groups.filter(name__in=['admin', 'coordinator']).exists():
            return qs
        
        # Others see only their own assessments
        return qs.filter(created_by=user)

    def perform_create(self, serializer):
        # Set the form name to 'self_assessment' for filtering
        instance = serializer.save(
            created_by=self.request.user,
            name='self_assessment',
            form_role='student'
        )

    def perform_update(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        """Ensure required Form fields are populated before validation."""
        mutable = request.data.copy()

        # Map legacy payloads that send `form_type` instead of `name`
        if not mutable.get('name') and mutable.get('form_type'):
            mutable['name'] = mutable.get('form_type')

        # Force correct name and role for self-assessments
        mutable['name'] = 'self_assessment'
        if not mutable.get('form_role'):
            mutable['form_role'] = 'student'

        # Ensure `data` is present for the Form serializer
        if 'data' not in mutable and 'payload' in mutable:
            mutable['data'] = mutable.get('payload')

        # Rebuild request with updated data
        request._full_data = mutable
        return super().create(request, *args, **kwargs)


class ProposalEvaluationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Master's Research Proposal Evaluation Forms.
    
    This viewset handles CRUD operations for proposal evaluation forms which 
    are filled by examiners to assess research proposals.
    
    Permission: Only users with 'evaluate_proposals' permission or examiners can access.
    """

    serializer_class = FormSerializer
    permission_classes = [IsAuthenticated]
    queryset = PresentationForm.objects.filter(name='proposal_evaluation').select_related('created_by')

    def get_queryset(self):
        user = self.request.user
        qs = PresentationForm.objects.filter(name='proposal_evaluation').select_related('created_by')
        
        # Admin can see all
        if user.user_groups.filter(name='admin').exists():
            return qs
        
        # Coordinator can see all
        if user.user_groups.filter(name='coordinator').exists():
            return qs
        
        # Users with evaluate_proposals permission can see their own
        # Check if user has evaluate_proposals permission in any of their groups
        user_groups = user.user_groups.all()
        has_permission = False
        for group in user_groups:
            perms = group.permissions or []
            if 'evaluate_proposals' in perms:
                has_permission = True
                break
        
        # Examiners and those with permission see only their own evaluations
        if user.user_groups.filter(name='examiner').exists() or has_permission:
            return qs.filter(created_by=user)
        
        # Others see nothing
        return qs.none()

    def perform_create(self, serializer):
        # Set the form name to 'proposal_evaluation' for filtering
        instance = serializer.save(
            created_by=self.request.user,
            name='proposal_evaluation',
            form_role='examiner'
        )

    def perform_update(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        """Ensure required Form fields are populated before validation."""
        mutable = request.data.copy()

        # Force correct name and role for proposal evaluations
        mutable['name'] = 'proposal_evaluation'
        if not mutable.get('form_role'):
            mutable['form_role'] = 'examiner'

        # Ensure `data` is present for the Form serializer
        if 'data' not in mutable and 'payload' in mutable:
            mutable['data'] = mutable.get('payload')

        # Rebuild request with updated data
        request._full_data = mutable
        return super().create(request, *args, **kwargs)


class PhdProposalEvaluationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing PhD Research Proposal Evaluation Forms.
    
    This viewset handles CRUD operations for PhD proposal evaluation forms which 
    are filled by examiners to assess PhD research proposals.
    
    Permission: Only users with 'evaluate_phd_proposals' permission or examiners can access.
    """

    serializer_class = FormSerializer
    permission_classes = [IsAuthenticated]
    queryset = PresentationForm.objects.filter(name='phd_proposal_evaluation').select_related('created_by')

    def get_queryset(self):
        user = self.request.user
        qs = PresentationForm.objects.filter(name='phd_proposal_evaluation').select_related('created_by')
        
        # Admin can see all
        if user.user_groups.filter(name='admin').exists():
            return qs
        
        # Coordinator can see all
        if user.user_groups.filter(name='coordinator').exists():
            return qs
        
        # Users with evaluate_phd_proposals permission can see their own
        # Check if user has evaluate_phd_proposals permission in any of their groups
        user_groups = user.user_groups.all()
        has_permission = False
        for group in user_groups:
            perms = group.permissions or []
            if 'evaluate_phd_proposals' in perms:
                has_permission = True
                break
        
        # Examiners and those with permission see only their own evaluations
        if user.user_groups.filter(name='examiner').exists() or has_permission:
            return qs.filter(created_by=user)
        
        # Others see nothing
        return qs.none()

    def perform_create(self, serializer):
        # Set the form name to 'phd_proposal_evaluation' for filtering
        instance = serializer.save(
            created_by=self.request.user,
            name='phd_proposal_evaluation',
            form_role='examiner'
        )

    def perform_update(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        """Ensure required Form fields are populated before validation."""
        mutable = request.data.copy()

        # Force correct name and role for PhD proposal evaluations
        mutable['name'] = 'phd_proposal_evaluation'
        if not mutable.get('form_role'):
            mutable['form_role'] = 'examiner'

        # Ensure `data` is present for the Form serializer
        if 'data' not in mutable and 'payload' in mutable:
            mutable['data'] = mutable.get('payload')

        # Rebuild request with updated data
        request._full_data = mutable
        return super().create(request, *args, **kwargs)


class PhdAssessmentItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing PhD Assessment Items.
    
    This viewset allows admins to manage the assessment criteria items
    used in PhD Research Proposal Evaluation Forms.
    
    - GET /phd-assessment-items/ - List all items (filtered by is_active for non-admins)
    - GET /phd-assessment-items/?all=true - List all items including inactive (admin only)
    - POST /phd-assessment-items/ - Create new item (admin only)
    - PUT /phd-assessment-items/{id}/ - Update item (admin only)
    - DELETE /phd-assessment-items/{id}/ - Delete item (admin only)
    """
    
    serializer_class = PhdAssessmentItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = PhdAssessmentItem.objects.all()
        
        # Admin can see all items (always, for CRUD operations)
        if user.user_groups.filter(name='admin').exists():
            return queryset
        
        # Non-admins only see active items
        return queryset.filter(is_active=True)
    
    def check_admin_permission(self):
        """Check if user is admin for write operations"""
        user = self.request.user
        if not user.user_groups.filter(name='admin').exists():
            return Response(
                {'error': 'Only administrators can modify assessment items'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    def create(self, request, *args, **kwargs):
        """Create a new assessment item (admin only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update an assessment item (admin only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update an assessment item (admin only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete an assessment item (admin only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def total_score(self, request):
        """Get the total maximum score of all active assessment items"""
        from django.db.models import Sum
        total = PhdAssessmentItem.objects.filter(is_active=True).aggregate(
            total=Sum('max_score')
        )['total'] or 0
        return Response({'total_max_score': total})
