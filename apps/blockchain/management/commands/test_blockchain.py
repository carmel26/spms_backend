"""
Management command to test blockchain integrity and tamper detection
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.blockchain.models import BlockchainRecord
from apps.blockchain.utils import BlockchainManager
from apps.users.models import CustomUser
from apps.presentations.models import PresentationRequest
import random


class Command(BaseCommand):
    help = 'Test blockchain integrity and tamper detection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tamper',
            action='store_true',
            help='Simulate tampering with blockchain data',
        )
        parser.add_argument(
            '--audit',
            type=int,
            help='Show audit trail for presentation ID',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING('BLOCKCHAIN INTEGRITY TEST'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))
        
        # Show blockchain statistics
        self.show_statistics()
        
        # Test 1: Create some test records
        if not options.get('tamper') and not options.get('audit'):
            self.stdout.write(self.style.WARNING('\n--- Test 1: Creating Test Records ---'))
            self.create_test_records()
        
        # Test 2: Verify integrity
        self.stdout.write(self.style.WARNING('\n--- Test 2: Verifying Blockchain Integrity ---'))
        self.verify_integrity()
        
        # Test 3: Tamper detection (if requested)
        if options.get('tamper'):
            self.stdout.write(self.style.WARNING('\n--- Test 3: Tampering with Data ---'))
            self.simulate_tampering()
            self.stdout.write(self.style.WARNING('\n--- Test 4: Re-verifying After Tampering ---'))
            self.verify_integrity()
        
        # Test 4: Audit trail (if requested)
        if options.get('audit'):
            presentation_id = options['audit']
            self.stdout.write(self.style.WARNING(f'\n--- Audit Trail for Presentation #{presentation_id} ---'))
            self.show_audit_trail(presentation_id)
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('BLOCKCHAIN TEST COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def show_statistics(self):
        """Display blockchain statistics"""
        total_blocks = BlockchainRecord.objects.count()
        
        self.stdout.write(self.style.HTTP_INFO(f'\n📊 Blockchain Statistics:'))
        self.stdout.write(f'  Total Blocks: {total_blocks}')
        
        if total_blocks > 0:
            first_block = BlockchainRecord.objects.order_by('block_number').first()
            last_block = BlockchainRecord.objects.order_by('-block_number').first()
            
            self.stdout.write(f'  First Block: #{first_block.block_number} ({first_block.timestamp})')
            self.stdout.write(f'  Last Block: #{last_block.block_number} ({last_block.timestamp})')
            
            # Count by type
            self.stdout.write(f'\n  Records by Type:')
            for choice in BlockchainRecord.RECORD_TYPE_CHOICES:
                count = BlockchainRecord.objects.filter(record_type=choice[0]).count()
                if count > 0:
                    self.stdout.write(f'    - {choice[1]}: {count}')

    def create_test_records(self):
        """Create test blockchain records"""
        # Test with existing users and presentations
        users = CustomUser.objects.all()[:3]
        presentations = PresentationRequest.objects.all()[:3]
        
        if not users.exists():
            self.stdout.write(self.style.WARNING('  No users found to create test records'))
            return
        
        created_count = 0
        
        # Create some test records
        for user in users:
            BlockchainManager.record_operation(
                record_type='user_update',
                model_instance=user,
                operation='update',
                user=user
            )
            created_count += 1
        
        for presentation in presentations:
            BlockchainManager.record_operation(
                record_type='presentation_submission',
                model_instance=presentation,
                operation='update',
                user=presentation.student
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} test records'))

    def verify_integrity(self):
        """Verify blockchain integrity"""
        is_valid, errors = BlockchainManager.verify_chain_integrity()
        
        if is_valid:
            self.stdout.write(self.style.SUCCESS('  ✓ Blockchain integrity verified: VALID'))
            self.stdout.write(self.style.SUCCESS('  ✓ All blocks are properly chained'))
            self.stdout.write(self.style.SUCCESS('  ✓ All hashes are correct'))
        else:
            self.stdout.write(self.style.ERROR('  ✗ Blockchain integrity check: FAILED'))
            self.stdout.write(self.style.ERROR(f'  ✗ Found {len(errors)} error(s):'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'    - {error}'))

    def simulate_tampering(self):
        """Simulate tampering with blockchain data"""
        # Get a random block (not the genesis block)
        blocks = BlockchainRecord.objects.filter(block_number__gt=1)
        
        if not blocks.exists():
            self.stdout.write(self.style.WARNING('  Not enough blocks to simulate tampering'))
            return
        
        tampered_block = random.choice(blocks)
        original_data = tampered_block.record_data.copy()
        
        # Tamper with the data
        tampered_block.record_data['TAMPERED'] = True
        tampered_block.record_data['original_operation'] = original_data.get('operation')
        tampered_block.save()
        
        self.stdout.write(self.style.ERROR(f'  ⚠️  Tampered with Block #{tampered_block.block_number}'))
        self.stdout.write(f'  Modified record data to include TAMPERED flag')
        self.stdout.write(f'  Block hash: {tampered_block.current_hash}')
        
        # Restore data
        self.stdout.write(self.style.WARNING('\n  Note: Data has been permanently tampered to test detection'))

    def show_audit_trail(self, presentation_id):
        """Show audit trail for a presentation"""
        try:
            presentation = PresentationRequest.objects.get(pk=presentation_id)
        except PresentationRequest.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'  Presentation #{presentation_id} not found'))
            return
        
        trail = BlockchainManager.get_audit_trail(presentation)
        
        self.stdout.write(self.style.HTTP_INFO(f'\n  Presentation: {presentation.research_title}'))
        self.stdout.write(f'  Student: {presentation.student.get_full_name()}')
        self.stdout.write(f'  Total Records: {len(trail)}\n')
        
        if not trail:
            self.stdout.write(self.style.WARNING('  No blockchain records found'))
            return
        
        for i, record in enumerate(trail, 1):
            self.stdout.write(f'  {i}. Block #{record["block_number"]}')
            self.stdout.write(f'     Timestamp: {record["timestamp"]}')
            self.stdout.write(f'     Operation: {record["operation"]}')
            self.stdout.write(f'     User: {record["user"]}')
            self.stdout.write(f'     Hash: {record["hash"][:16]}...')
            self.stdout.write('')
