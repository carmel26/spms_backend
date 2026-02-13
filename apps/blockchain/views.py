"""
Blockchain API views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from apps.blockchain.models import BlockchainRecord
from apps.blockchain.utils import BlockchainManager
from apps.presentations.models import PresentationRequest
from apps.users.models import CustomUser


class BlockchainViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blockchain operations
    """
    queryset = BlockchainRecord.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        # We'll create a simple serializer inline
        from rest_framework import serializers
        
        class BlockchainRecordSerializer(serializers.ModelSerializer):
            user_name = serializers.SerializerMethodField()
            presentation_title = serializers.SerializerMethodField()
            
            class Meta:
                model = BlockchainRecord
                fields = [
                    'id', 'block_number', 'previous_hash', 'current_hash',
                    'record_type', 'record_data', 'timestamp', 'ip_address',
                    'user_name', 'presentation_title'
                ]
            
            def get_user_name(self, obj):
                return obj.user.get_full_name() if obj.user else 'System'
            
            def get_presentation_title(self, obj):
                return obj.presentation.research_title if obj.presentation else None
        
        return BlockchainRecordSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def verify_integrity(self, request):
        """
        Verify the integrity of the entire blockchain
        """
        is_valid, errors = BlockchainManager.verify_chain_integrity()
        
        total_blocks = BlockchainRecord.objects.count()
        
        return Response({
            'is_valid': is_valid,
            'total_blocks': total_blocks,
            'errors': errors,
            'message': 'Blockchain integrity verified successfully' if is_valid else 'Blockchain integrity check failed'
        })
    
    @action(detail=False, methods=['get'], url_path='audit-trail/presentation/(?P<presentation_id>[^/.]+)')
    def presentation_audit_trail(self, request, presentation_id=None):
        """
        Get audit trail for a specific presentation
        """
        presentation = get_object_or_404(PresentationRequest, pk=presentation_id)
        
        # Check permissions
        user = request.user
        if not (user.is_staff or user == presentation.student or 
                user.groups.filter(name__in=['Coordinator', 'Examiner']).exists()):
            return Response(
                {'error': 'You do not have permission to view this audit trail'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        trail = BlockchainManager.get_audit_trail(presentation)
        
        return Response({
            'presentation_id': str(presentation.id),
            'research_title': presentation.research_title,
            'student': presentation.student.get_full_name(),
            'audit_trail': trail,
            'total_records': len(trail)
        })
    
    @action(detail=False, methods=['get'], url_path='audit-trail/user/(?P<user_id>[^/.]+)')
    def user_audit_trail(self, request, user_id=None):
        """
        Get audit trail for a specific user
        """
        user_obj = get_object_or_404(CustomUser, pk=user_id)
        
        # Check permissions - users can only see their own trail unless admin
        if not (request.user.is_staff or request.user.id == user_obj.id):
            return Response(
                {'error': 'You do not have permission to view this audit trail'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        trail = BlockchainManager.get_audit_trail(user_obj)
        
        return Response({
            'user_id': str(user_obj.id),
            'user_name': user_obj.get_full_name(),
            'audit_trail': trail,
            'total_records': len(trail)
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get blockchain statistics
        """
        total_blocks = BlockchainRecord.objects.count()
        
        # Count by record type
        record_type_counts = {}
        for choice in BlockchainRecord.RECORD_TYPE_CHOICES:
            count = BlockchainRecord.objects.filter(record_type=choice[0]).count()
            record_type_counts[choice[1]] = count
        
        # Get latest blocks (fetch more for frontend pagination)
        latest_blocks = BlockchainRecord.objects.order_by('-block_number')[:50]
        
        serializer = self.get_serializer(latest_blocks, many=True)
        
        return Response({
            'total_blocks': total_blocks,
            'record_type_counts': record_type_counts,
            'latest_blocks': serializer.data
        })
