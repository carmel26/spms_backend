"""
Django signals for automatic blockchain recording
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.users.models import CustomUser, UserGroup
from apps.presentations.models import (
    PresentationRequest, PresentationAssignment,
    ExaminerAssignment, SupervisorAssignment
)
from apps.notifications.models import Notification
from apps.blockchain.utils import BlockchainManager


# User signals
@receiver(post_save, sender=CustomUser)
def record_user_blockchain(sender, instance, created, **kwargs):
    """Record user creation/update in blockchain"""
    if created:
        BlockchainManager.record_operation(
            record_type='user_creation',
            model_instance=instance,
            operation='create',
            user=instance
        )
    else:
        BlockchainManager.record_operation(
            record_type='user_update',
            model_instance=instance,
            operation='update',
            user=instance
        )


# UserGroup/Role signals
@receiver(post_save, sender=UserGroup)
def record_user_group_blockchain(sender, instance, created, **kwargs):
    """Record user group/role creation/update in blockchain"""
    if created:
        BlockchainManager.record_operation(
            record_type='role_creation',
            model_instance=instance,
            operation='create',
            user=None
        )
    else:
        BlockchainManager.record_operation(
            record_type='role_update',
            model_instance=instance,
            operation='update',
            user=None
        )


@receiver(post_delete, sender=UserGroup)
def record_user_group_deletion_blockchain(sender, instance, **kwargs):
    """Record user group/role deletion in blockchain"""
    BlockchainManager.record_operation(
        record_type='role_deletion',
        model_instance=instance,
        operation='delete',
        user=None
    )


# Presentation signals
@receiver(post_save, sender=PresentationRequest)
def record_presentation_blockchain(sender, instance, created, **kwargs):
    """Record presentation submission/update in blockchain"""
    if created:
        BlockchainManager.record_operation(
            record_type='presentation_submission',
            model_instance=instance,
            operation='create',
            user=instance.student
        )
    else:
        # Check if scheduled_date changed
        if instance.scheduled_date:
            BlockchainManager.record_operation(
                record_type='presentation_scheduled',
                model_instance=instance,
                operation='update',
                user=None
            )


@receiver(post_save, sender=PresentationAssignment)
def record_assignment_blockchain(sender, instance, created, **kwargs):
    """Record presentation assignment in blockchain"""
    if created:
        BlockchainManager.record_operation(
            record_type='presentation_scheduled',
            model_instance=instance,
            operation='create',
            user=instance.coordinator if hasattr(instance, 'coordinator') else None
        )


@receiver(post_save, sender=ExaminerAssignment)
def record_examiner_assignment_blockchain(sender, instance, created, **kwargs):
    """Record examiner assignment in blockchain"""
    if created or instance.status in ['accepted', 'declined']:
        BlockchainManager.record_operation(
            record_type='assessment_submitted',
            model_instance=instance,
            operation='create' if created else 'update',
            user=instance.examiner
        )


# Notification signals
@receiver(post_save, sender=Notification)
def record_notification_blockchain(sender, instance, created, **kwargs):
    """Record notification sending in blockchain"""
    if created:
        BlockchainManager.record_operation(
            record_type='notification_sent',
            model_instance=instance,
            operation='create',
            user=instance.recipient
        )
