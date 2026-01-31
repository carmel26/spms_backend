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

        # Supervisors should see forms assigned to them (either via the linked Presentation
        # or via selected_supervisor(s) stored in the JSON `data` field). Students should
        # continue to see their own created forms.
        if user.user_groups.filter(name='supervisor').exists():
            # Build a queryset that includes forms where:
            # - created_by is the user (safe)
            # - the linked presentation has this user in its supervisors relation
            # - OR the JSON data contains a selected_supervisor(s) equal to this user's id
            try:
                from django.db.models import Q
                uid = int(user.id)
                q = Q(created_by=user) | Q(presentation__supervisors__id=uid)

                # JSONField lookups - try a couple of common shapes. These lookups may
                # depend on the DB backend (Postgres supports JSONField contains lookups).
                # We check for array contains and string/int equality where possible.
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
                    q |= Q(data__selected_supervisor__contains=str(uid))
                except Exception:
                    pass

                return qs.filter(q).distinct()
            except Exception:
                # Fallback: return forms created by the user only
                return qs.filter(created_by=user)

        # Default: students and other roles see only forms they created
        return qs.filter(created_by=user)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)

        # If the form payload included a selected supervisor, notify them to
        # complete the supervisor part of the form (Part B).
        try:
            data = getattr(instance, 'data', {}) or {}
            sel = data.get('selected_supervisor') or data.get('selected_supervisors')
            if sel:
                # sel might be a single id or a list
                from apps.users.models import CustomUser
                from apps.notifications.models import Notification

                ids = sel if isinstance(sel, list) else [sel]
                for sid in ids:
                    try:
                        sup = CustomUser.objects.get(id=int(sid))
                    except Exception:
                        sup = None
                    if sup:
                        try:
                            # Prefer sending the backend's supervisor assignment email/template when we have
                            # a linked PresentationRequest. This sends an email using the same design as
                            # other supervisor assignment flows and is best-effort.
                            if getattr(instance, 'presentation', None):
                                send_supervisor_assignment_notification(sup, instance.presentation, assigned_by=instance.created_by)
                            else:
                                # No presentation associated: send a simple email using same template files
                                try:
                                    from django.conf import settings
                                    from django.template.loader import render_to_string
                                    from django.core.mail import EmailMultiAlternatives
                                    import logging

                                    logger = logging.getLogger(__name__)
                                    title = 'Action required: Complete Part B'
                                    message = f'{instance.created_by.get_full_name()} has submitted a Research Progress Report and requested supervisor input. Please log in to the system to complete your part.'
                                    context = {
                                        'presentation': None,
                                        'recipient': sup,
                                        'assigned_by': instance.created_by,
                                        'role_label': 'Supervisor',
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
                                    to_emails = [sup.email] if getattr(sup, 'email', None) else []
                                    if to_emails:
                                        msg = EmailMultiAlternatives(title, text_body, from_email, to_emails)
                                        if html_body:
                                            msg.attach_alternative(html_body, 'text/html')
                                        try:
                                            logger.info('Attempting to send supervisor email (form create) to %s', to_emails)
                                            msg.send(fail_silently=False)
                                            logger.info('Supervisor email (form create) sent to %s', to_emails)
                                        except Exception as send_err:
                                            logger.exception('Failed to send supervisor email from form create: %s', send_err)
                                except Exception:
                                    pass
                        except Exception:
                            pass
        except Exception:
            # Non-fatal: don't block form creation on notification failures
            pass

    def perform_update(self, serializer):
        # Preserve created_by
        instance = serializer.save()
        # If supervisor selection changed on update, optionally notify newly selected supervisors
        try:
            data = getattr(instance, 'data', {}) or {}
            sel = data.get('selected_supervisor') or data.get('selected_supervisors')
            if sel:
                from apps.users.models import CustomUser
                from apps.notifications.models import Notification
                ids = sel if isinstance(sel, list) else [sel]
                for sid in ids:
                    try:
                        sup = CustomUser.objects.get(id=int(sid))
                    except Exception:
                        sup = None
                    if sup:
                        try:
                            if getattr(instance, 'presentation', None):
                                send_supervisor_assignment_notification(sup, instance.presentation, assigned_by=instance.created_by)
                            else:
                                # Send email fallback when presentation is not linked
                                try:
                                    from django.conf import settings
                                    from django.template.loader import render_to_string
                                    from django.core.mail import EmailMultiAlternatives
                                    import logging

                                    logger = logging.getLogger(__name__)
                                    title = 'Action required: Complete Part B'
                                    message = f'{instance.created_by.get_full_name()} has updated a Research Progress Report and requested supervisor input. Please log in to the system to complete your part.'
                                    context = {
                                        'presentation': None,
                                        'recipient': sup,
                                        'assigned_by': instance.created_by,
                                        'role_label': 'Supervisor',
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
                                    to_emails = [sup.email] if getattr(sup, 'email', None) else []
                                    if to_emails:
                                            msg = EmailMultiAlternatives(title, text_body, from_email, to_emails)
                                            if html_body:
                                                msg.attach_alternative(html_body, 'text/html')
                                            try:
                                                logger.info('Attempting to send supervisor email (form update) to %s', to_emails)
                                                msg.send(fail_silently=False)
                                                logger.info('Supervisor email (form update) sent to %s', to_emails)
                                            except Exception as send_err:
                                                logger.exception('Failed to send supervisor email from form update: %s', send_err)
                                except Exception:
                                    pass
                        except Exception:
                            pass
        except Exception:
            pass

        return instance

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
                # Try several ways to extract an integer id from x
                try:
                    if x is None:
                        return None
                    if isinstance(x, int):
                        return int(x)
                    if isinstance(x, str):
                        # attempt to parse an integer inside the string
                        import re
                        m = re.search(r"(\d+)", x)
                        if m:
                            return int(m.group(1))
                        return None
                    if isinstance(x, dict):
                        for k in ('id', 'value', 'user_id', 'supervisor_id'):
                            if k in x and x[k] is not None:
                                try:
                                    return int(x[k])
                                except Exception:
                                    continue
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
                        candidate_ids.add(int(sup.id))
                except Exception:
                    pres = last_preq
            elif getattr(last, 'presentation', None):
                try:
                    pres = last.presentation
                    for sup in pres.supervisors.all():
                        candidate_ids.add(int(sup.id))
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
                    last_selected = int(ls[-1])
                elif ls is not None:
                    # try to coerce
                    last_selected = int(ls)
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
                            ids.append(int(v))
                        except Exception:
                            continue
                else:
                    try:
                        ids.append(int(sel))
                    except Exception:
                        # sometimes the id may be embedded in a string like "user:12"
                        import re
                        m = re.search(r"(\d+)", str(sel))
                        if m:
                            try:
                                ids.append(int(m.group(1)))
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

    def perform_update(self, serializer):
        """Save the instance and ensure supervisor signature fields are persisted

        When supervisors submit Part B we store their input under `data.supervisor_part_b`.
        For convenience and compatibility with some detail views, copy commonly-used
        supervisor signature fields into top-level keys under `data` so they are
        immediately visible without needing to traverse nested objects.
        """
        instance = serializer.save()
        try:
            data = getattr(instance, 'data', {}) or {}
            sup = data.get('supervisor_part_b') or {}
            # Ensure signature_name is set to the connected user's name when supervisor is submitting
            try:
                req_user = getattr(self.request, 'user', None)
                if req_user and sup is not None:
                    has_sig = sup.get('include_signature') or sup.get('signature_hash') or sup.get('signature_signed_at')
                    # build a reasonable display name
                    if not sup.get('signature_name') and has_sig:
                        user_name = None
                        try:
                            user_name = getattr(req_user, 'full_name_with_title', None)
                        except Exception:
                            user_name = None
                        if not user_name:
                            fn = getattr(req_user, 'first_name', '') or ''
                            ln = getattr(req_user, 'last_name', '') or ''
                            user_name = f"{fn} {ln}".strip() or getattr(req_user, 'username', None)
                        if user_name:
                            sup['signature_name'] = user_name
            except Exception:
                pass

            if sup:
                changed = False
                # prefer explicit supervisor signature keys inside supervisor_part_b
                sig_hash = sup.get('signature_hash') or sup.get('supervisor_signature_hash')
                sig_name = sup.get('signature_name') or sup.get('supervisor_name')
                sig_at = sup.get('signature_signed_at') or sup.get('supervisor_signed_at')

                if sig_hash:
                    # mirror under a stable top-level key
                    if data.get('signature_hash_supervisor') != sig_hash:
                        data['signature_hash_supervisor'] = sig_hash
                        changed = True
                if sig_name:
                    if data.get('signature_name_supervisor') != sig_name:
                        data['signature_name_supervisor'] = sig_name
                        changed = True
                if sig_at:
                    if data.get('signature_signed_at_supervisor') != sig_at:
                        data['signature_signed_at_supervisor'] = sig_at
                        changed = True

                if changed:
                    instance.data = data
                    instance._current_user = getattr(self.request, 'user', None)
                    instance.save()
        except Exception:
            # Non-fatal: don't block the update if mirroring fails
            pass
        return instance

