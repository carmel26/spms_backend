"""
Utility functions for notifications
"""
from apps.notifications.models import Notification


def _get_honorific(user):
    """Return a short honorific for a user (e.g. 'Dr.', 'Prof.', 'Mr/Ms').

    Preference order:
      - common title fields if present on the user object
      - prefix in full name (e.g. 'Dr', 'Prof')
      - fallback to 'Mr/Ms'
    """
    if not user:
        return 'Mr/Ms'

    # Common attribute names that may store a title
    for attr in ('title_display', 'title', 'academic_title', 'honorific'):
        val = getattr(user, attr, None)
        if val:
            # normalize
            s = str(val).strip()
            if s:
                # ensure trailing dot for common academic titles
                if s.lower().startswith('dr') and not s.endswith('.'):
                    return 'Dr.'
                if s.lower().startswith('prof') and not s.endswith('.'):
                    return 'Prof.'
                return s

    # Try to detect prefix in full name
    try:
        full = user.get_full_name() if callable(getattr(user, 'get_full_name', None)) else ''
    except Exception:
        full = ''

    if full:
        for p in ('Dr.', 'Dr', 'Prof.', 'Prof', 'Professor'):
            if full.startswith(p):
                # normalize
                if p.startswith('Dr'):
                    return 'Dr.'
                return 'Prof.'

    # Fallback
    return 'Mr/Ms'


def create_notification_for_students(title, message, notification_type, **kwargs):
    """
    Create notifications only for users with student profile
    
    Args:
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        **kwargs: Additional fields (presentation, related_user, priority, etc.)
    
    Returns:
        List of created Notification objects
    """
    from apps.users.models import CustomUser
    
    # Get all active students
    students = CustomUser.objects.filter(
        is_active=True,
        studentprofile__isnull=False,
        studentprofile__is_active_student=True
    ).distinct()
    
    notifications = []
    for student in students:
        notification = Notification.objects.create(
            recipient=student,
            title=title,
            message=message,
            notification_type=notification_type,
            **kwargs
        )
        notifications.append(notification)
    
    return notifications


def create_notification_for_user(recipient, title, message, notification_type, **kwargs):
    """
    Create notification for a specific user (only if they're a student)
    
    Args:
        recipient: CustomUser instance
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        **kwargs: Additional fields (presentation, related_user, priority, etc.)
    
    Returns:
        Notification object or None if user is not a student
    """
    # Check if recipient is a student
    if not hasattr(recipient, 'studentprofile'):
        return None
    
    if not recipient.studentprofile.is_active_student:
        return None
    
    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        **kwargs
    )
    
    return notification


def send_presentation_notification(presentation_request, notification_type, custom_message=None):
    """
    Send presentation-related notifications to the student who created the request
    
    Args:
        presentation_request: PresentationRequest instance
        notification_type: Type of notification
        custom_message: Optional custom message
    
    Returns:
        Notification object or None
    """
    titles = {
        'presentation_accepted': 'Presentation Request Accepted',
        'presentation_declined': 'Presentation Request Declined',
        'date_changed': 'Presentation Date Changed',
        'time_warning': 'Presentation Starting Soon',
        'assessment_submitted': 'Assessment Submitted',
        'presentation_completed': 'Presentation Completed',
    }
    
    title = titles.get(notification_type, 'Presentation Update')
    message = custom_message or f'Update on your presentation request: {presentation_request.research_title}'
    
    return create_notification_for_user(
        recipient=presentation_request.student,
        title=title,
        message=message,
        notification_type=notification_type,
        presentation=presentation_request
    )


def send_examiner_assignment_notification(examiner, presentation_request, assigned_by):
    """
    Send notification to examiner when they are assigned to a presentation
    
    Args:
        examiner: CustomUser instance (examiner)
        presentation_request: PresentationRequest instance
        assigned_by: CustomUser who assigned the examiner (usually coordinator)
    
    Returns:
        Notification object
    """
    title = 'New Examiner Assignment'
    message = f'You have been assigned as an examiner for the presentation: "{presentation_request.research_title}" by {presentation_request.student.get_full_name()}. Please review and respond to this assignment.'
    
    # Create in-app notification
    try:
        notification = Notification.objects.create(
            recipient=examiner,
            title=title,
            message=message,
            notification_type='examiner_assignment',
            presentation=presentation_request,
            related_user=assigned_by
        )
    except Exception:
        notification = None

    # Send email using HTML template (best-effort). Log exceptions so failures are visible.
    try:
        import logging
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives

        logger = logging.getLogger(__name__)

        subject = title

        # Prepare context for templates
        context = {
            'presentation': presentation_request,
            'examiner': examiner,
            'assigned_by': assigned_by,
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
            'honorific': _get_honorific(examiner)
        }

        # Render text and HTML versions
        try:
            html_body = render_to_string('emails/examiner_assignment.html', context)
        except Exception:
            html_body = None

        try:
            text_body = render_to_string('emails/examiner_assignment.txt', context)
        except Exception:
            # Fallback plain text
            body_lines = [message, '', 'Presentation details:']
            body_lines.append(f"Title: {presentation_request.research_title}")
            body_lines.append(f"Student: {presentation_request.student.get_full_name()}")
            if getattr(presentation_request, 'proposed_date', None):
                body_lines.append(f"Proposed date: {presentation_request.proposed_date}")
            body_lines.append('')
            body_lines.append('Please log in to the system to view the assignment and respond.')
            text_body = '\n'.join(body_lines)

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
        to_emails = [ex.email] if (ex := getattr(examiner, 'email', None)) else []

        if to_emails:
            msg = EmailMultiAlternatives(subject, text_body, from_email, to_emails)
            if html_body:
                msg.attach_alternative(html_body, 'text/html')
            try:
                msg.send(fail_silently=False)
            except Exception as send_err:
                logger.exception('Failed to send examiner assignment email: %s', send_err)
    except Exception:
        # Ensure notification creation does not break the flow
        pass

    return notification


def send_examiner_response_notification(coordinator, presentation_request, examiner, status, decline_reason=None):
    """
    Send notification to coordinator when examiner accepts or declines an assignment
    
    Args:
        coordinator: CustomUser instance (coordinator)
        presentation_request: PresentationRequest instance
        examiner: CustomUser who responded to the assignment
        status: 'accepted' or 'declined'
        decline_reason: Reason for declining (if declined)
    
    Returns:
        Notification object
    """
    if status == 'accepted':
        title = 'Examiner Accepted Assignment'
        message = f'{examiner.get_full_name()} has accepted the examiner assignment for the presentation: "{presentation_request.research_title}" by {presentation_request.student.get_full_name()}.'
    else:  # declined
        title = 'Examiner Declined Assignment - Action Required'
        message = f'{examiner.get_full_name()} has declined the examiner assignment for the presentation: "{presentation_request.research_title}" by {presentation_request.student.get_full_name()}.'
        if decline_reason:
            message += f'\n\nReason: {decline_reason}'
        message += '\n\nPlease assign a different examiner to this presentation.'
    
    return Notification.objects.create(
        recipient=coordinator,
        title=title,
        message=message,
        notification_type='examiner_assignment',
        presentation=presentation_request,
        related_user=examiner
    )


def send_presentation_submitted_notification(presentation_request):
    """
    Send notifications to all coordinators when a presentation is submitted
    
    Args:
        presentation_request: PresentationRequest instance
    
    Returns:
        List of Notification objects
    """
    from apps.users.models import CustomUser
    
    # Get all active coordinators
    coordinators = CustomUser.objects.filter(
        user_groups__name='coordinator',
        is_active=True,
        is_approved=True
    ).distinct()
    
    notifications = []
    for coordinator in coordinators:
        notification = Notification.objects.create(
            recipient=coordinator,
            title='New Presentation Request',
            message=f'{presentation_request.student.get_full_name()} has submitted a new presentation request: "{presentation_request.research_title}"',
            notification_type='presentation_request',
            presentation=presentation_request,
            related_user=presentation_request.student
        )
        notifications.append(notification)
    
    return notifications


def send_presentation_completed_notification(presentation_request, coordinator):
    """
    Send notification when all examiners have submitted their assessments
    and the presentation is marked as completed
    
    Args:
        presentation_request: PresentationRequest instance
        coordinator: CustomUser instance (coordinator)
    
    Returns:
        List of Notification objects
    """
    notifications = []
    
    # Notify student
    student_notification = Notification.objects.create(
        recipient=presentation_request.student,
        title='Presentation Completed',
        message=f'Your presentation "{presentation_request.research_title}" has been completed. All examiners have submitted their assessments.',
        notification_type='presentation_completed',
        presentation=presentation_request
    )
    notifications.append(student_notification)
    
    # Notify coordinator
    coordinator_notification = Notification.objects.create(
        recipient=coordinator,
        title='Presentation Completed',
        message=f'The presentation "{presentation_request.research_title}" by {presentation_request.student.get_full_name()} has been completed. All examiners have submitted their assessments.',
        notification_type='presentation_completed',
        presentation=presentation_request,
        related_user=presentation_request.student
    )
    notifications.append(coordinator_notification)
    
    return notifications


def send_presentation_time_reminder(presentation_request, minutes_before=15):
    """
    Send reminder emails and in-app notifications to relevant users
    a specified number of minutes before the scheduled presentation.

    Recipients and role-specific wording:
      - Student (presenter)
      - Assigned examiners
      - Session moderator
      - Supervisors
      - Coordinator(s) (assignment.coordinator)

    Args:
        presentation_request: PresentationRequest instance
        minutes_before: int minutes remaining (default 15)

    Returns:
        List of created Notification objects
    """
    import logging
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.core.mail import EmailMultiAlternatives

    logger = logging.getLogger(__name__)
    notifications = []

    try:
        role_entries = []

        # Student
        if getattr(presentation_request, 'student', None):
            role_entries.append(('Presenter', presentation_request.student))

        # Coordinator & session moderator from assignment
        assignment = getattr(presentation_request, 'assignment', None)
        if assignment:
            if getattr(assignment, 'coordinator', None):
                role_entries.append(('Coordinator', assignment.coordinator))
            if getattr(assignment, 'session_moderator', None):
                role_entries.append(('Session Moderator', assignment.session_moderator))

            # Examiner assignments (ExaminerAssignment)
            try:
                for ea in getattr(assignment, 'examiner_assignments', []).all():
                    if getattr(ea, 'examiner', None):
                        role_entries.append(('Examiner', ea.examiner))
            except Exception:
                # assignment.examiner_assignments may be a queryset or empty
                pass

        # Supervisors (ManyToMany on PresentationRequest)
        try:
            for sup in getattr(presentation_request, 'supervisors', []).all():
                role_entries.append(('Supervisor', sup))
        except Exception:
            pass

        # Remove duplicates by user id
        seen = set()
        unique_entries = []
        for role_label, user in role_entries:
            if not user or not getattr(user, 'is_active', True):
                continue
            uid = getattr(user, 'id', None)
            if uid in seen:
                continue
            seen.add(uid)
            unique_entries.append((role_label, user))

        # Prepare context common
        from apps.notifications.models import ReminderLog

        for role_label, user in unique_entries:
            try:
                title = f'Presentation Reminder — {minutes_before} minutes'
                # role-specific message
                message = f'Reminder: the presentation "{presentation_request.research_title}" is scheduled to start in {minutes_before} minutes.\nPlease be ready.'

                # Create in-app notification
                try:
                    n = Notification.objects.create(
                        recipient=user,
                        title='Presentation Reminder',
                        message=f'{role_label}: {message}',
                        notification_type='presentation_reminder',
                        presentation=presentation_request,
                        related_user=None
                    )
                    notifications.append(n)
                    try:
                        ReminderLog.objects.create(
                            recipient=user,
                            presentation=presentation_request,
                            minutes_before=minutes_before,
                            channel='in_app',
                            status='sent'
                        )
                    except Exception:
                        # If logging fails, don't break flow
                        pass
                except Exception as notif_err:
                    try:
                        ReminderLog.objects.create(
                            recipient=user,
                            presentation=presentation_request,
                            minutes_before=minutes_before,
                            channel='in_app',
                            status='failed',
                            error=str(notif_err)
                        )
                    except Exception:
                        pass

                # Email
                context = {
                    'presentation': presentation_request,
                    'recipient': user,
                    'role_label': role_label,
                    'minutes_before': minutes_before,
                    'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
                        'honorific': _get_honorific(user),
                }

                try:
                    html_body = render_to_string('emails/presentation_reminder.html', context)
                except Exception:
                    html_body = None

                try:
                    text_body = render_to_string('emails/presentation_reminder.txt', context)
                except Exception:
                    text_body = message

                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
                to_emails = [user.email] if getattr(user, 'email', None) else []

                if to_emails:
                    subj = f'[{role_label}] Presentation starts in {minutes_before} minutes'
                    msg = EmailMultiAlternatives(subj, text_body, from_email, to_emails)
                    if html_body:
                        msg.attach_alternative(html_body, 'text/html')
                    try:
                        msg.send(fail_silently=False)
                        try:
                            ReminderLog.objects.create(
                                recipient=user,
                                presentation=presentation_request,
                                minutes_before=minutes_before,
                                channel='email',
                                status='sent'
                            )
                        except Exception:
                            pass
                    except Exception as e:
                        logger.exception('Failed to send presentation reminder to %s: %s', user.email, e)
                        try:
                            ReminderLog.objects.create(
                                recipient=user,
                                presentation=presentation_request,
                                minutes_before=minutes_before,
                                channel='email',
                                status='failed',
                                error=str(e)
                            )
                        except Exception:
                            pass

            except Exception as inner_e:
                logger.exception('Error preparing reminder for user %s: %s', getattr(user, 'id', None), inner_e)

    except Exception as e:
        logger.exception('Failed to send presentation time reminders: %s', e)

    return notifications


def send_supervisor_assignment_notification(supervisor, presentation_request, assigned_by=None):
    """
    Send notification (and email) to a supervisor when they are attached/assigned
    to a presentation request.

    Args:
        supervisor: CustomUser instance (supervisor)
        presentation_request: PresentationRequest instance
        assigned_by: CustomUser who assigned/attached the supervisor (optional)

    Returns:
        Notification object
    """
    title = 'New Supervisor Assignment'
    message = f'You have been assigned as a supervisor for the presentation: "{presentation_request.research_title}" by {presentation_request.student.get_full_name()}.'

    # Do not create an in-app Notification object here; supervisors will
    # view assignments in the notifications bar when they log in. Keep
    # `notification` variable for compatibility but do not persist.
    notification = None

    # Send email (best-effort)
    # Send email using HTML/text templates and log failures
    try:
        import logging
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives

        logger = logging.getLogger(__name__)

        subject = title
        context = {
            'presentation': presentation_request,
            'recipient': supervisor,
            'assigned_by': assigned_by,
            'role_label': 'Supervisor',
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
            'honorific': _get_honorific(supervisor)
        }

        try:
            html_body = render_to_string('emails/examiner_assignment.html', context)
        except Exception:
            html_body = None

        try:
            text_body = render_to_string('emails/examiner_assignment.txt', context)
        except Exception:
            text_body = f"{message}\n\nPlease log in to the system to view the assignment and respond if required."

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
        to_emails = [supervisor.email] if getattr(supervisor, 'email', None) else []

        if to_emails:
            logger.info('Attempting to send supervisor assignment email to %s', to_emails)
            msg = EmailMultiAlternatives(subject, text_body, from_email, to_emails)
            if html_body:
                msg.attach_alternative(html_body, 'text/html')
            try:
                msg.send(fail_silently=False)
                logger.info('Supervisor assignment email sent to %s', to_emails)
            except Exception as send_err:
                logger.exception('Failed to send supervisor assignment email: %s', send_err)
    except Exception:
        pass

    return notification


def send_session_moderator_assignment_notification(moderator, presentation_request, assigned_by=None):
    """
    Notify a session moderator when they are assigned to moderate a presentation.

    Args:
        moderator: CustomUser instance (moderator)
        presentation_request: PresentationRequest instance
        assigned_by: CustomUser who assigned the moderator (optional)

    Returns:
        Notification object or None
    """
    title = 'Assigned as Session Moderator'
    message = f'You have been assigned as the session moderator for the presentation: "{presentation_request.research_title}" by {presentation_request.student.get_full_name()}.'

    try:
        notification = Notification.objects.create(
            recipient=moderator,
            title=title,
            message=message,
            notification_type='session_moderator_assignment',
            presentation=presentation_request,
            related_user=assigned_by
        )
    except Exception:
        notification = None

    # Send email (best-effort)
    try:
        import logging
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives

        logger = logging.getLogger(__name__)

        subject = title
        context = {
            'presentation': presentation_request,
            'recipient': moderator,
            'assigned_by': assigned_by,
            'role_label': 'Session Moderator',
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200')
        }

        try:
            html_body = render_to_string('emails/examiner_assignment.html', context)
        except Exception:
            html_body = None

        try:
            text_body = render_to_string('emails/examiner_assignment.txt', context)
        except Exception:
            text_body = f"{message}\n\nPlease log in to the system to view the session details and the presentation request."

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@localhost'
        to_emails = [moderator.email] if getattr(moderator, 'email', None) else []

        if to_emails:
            msg = EmailMultiAlternatives(subject, text_body, from_email, to_emails)
            if html_body:
                msg.attach_alternative(html_body, 'text/html')
            try:
                msg.send(fail_silently=False)
            except Exception as send_err:
                logger.exception('Failed to send moderator assignment email: %s', send_err)
    except Exception:
        pass

    return notification