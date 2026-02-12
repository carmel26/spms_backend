import logging
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.contrib.contenttypes.models import ContentType
from apps.notifications.models import Notification, ReminderLog
from apps.users.models import CustomUser


logger = logging.getLogger(__name__)


# -------------------------------
# Helper function for creating notifications
# -------------------------------
def create_notification(recipient, title, message, notification_type, obj=None, related_user=None, priority=0):
    """
    Unified helper to create a notification for a user.
    
    Args:
        recipient: CustomUser instance
        title: Notification title
        message: Notification message
        notification_type: string, one of Notification.NOTIFICATION_TYPE_CHOICES
        obj: optional object to link via GenericForeignKey
        related_user: optional related user
        priority: integer
    Returns:
        Notification object
    """
    kwargs = {
        'recipient': recipient,
        'title': title,
        'message': message,
        'notification_type': notification_type,
        'related_user': related_user,
        'priority': priority
    }
    if obj:
        kwargs['content_type'] = ContentType.objects.get_for_model(obj)
        kwargs['object_id'] = obj.id
    return Notification.objects.create(**kwargs)


# -------------------------------
# Honorific helper
# -------------------------------
def _get_honorific(user):
    if not user:
        return 'Mr/Ms'

    for attr in ('title_display', 'title', 'academic_title', 'honorific'):
        val = getattr(user, attr, None)
        if val:
            s = str(val).strip()
            if s.lower().startswith('dr') and not s.endswith('.'):
                return 'Dr.'
            if s.lower().startswith('prof') and not s.endswith('.'):
                return 'Prof.'
            return s

    try:
        full = user.get_full_name() if callable(getattr(user, 'get_full_name', None)) else ''
    except Exception:
        full = ''

    if full:
        for p in ('Dr.', 'Dr', 'Prof.', 'Prof', 'Professor'):
            if full.startswith(p):
                if p.startswith('Dr'):
                    return 'Dr.'
                return 'Prof.'

    return 'Mr/Ms'


# -------------------------------
# Notification creators
# -------------------------------

def create_notification_for_students(title, message, notification_type, obj=None, related_user=None, priority=0):
    """
    Create notifications for all active students.
    """
    students = CustomUser.objects.filter(
        is_active=True,
        studentprofile__isnull=False,
        studentprofile__is_active_student=True
    ).distinct()

    notifications = []
    for student in students:
        n = create_notification(
            recipient=student,
            title=title,
            message=message,
            notification_type=notification_type,
            obj=obj,
            related_user=related_user,
            priority=priority
        )
        notifications.append(n)
    return notifications


def create_notification_for_user(recipient, title, message, notification_type, obj=None, related_user=None, priority=0):
    """
    Create a notification for a single student user.
    """
    if not hasattr(recipient, 'studentprofile') or not recipient.studentprofile.is_active_student:
        return None

    return create_notification(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        obj=obj,
        related_user=related_user,
        priority=priority
    )


# -------------------------------
# Presentation-specific notifications
# -------------------------------
def send_presentation_notification(presentation_request, notification_type, custom_message=None):
    titles = {
        'presentation_accepted': 'Presentation Request Accepted',
        'presentation_declined': 'Presentation Request Declined',
        'date_changed': 'Presentation Date Changed',
        'time_warning': 'Presentation Starting Soon',
        'assessment_submitted': 'Assessment Submitted',
        'presentation_completed': 'Presentation Completed',
        'presentation_reminder': 'Presentation Reminder'
    }
    title = titles.get(notification_type, 'Presentation Update')
    message = custom_message or f'Update on your presentation request: {presentation_request.research_title}'
    return create_notification_for_user(
        recipient=presentation_request.student,
        title=title,
        message=message,
        notification_type=notification_type,
        obj=presentation_request
    )


def send_examiner_assignment_notification(examiner, presentation_request, assigned_by):
    title = 'New Examiner Assignment'
    message = f'You have been assigned as an examiner for the presentation: "{presentation_request.research_title}" by {presentation_request.student.get_full_name()}. Please review and respond.'

    n = create_notification(
        recipient=examiner,
        title=title,
        message=message,
        notification_type='examiner_assignment',
        obj=presentation_request,
        related_user=assigned_by
    )

    # Email sending (best-effort)
    _send_email(recipient=examiner, subject=title, message=message, template_prefix='examiner_assignment', context={
        'presentation': presentation_request,
        'examiner': examiner,
        'assigned_by': assigned_by,
        'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
        'honorific': _get_honorific(examiner)
    })

    return n


def send_examiner_response_notification(coordinator, presentation_request, examiner, status, decline_reason=None):
    if status == 'accepted':
        title = 'Examiner Accepted Assignment'
        message = f'{examiner.get_full_name()} has accepted the examiner assignment for "{presentation_request.research_title}".'
    else:
        title = 'Examiner Declined Assignment - Action Required'
        message = f'{examiner.get_full_name()} has declined the examiner assignment for "{presentation_request.research_title}".'
        if decline_reason:
            message += f'\nReason: {decline_reason}\nPlease assign a different examiner.'

    return create_notification(
        recipient=coordinator,
        title=title,
        message=message,
        notification_type='examiner_assignment',
        obj=presentation_request,
        related_user=examiner
    )


def send_presentation_submitted_notification(presentation_request):
    coordinators = CustomUser.objects.filter(
        user_groups__name='coordinator',
        is_active=True,
        is_approved=True
    ).distinct()

    notifications = []
    for coordinator in coordinators:
        n = create_notification(
            recipient=coordinator,
            title='New Presentation Request',
            message=f'{presentation_request.student.get_full_name()} submitted a new presentation: "{presentation_request.research_title}"',
            notification_type='presentation_request',
            obj=presentation_request,
            related_user=presentation_request.student
        )
        notifications.append(n)
    return notifications


def send_presentation_completed_notification(presentation_request, coordinator):
    notifications = []

    # Notify student
    n1 = create_notification(
        recipient=presentation_request.student,
        title='Presentation Completed',
        message=f'Your presentation "{presentation_request.research_title}" has been completed.',
        notification_type='presentation_completed',
        obj=presentation_request
    )
    notifications.append(n1)

    # Notify coordinator
    n2 = create_notification(
        recipient=coordinator,
        title='Presentation Completed',
        message=f'The presentation "{presentation_request.research_title}" by {presentation_request.student.get_full_name()} has been completed.',
        notification_type='presentation_completed',
        obj=presentation_request,
        related_user=presentation_request.student
    )
    notifications.append(n2)

    return notifications

# -------------------------------
def send_supervisor_assignment_notification(supervisor, presentation_request, assigned_by):
    """
    Notify a supervisor that they have been assigned to a student's presentation.
    """
    title = "Supervisor Assignment"
    message = (
        f"You have been assigned as a supervisor for the presentation: "
        f"'{presentation_request.research_title}' by {presentation_request.student.get_full_name()}."
    )

    notification = create_notification(
        recipient=supervisor,
        title=title,
        message=message,
        notification_type='supervisor_assignment',
        obj=presentation_request,
        related_user=assigned_by
    )

    # Optional: send email
    _send_email(
        recipient=supervisor,
        subject=title,
        message=message,
        template_prefix='supervisor_assignment',
        context={
            'presentation': presentation_request,
            'supervisor': supervisor,
            'assigned_by': assigned_by,
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
            'honorific': _get_honorific(supervisor)
        }
    )

    return notification

# -------------------------------
def send_session_moderator_assignment_notification(moderator, session, assigned_by):
    """
    Notify a session moderator that they have been assigned to a session.
    """
    title = "Session Moderator Assignment"
    message = (
        f"You have been assigned as a moderator for the session: "
        f"'{session.title}' by {session.presenter.get_full_name()}."
    )

    notification = create_notification(
        recipient=moderator,
        title=title,
        message=message,
        notification_type='session_moderator_assignment',
        obj=session,
        related_user=assigned_by
    )

    # Optional: send email
    _send_email(
        recipient=moderator,
        subject=title,
        message=message,
        template_prefix='session_moderator_assignment',
        context={
            'session': session,
            'moderator': moderator,
            'assigned_by': assigned_by,
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
            'honorific': _get_honorific(moderator)
        }
    )

    return notification


# -------------------------------

def send_presentation_time_reminder(presentation_request, minutes_before=30):
    """
    Send a reminder notification AND email to a single recipient (the student).
    Kept for backward-compatibility; prefer send_presentation_reminders_to_all_actors().
    """
    return _send_reminder_to_recipient(
        presentation_request,
        recipient=presentation_request.student,
        role_label='Presenter',
        minutes_before=minutes_before,
    )


def send_presentation_reminders_to_all_actors(presentation_request, minutes_before=30):
    """
    Send reminder notifications + emails to **all** actors linked to this
    presentation: student, supervisors, session moderator, and examiners.
    """
    results = []

    # 1. Student (presenter)
    results.append(
        _send_reminder_to_recipient(
            presentation_request,
            recipient=presentation_request.student,
            role_label='Presenter',
            minutes_before=minutes_before,
        )
    )

    # 2. Supervisors (from assignment)
    try:
        assignment = presentation_request.assignment
        for sa in assignment.supervisor_assignments.select_related('supervisor').all():
            results.append(
                _send_reminder_to_recipient(
                    presentation_request,
                    recipient=sa.supervisor,
                    role_label='Supervisor',
                    minutes_before=minutes_before,
                )
            )
    except Exception:
        logger.debug('No assignment / supervisors for presentation %s', presentation_request.id)

    # 3. Session moderator
    try:
        moderator = presentation_request.assignment.session_moderator
        if moderator:
            results.append(
                _send_reminder_to_recipient(
                    presentation_request,
                    recipient=moderator,
                    role_label='Session Moderator',
                    minutes_before=minutes_before,
                )
            )
    except Exception:
        logger.debug('No moderator for presentation %s', presentation_request.id)

    # 4. Examiners (from assignment)
    try:
        assignment = presentation_request.assignment
        for ea in assignment.examiner_assignments.select_related('examiner').all():
            results.append(
                _send_reminder_to_recipient(
                    presentation_request,
                    recipient=ea.examiner,
                    role_label='Examiner',
                    minutes_before=minutes_before,
                )
            )
    except Exception:
        logger.debug('No examiners for presentation %s', presentation_request.id)

    return results


# ---- internal helper to avoid duplication ----
def _send_reminder_to_recipient(presentation_request, recipient, role_label, minutes_before):
    """
    Create an in-app notification, log the reminder, and send an email to ONE
    recipient using the ``presentation_reminder`` template.
    """
    title = "Presentation Starting Soon"
    message = (
        f"The presentation '{presentation_request.research_title}' "
        f"will start in {minutes_before} minutes.  You are listed as: {role_label}."
    )

    # In-app notification (uses create_notification directly so it works for
    # non-student recipients too — create_notification_for_user guards on
    # studentprofile which staff don't have).
    notification = create_notification(
        recipient=recipient,
        title=title,
        message=message,
        notification_type='time_warning',
        obj=presentation_request,
    )

    # Reminder log
    ReminderLog.objects.create(
        recipient=recipient,
        presentation=presentation_request,
        minutes_before=minutes_before,
        channel='email',
        status='sent',
    )

    # Email (best-effort)
    try:
        _send_email(
            recipient=recipient,
            subject=title,
            message=message,
            template_prefix='presentation_reminder',
            context={
                'presentation': presentation_request,
                'recipient': recipient,
                'role_label': role_label,
                'minutes_before': minutes_before,
                'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:4200'),
                'honorific': _get_honorific(recipient),
            },
        )
    except Exception:
        logger.exception(
            'Failed to send presentation reminder email for presentation id %s to %s',
            getattr(presentation_request, 'id', None),
            getattr(recipient, 'email', None),
        )

    return notification

# -------------------------------
# Helper for sending emails
# -------------------------------
def _send_email(recipient, subject, message, template_prefix=None, context=None):
    try:
        logger.debug('Preparing email: recipient=%s subject=%s template=%s', getattr(recipient, 'email', None), subject, template_prefix)
        html_body = None
        text_body = message

        if template_prefix and context:
            try:
                html_body = render_to_string(f'emails/{template_prefix}.html', context)
            except Exception:
                pass
            try:
                text_body = render_to_string(f'emails/{template_prefix}.txt', context)
            except Exception:
                text_body = message

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@spms.edu')
        to_emails = [recipient.email] if getattr(recipient, 'email', None) else []

        if not to_emails:
            logger.warning('Not sending email: recipient has no email address (recipient=%s)', getattr(recipient, 'id', None))
            return

        logger.debug('Email from=%s to=%s; html_body=%s text_body_len=%d', from_email, to_emails, bool(html_body), len(text_body or ''))
        msg = EmailMultiAlternatives(subject, text_body, from_email, to_emails)
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info('Email sent to %s subject=%s', to_emails, subject)
    except Exception as e:
        logger.exception('Failed to send email to %s: %s', getattr(recipient, 'email', None), e)
