"""
Django signals for tracking model changes in audit logs
"""
from django.db.models.signals import pre_save, post_save, pre_delete, m2m_changed
from django.dispatch import receiver
from django.forms.models import model_to_dict
from .models import CustomUser, UserGroup, SystemSettings, AuditLog


# Import presentation models
try:
    from apps.presentations.models import (
        PresentationRequest, PresentationAssignment,
        ExaminerAssignment, SupervisorAssignment, PresentationSchedule
    )
    PRESENTATION_MODELS_AVAILABLE = True
except ImportError:
    PRESENTATION_MODELS_AVAILABLE = False


# Store original data before save
_pre_save_instances = {}


@receiver(pre_save, sender=SystemSettings)
def capture_settings_before_save(sender, instance, **kwargs):
    """Capture SystemSettings data before it's updated"""
    if instance.pk:  # Only for updates, not creates
        try:
            original = SystemSettings.objects.get(pk=instance.pk)
            _pre_save_instances[f'SystemSettings_{instance.pk}'] = model_to_dict(original)
        except SystemSettings.DoesNotExist:
            pass


@receiver(post_save, sender=SystemSettings)
def log_settings_changes(sender, instance, created, **kwargs):
    """Log SystemSettings changes to audit log"""
    key = f'SystemSettings_{instance.pk}'
    
    if not created and key in _pre_save_instances:
        # Get old and new data
        old_data = _pre_save_instances[key]
        new_data = model_to_dict(instance)
        
        # Find what changed
        changes = {}
        for field, new_value in new_data.items():
            old_value = old_data.get(field)
            if old_value != new_value:
                # Convert to strings for better JSON serialization
                changes[field] = [str(old_value) if old_value is not None else None,
                                  str(new_value) if new_value is not None else None]
        
        # Only log if there are actual changes
        if changes:
            # Get the user from the instance if it was set
            user = getattr(instance, '_current_user', None)
            
            AuditLog.log_action(
                user=user,
                action='UPDATE',
                model_instance=instance,
                description=f'Updated system settings',
                changes=changes,
                success=True
            )
        
        # Clean up
        del _pre_save_instances[key]


@receiver(pre_save, sender=UserGroup)
def capture_usergroup_before_save(sender, instance, **kwargs):
    """Capture UserGroup data before it's updated"""
    if instance.pk:  # Only for updates
        try:
            original = UserGroup.objects.get(pk=instance.pk)
            data = {
                'name': original.name,
                'display_name': original.display_name,
                'description': original.description,
            }
            _pre_save_instances[f'UserGroup_{instance.pk}'] = data
        except UserGroup.DoesNotExist:
            pass


@receiver(post_save, sender=UserGroup)
def log_usergroup_changes(sender, instance, created, **kwargs):
    """Log UserGroup changes to audit log"""
    if created:
        # Log creation
        changes = {
            'name': [None, instance.name],
            'display_name': [None, instance.display_name],
            'description': [None, instance.description or 'N/A'],
        }
        
        AuditLog.log_action(
            user=getattr(instance, '_current_user', None),
            action='CREATE',
            model_instance=instance,
            description=f'Created user group: {instance.display_name}',
            changes=changes,
            success=True
        )
    else:
        # Log update
        key = f'UserGroup_{instance.pk}'
        if key in _pre_save_instances:
            old_data = _pre_save_instances[key]
            
            changes = {}
            if old_data['name'] != instance.name:
                changes['name'] = [old_data['name'], instance.name]
            if old_data['display_name'] != instance.display_name:
                changes['display_name'] = [old_data['display_name'], instance.display_name]
            if old_data['description'] != (instance.description or ''):
                changes['description'] = [old_data['description'], instance.description or 'N/A']
            
            if changes:
                AuditLog.log_action(
                    user=getattr(instance, '_current_user', None),
                    action='UPDATE',
                    model_instance=instance,
                    description=f'Updated user group: {instance.display_name}',
                    changes=changes,
                    success=True
                )
            
            del _pre_save_instances[key]


@receiver(pre_save, sender=CustomUser)
def capture_user_before_save(sender, instance, **kwargs):
    """Capture CustomUser data before it's updated"""
    if instance.pk:  # Only for updates
        try:
            original = CustomUser.objects.get(pk=instance.pk)
            data = {
                'username': original.username,
                'email': original.email,
                'first_name': original.first_name,
                'last_name': original.last_name,
                'title': original.title,
                'phone_number': original.phone_number,
                'is_approved': original.is_approved,
                'is_active': original.is_active,
            }
            _pre_save_instances[f'CustomUser_{instance.pk}'] = data
        except CustomUser.DoesNotExist:
            pass


@receiver(post_save, sender=CustomUser)
def log_user_changes(sender, instance, created, **kwargs):
    """Log CustomUser changes to audit log"""
    if created:
        # Log user creation
        changes = {
            'username': [None, instance.username],
            'email': [None, instance.email],
            'first_name': [None, instance.first_name],
            'last_name': [None, instance.last_name],
            'title': [None, instance.title or 'N/A'],
            'is_approved': [None, instance.is_approved],
        }
        
        AuditLog.log_action(
            user=getattr(instance, '_current_user', None),
            action='CREATE',
            model_instance=instance,
            description=f'Created user: {instance.get_full_name()}',
            changes=changes,
            success=True
        )
    else:
        # Log user update
        key = f'CustomUser_{instance.pk}'
        if key in _pre_save_instances:
            old_data = _pre_save_instances[key]
            
            changes = {}
            for field in ['username', 'email', 'first_name', 'last_name', 'title', 
                          'phone_number', 'is_approved', 'is_active']:
                old_val = old_data.get(field)
                new_val = getattr(instance, field)
                if old_val != new_val:
                    changes[field] = [old_val, new_val]
            
            if changes:
                AuditLog.log_action(
                    user=getattr(instance, '_current_user', None),
                    action='UPDATE',
                    model_instance=instance,
                    description=f'Updated user: {instance.get_full_name()}',
                    changes=changes,
                    success=True
                )
            
            del _pre_save_instances[key]


# ==================== PRESENTATION MODELS ====================

if PRESENTATION_MODELS_AVAILABLE:
    
    @receiver(pre_save, sender=PresentationRequest)
    def capture_presentation_before_save(sender, instance, **kwargs):
        """Capture PresentationRequest data before it's updated"""
        if instance.pk:
            try:
                original = PresentationRequest.objects.get(pk=instance.pk)
                # Resolve location from related assignment or schedule (safe access)
                orig_location = None
                try:
                    if hasattr(original, 'assignment') and getattr(original, 'assignment'):
                        orig_location = original.assignment.venue or original.assignment.meeting_link or None
                    elif hasattr(original, 'schedule') and getattr(original, 'schedule'):
                        orig_location = original.schedule.venue or original.schedule.meeting_link or None
                except Exception:
                    orig_location = None

                data = {
                    'research_title': original.research_title,
                    'status': original.status,
                    'scheduled_date': str(original.scheduled_date) if original.scheduled_date else None,
                    'location': orig_location,
                }
                _pre_save_instances[f'PresentationRequest_{instance.pk}'] = data
            except PresentationRequest.DoesNotExist:
                pass
    
    
    @receiver(post_save, sender=PresentationRequest)
    def log_presentation_changes(sender, instance, created, **kwargs):
        """Log PresentationRequest changes to audit log"""
        if created:
            supervisors_names = ', '.join([s.get_full_name() for s in instance.supervisors.all()]) if hasattr(instance, 'supervisors') else 'N/A'
            changes = {
                'research_title': [None, instance.research_title],
                'status': [None, instance.status],
                'student': [None, instance.student.get_full_name() if instance.student else 'N/A'],
                'supervisors': [None, supervisors_names],
                'school': [None, instance.school.name if hasattr(instance, 'school') and instance.school else 'N/A'],
            }
            
            AuditLog.log_action(
                user=getattr(instance, '_current_user', instance.student),
                action='CREATE',
                model_instance=instance,
                description=f'Created presentation: {instance.research_title[:50]}',
                changes=changes,
                success=True
            )
        else:
            key = f'PresentationRequest_{instance.pk}'
            if key in _pre_save_instances:
                old_data = _pre_save_instances[key]
                
                changes = {}
                if old_data['research_title'] != instance.research_title:
                    changes['research_title'] = [old_data['research_title'], instance.research_title]
                if old_data['status'] != instance.status:
                    changes['status'] = [old_data['status'], instance.status]
                if old_data['scheduled_date'] != (str(instance.scheduled_date) if instance.scheduled_date else None):
                    changes['scheduled_date'] = [old_data['scheduled_date'], str(instance.scheduled_date) if instance.scheduled_date else 'Not scheduled']

                # Resolve current instance location similarly to how we captured the original
                inst_location = None
                try:
                    if hasattr(instance, 'assignment') and getattr(instance, 'assignment'):
                        inst_location = instance.assignment.venue or instance.assignment.meeting_link or None
                    elif hasattr(instance, 'schedule') and getattr(instance, 'schedule'):
                        inst_location = instance.schedule.venue or instance.schedule.meeting_link or None
                except Exception:
                    inst_location = None

                if old_data.get('location') != inst_location:
                    changes['location'] = [old_data.get('location') or 'Not set', inst_location or 'Not set']
                
                if changes:
                    AuditLog.log_action(
                        user=getattr(instance, '_current_user', None),
                        action='UPDATE',
                        model_instance=instance,
                        description=f'Updated presentation: {instance.research_title[:50]}',
                        changes=changes,
                        success=True
                    )
                
                del _pre_save_instances[key]
    
    
    @receiver(pre_delete, sender=PresentationRequest)
    def log_presentation_deletion(sender, instance, **kwargs):
        """Log PresentationRequest deletion"""
        supervisors_names = ', '.join([s.get_full_name() for s in instance.supervisors.all()]) if hasattr(instance, 'supervisors') else 'N/A'
        # Resolve location from related assignment or schedule
        del_location = None
        try:
            if hasattr(instance, 'assignment') and getattr(instance, 'assignment'):
                del_location = instance.assignment.venue or instance.assignment.meeting_link or None
            elif hasattr(instance, 'schedule') and getattr(instance, 'schedule'):
                del_location = instance.schedule.venue or instance.schedule.meeting_link or None
        except Exception:
            del_location = None

        deleted_data = {
            'id': instance.id,
            'research_title': instance.research_title,
            'status': instance.status,
            'student': instance.student.get_full_name() if instance.student else 'N/A',
            'supervisors': supervisors_names,
            'school': instance.school.name if instance.school else 'N/A',
            'scheduled_date': str(instance.scheduled_date) if instance.scheduled_date else 'Not scheduled',
            'location': del_location or 'Not set',
        }
        
        AuditLog.log_action(
            user=getattr(instance, '_current_user', None),
            action='DELETE',
            model_instance=instance,
            description=f'Deleted presentation: {instance.research_title[:50]}',
            changes=deleted_data,
            success=True
        )
    
    
    @receiver(pre_save, sender=ExaminerAssignment)
    def capture_examiner_assignment_before_save(sender, instance, **kwargs):
        """Capture ExaminerAssignment data before update"""
        if instance.pk:
            try:
                original = ExaminerAssignment.objects.get(pk=instance.pk)
                data = {
                    'status': original.status,
                    'is_confirmed': getattr(original, 'is_confirmed', None),
                }
                _pre_save_instances[f'ExaminerAssignment_{instance.pk}'] = data
            except ExaminerAssignment.DoesNotExist:
                pass
    
    
    @receiver(post_save, sender=ExaminerAssignment)
    def log_examiner_assignment_changes(sender, instance, created, **kwargs):
        """Log ExaminerAssignment changes"""
        if created:
            # Resolve presentation title safely via assignment -> presentation
            pres_title = 'N/A'
            try:
                if hasattr(instance, 'assignment') and instance.assignment and hasattr(instance.assignment, 'presentation') and instance.assignment.presentation:
                    pres_title = instance.assignment.presentation.research_title[:50]
            except Exception:
                pres_title = 'N/A'

            changes = {
                'examiner': [None, instance.examiner.get_full_name() if instance.examiner else 'N/A'],
                'presentation': [None, pres_title],
                'status': [None, instance.status],
            }
            
            AuditLog.log_action(
                user=getattr(instance, '_current_user', None),
                action='ASSIGN',
                model_instance=instance,
                description=f'Assigned examiner: {instance.examiner.get_full_name() if instance.examiner else "N/A"}',
                changes=changes,
                success=True
            )
        else:
            key = f'ExaminerAssignment_{instance.pk}'
            if key in _pre_save_instances:
                old_data = _pre_save_instances[key]
                
                changes = {}
                if old_data['status'] != instance.status:
                    changes['status'] = [old_data['status'], instance.status]
                if old_data.get('is_confirmed') != getattr(instance, 'is_confirmed', None):
                    changes['is_confirmed'] = [old_data.get('is_confirmed'), getattr(instance, 'is_confirmed', None)]
                
                if changes:
                    AuditLog.log_action(
                        user=getattr(instance, '_current_user', None),
                        action='UPDATE',
                        model_instance=instance,
                        description=f'Updated examiner assignment: {instance.examiner.get_full_name() if instance.examiner else "N/A"}',
                        changes=changes,
                        success=True
                    )
                
                del _pre_save_instances[key]
    
    
    @receiver(post_save, sender=SupervisorAssignment)
    def log_supervisor_assignment_changes(sender, instance, created, **kwargs):
        """Log SupervisorAssignment changes"""
        if created:
            changes = {
                'supervisor': [None, instance.supervisor.get_full_name() if instance.supervisor else 'N/A'],
                'student': [None, instance.student.get_full_name() if instance.student else 'N/A'],
            }
            
            AuditLog.log_action(
                user=getattr(instance, '_current_user', None),
                action='ASSIGN',
                model_instance=instance,
                description=f'Assigned supervisor: {instance.supervisor.get_full_name() if instance.supervisor else "N/A"}',
                changes=changes,
                success=True
            )
            # Notify the supervisor by creating an in-app notification and sending an email
            try:
                from apps.notifications.utils import send_supervisor_assignment_notification
                try:
                    send_supervisor_assignment_notification(
                        supervisor=instance.supervisor,
                        presentation_request=instance.assignment.presentation,
                        assigned_by=getattr(instance, '_current_user', None)
                    )
                except Exception:
                    # best-effort: do not fail the signal if notification fails
                    pass
            except Exception:
                # If the notifications utils cannot be imported, ignore to avoid breaking save flow
                pass
    
    
    @receiver(post_save, sender=PresentationAssignment)
    def log_presentation_assignment_changes(sender, instance, created, **kwargs):
        """Log PresentationAssignment changes"""
        if created:
            changes = {
                'coordinator': [None, instance.coordinator.get_full_name() if instance.coordinator else 'N/A'],
                'presentation': [None, instance.presentation.research_title[:50] if instance.presentation else 'N/A'],
                'session_moderator': [None, instance.session_moderator.get_full_name() if instance.session_moderator else 'Not assigned'],
            }
            
            AuditLog.log_action(
                user=getattr(instance, '_current_user', None),
                action='CREATE',
                model_instance=instance,
                description=f'Created presentation assignment for: {instance.presentation.research_title[:50] if instance.presentation else "N/A"}',
                changes=changes,
                success=True
            )


    @receiver(post_save, sender=PresentationSchedule)
    def sync_schedule_to_presentation(sender, instance, created, **kwargs):
        """When a PresentationSchedule is created/updated, copy its start_time
        into the PresentationRequest.scheduled_date so assignments/notifications
        use the latest date set by coordinators through scheduling."""
        try:
            presentation = instance.presentation
            if presentation:
                # Only update if the schedule start_time differs from current
                if presentation.scheduled_date != instance.start_time:
                    presentation.scheduled_date = instance.start_time
                    presentation.status = 'scheduled'
                    # Preserve current user if provided on the schedule instance
                    if hasattr(instance, '_current_user'):
                        presentation._current_user = instance._current_user
                    presentation.save()
        except Exception:
            # Fail silently to avoid breaking admin/schedule flows
            pass
