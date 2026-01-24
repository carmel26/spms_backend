from django.db import models
import hashlib
import json
from datetime import datetime


class BlockchainRecord(models.Model):
    """Model to store blockchain records for tamper-proof data"""
    
    RECORD_TYPE_CHOICES = (
        ('user_creation', 'User Creation'),
        ('user_update', 'User Update'),
        ('role_creation', 'Role Creation'),
        ('role_update', 'Role Update'),
        ('role_deletion', 'Role Deletion'),
        ('presentation_submission', 'Presentation Submission'),
        ('presentation_scheduled', 'Presentation Scheduled'),
        ('assessment_submitted', 'Assessment Submitted'),
        ('notification_sent', 'Notification Sent'),
        ('date_changed', 'Date Changed'),
    )
    
    # Block information
    block_number = models.BigIntegerField(unique=True)
    previous_hash = models.CharField(max_length=256)
    current_hash = models.CharField(max_length=256, unique=True)
    
    # Record details
    record_type = models.CharField(max_length=50, choices=RECORD_TYPE_CHOICES)
    record_data = models.JSONField()  # Serialized data
    
    # Associated objects
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='blockchain_records'
    )
    presentation = models.ForeignKey(
        'presentations.PresentationRequest',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='blockchain_records'
    )
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'blockchain_records'
        ordering = ['block_number']
    
    def __str__(self):
        return f"Block #{self.block_number} - {self.record_type}"
    
    @staticmethod
    def calculate_hash(block_number, previous_hash, data, timestamp):
        """Calculate SHA-256 hash for a block"""
        block_string = json.dumps({
            'block_number': block_number,
            'previous_hash': previous_hash,
            'data': data,
            'timestamp': str(timestamp)
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    @classmethod
    def get_last_block(cls):
        """Get the last block in the chain"""
        try:
            return cls.objects.order_by('-block_number').first()
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def create_block(cls, record_type, record_data, user=None, presentation=None, ip_address=None):
        """Create a new block in the blockchain"""
        from django.utils import timezone as tz
        
        last_block = cls.get_last_block()
        
        # Determine next block number and previous hash
        if last_block:
            block_number = last_block.block_number + 1
            previous_hash = last_block.current_hash
        else:
            block_number = 1
            previous_hash = "0" * 64  # Genesis block
        
        # Create block first to get the actual timestamp
        block = cls.objects.create(
            block_number=block_number,
            previous_hash=previous_hash,
            current_hash="temporary",  # Temporary placeholder
            record_type=record_type,
            record_data=record_data,
            user=user,
            presentation=presentation,
            ip_address=ip_address
        )
        
        # Now calculate hash with the actual timestamp
        current_hash = cls.calculate_hash(block_number, previous_hash, record_data, block.timestamp)
        
        # Update with correct hash
        block.current_hash = current_hash
        block.save(update_fields=['current_hash'])
        
        return block


class SmartContract(models.Model):
    """Model for smart contracts related to presentations"""
    
    CONTRACT_TYPE_CHOICES = (
        ('presentation_rules', 'Presentation Rules'),
        ('assessment_rules', 'Assessment Rules'),
        ('notification_rules', 'Notification Rules'),
    )
    
    name = models.CharField(max_length=255)
    contract_type = models.CharField(max_length=50, choices=CONTRACT_TYPE_CHOICES)
    contract_code = models.TextField()  # Python code as string
    contract_hash = models.CharField(max_length=256, unique=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deployed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'smart_contracts'
    
    def __str__(self):
        return self.name
    
    def calculate_hash(self):
        """Calculate hash of contract code"""
        return hashlib.sha256(self.contract_code.encode()).hexdigest()
    
    def save(self, *args, **kwargs):
        self.contract_hash = self.calculate_hash()
        super().save(*args, **kwargs)
