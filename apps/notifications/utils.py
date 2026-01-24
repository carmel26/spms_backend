"""
Utility functions for notifications
"""
from apps.notifications.models import Notification


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
    
    return Notification.objects.create(
        recipient=examiner,
        title=title,
        message=message,
        notification_type='examiner_assignment',
        presentation=presentation_request,
        related_user=assigned_by
    )


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