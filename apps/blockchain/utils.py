"""
Blockchain utility functions for tamper-proof data management
"""
import hashlib
import json
from django.utils import timezone
from apps.blockchain.models import BlockchainRecord


class BlockchainManager:
    """Manager class for blockchain operations"""
    
    @staticmethod
    def record_operation(record_type, model_instance, operation='create', user=None, ip_address=None):
        """
        Record an operation in the blockchain
        
        Args:
            record_type: Type of record (e.g., 'user_creation', 'presentation_submission')
            model_instance: The Django model instance being recorded
            operation: Type of operation ('create', 'update', 'delete')
            user: User performing the operation
            ip_address: IP address of the request
        """
        # Prepare record data
        record_data = {
            'operation': operation,
            'model': model_instance.__class__.__name__,
            'model_id': str(model_instance.pk),
            'timestamp': str(timezone.now()),
            'data': serialize_model_data(model_instance)
        }
        
        # Determine presentation if applicable
        presentation = None
        if hasattr(model_instance, 'presentation'):
            presentation = model_instance.presentation
        elif model_instance.__class__.__name__ == 'PresentationRequest':
            presentation = model_instance
        
        # Create blockchain record
        block = BlockchainRecord.create_block(
            record_type=record_type,
            record_data=record_data,
            user=user,
            presentation=presentation,
            ip_address=ip_address
        )
        
        return block
    
    @staticmethod
    def verify_chain_integrity():
        """
        Verify the integrity of the entire blockchain
        Returns: (is_valid, errors_list)
        """
        blocks = BlockchainRecord.objects.order_by('block_number')
        errors = []
        
        if not blocks.exists():
            return True, []
        
        previous_block = None
        for block in blocks:
            # Check if previous hash matches
            if previous_block:
                if block.previous_hash != previous_block.current_hash:
                    errors.append(f"Block #{block.block_number}: Previous hash mismatch")
            else:
                # Genesis block should have all zeros
                if block.previous_hash != "0" * 64:
                    errors.append(f"Block #{block.block_number}: Invalid genesis block")
            
            # Verify current hash
            calculated_hash = BlockchainRecord.calculate_hash(
                block.block_number,
                block.previous_hash,
                block.record_data,
                block.timestamp
            )
            
            if block.current_hash != calculated_hash:
                errors.append(f"Block #{block.block_number}: Hash verification failed")
            
            previous_block = block
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_audit_trail(model_instance):
        """Get complete audit trail for a model instance"""
        model_name = model_instance.__class__.__name__
        model_id = model_instance.pk
        
        blocks = BlockchainRecord.objects.filter(
            record_data__model=model_name,
            record_data__model_id=model_id
        ).order_by('block_number')
        
        trail = []
        for block in blocks:
            trail.append({
                'block_number': block.block_number,
                'timestamp': block.timestamp,
                'record_type': block.record_type,
                'operation': block.record_data.get('operation'),
                'user': block.user.get_full_name() if block.user else 'System',
                'data': block.record_data.get('data'),
                'hash': block.current_hash
            })
        
        return trail


def serialize_model_data(instance):
    """
    Serialize model instance data for blockchain storage
    """
    data = {}
    
    # Get all fields except relations and auto fields
    for field in instance._meta.fields:
        field_name = field.name
        
        # Skip auto-generated fields
        if field_name in ['id', 'created_at', 'updated_at']:
            continue
        
        try:
            value = getattr(instance, field_name)
            
            # Handle different field types
            if hasattr(value, 'isoformat'):  # DateTime fields
                data[field_name] = value.isoformat()
            elif hasattr(value, 'pk'):  # Foreign keys
                # Convert related PKs to strings to ensure JSON serializability
                data[field_name] = {
                    'id': str(value.pk),
                    'str': str(value)
                }
            elif isinstance(value, (list, dict)):
                data[field_name] = value
            else:
                data[field_name] = str(value) if value is not None else None
        except:
            continue
    
    return data


def calculate_data_hash(data):
    """Calculate SHA-256 hash of data"""
    data_string = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_string.encode()).hexdigest()
