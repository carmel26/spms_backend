from django.utils import timezone
from rest_framework import serializers
from apps.presentations.models import (
    PresentationRequest,
    SupervisorAssignment,
    ExaminerAssignment,
    ExaminerChangeHistory
)
from apps.schools.models import PresentationType
from apps.users.models import CustomUser, StudentProfile
from apps.users.serializers import StudentProfileSerializer
from apps.notifications.utils import send_presentation_submitted_notification, send_supervisor_assignment_notification


class BasicUserSerializer(serializers.ModelSerializer):
    """Lightweight user serializer for selection lists"""

    full_name = serializers.SerializerMethodField()
    title_display = serializers.CharField(source='get_title_display', read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'title', 'title_display', 'email', 'registration_number', 'full_name']
        read_only_fields = ['id']

    def get_full_name(self, obj):
        # Get the title if present (human-readable display value)
        title = obj.get_title_display() if obj.title else ''
        # Get first and last name
        first_name = obj.first_name or ''
        last_name = obj.last_name or ''
        
        # Check if first name already contains the title
        if title and first_name.startswith(title):
            # Title already in first name, don't duplicate
            name = f"{first_name} {last_name}".strip()
        elif title:
            # Add title before name
            name = f"{title} {first_name} {last_name}".strip()
        else:
            # No title, just first and last name
            name = f"{first_name} {last_name}".strip()
        
        return name or obj.username


class PresentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PresentationType
        fields = ['id', 'name', 'description', 'programme_type', 'duration_minutes', 'required_examiners']
        read_only_fields = ['id']


class PresentationRequestSerializer(serializers.ModelSerializer):
    presentation_type_detail = PresentationTypeSerializer(source='presentation_type', read_only=True)
    supervisors_detail = BasicUserSerializer(source='supervisors', many=True, read_only=True)
    proposed_examiners_detail = BasicUserSerializer(source='proposed_examiners', many=True, read_only=True)
    student_name = serializers.CharField(source='student.get_full_name_with_title', read_only=True)
    assignment = serializers.SerializerMethodField()

    supervisors = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=CustomUser.objects.filter(user_groups__name='supervisor')
    )
    proposed_examiners = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=CustomUser.objects.filter(user_groups__name='examiner')
    )

    class Meta:
        model = PresentationRequest
        fields = [
            'id', 'student', 'student_name', 'research_title', 'presentation_type', 'presentation_type_detail',
            'status', 'research_document', 'presentation_slides', 'plagiarism_report', 'proposed_date',
            'alternative_date', 'submission_date', 'created_at', 'updated_at', 'scheduled_date',
            'supervisors', 'supervisors_detail', 'proposed_examiners', 'proposed_examiners_detail', 'assignment'
        ]
        read_only_fields = ['id', 'student', 'status', 'submission_date', 'created_at', 'updated_at']

    def get_assignment(self, obj):
        """Get assignment details if exists"""
        try:
            assignment = obj.assignment
            examiner_assignments = assignment.examiner_assignments.all()
            supervisor_assignments = assignment.supervisor_assignments.all()
            return {
                'id': str(assignment.id),
                'meeting_link': assignment.meeting_link,
                'venue': assignment.venue,
                'session_moderator_id': str(assignment.session_moderator.id) if assignment.session_moderator else None,
                'session_moderator': BasicUserSerializer(assignment.session_moderator).data if assignment.session_moderator else None,
                'supervisor_assignments': [{
                    'id': str(sa.id),
                    'supervisor': str(sa.supervisor.id),
                    'supervisor_detail': BasicUserSerializer(sa.supervisor).data,
                    'status': sa.status,
                    'decline_reason': sa.decline_reason
                } for sa in supervisor_assignments],
                'examiner_assignments': [{
                    'id': str(ea.id),
                    'examiner': str(ea.examiner.id),
                    'examiner_detail': BasicUserSerializer(ea.examiner).data,
                    'status': ea.status,
                    'decline_reason': ea.decline_reason
                } for ea in examiner_assignments]
            }
        except PresentationRequest.assignment.RelatedObjectDoesNotExist:
            return None

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        presentation_type = attrs.get('presentation_type')

        if not user:
            raise serializers.ValidationError('Request context is missing user.')

        if not user.is_student():
            raise serializers.ValidationError('Only students can create presentation requests.')

        student_profile = StudentProfile.objects.filter(user=user).first()
        if not student_profile:
            raise serializers.ValidationError('Student profile not found. Please contact the admission office.')

        if not user.is_approved:
            raise serializers.ValidationError('Your account is pending approval.')
        if not student_profile.is_admitted:
            raise serializers.ValidationError('Your account has not been admitted yet. Please contact the admission office.')
        if not student_profile.is_active_student:
            raise serializers.ValidationError('Your student profile is inactive. Please contact the admission office.')

        if presentation_type:
            if presentation_type.programme_type not in ('both', student_profile.programme_level):
                raise serializers.ValidationError('This presentation type is not available for your programme level.')

            has_existing = PresentationRequest.objects.filter(
                student=user,
                presentation_type=presentation_type
            ).exclude(status__in=['rejected', 'cancelled']).exists()
            if has_existing:
                raise serializers.ValidationError('You have already requested this presentation type.')

        proposed_date = attrs.get('proposed_date')
        alternative_date = attrs.get('alternative_date')
        now = timezone.now()
        if proposed_date and proposed_date < now:
            raise serializers.ValidationError('Proposed date must be in the future.')
        if alternative_date and proposed_date and alternative_date < proposed_date:
            raise serializers.ValidationError('Alternative date must be after the proposed date.')

        # Plagiarism report is required for all submissions
        if not attrs.get('plagiarism_report'):
            raise serializers.ValidationError('Plagiarism report is required for submission.')

        return attrs

    def create(self, validated_data):
        supervisors = validated_data.pop('supervisors', [])
        examiners = validated_data.pop('proposed_examiners', [])

        validated_data['student'] = self.context['request'].user
        validated_data['status'] = 'submitted'
        validated_data['submission_date'] = timezone.now()

        instance = super().create(validated_data)
        if supervisors:
            instance.supervisors.set(supervisors)
            # Notify newly attached supervisors
            try:
                request = self.context.get('request')
                assigned_by = request.user if request else None
                from apps.users.models import CustomUser
                for sup in supervisors:
                    try:
                        user = CustomUser.objects.get(id=sup.id) if hasattr(sup, 'id') else sup
                        send_supervisor_assignment_notification(user, instance, assigned_by=assigned_by)
                    except Exception:
                        pass
            except Exception:
                pass
        if examiners:
            instance.proposed_examiners.set(examiners)
        
        # Send notifications to all coordinators
        send_presentation_submitted_notification(instance)
        
        return instance

    def update(self, instance, validated_data):
        supervisors = validated_data.pop('supervisors', None)
        examiners = validated_data.pop('proposed_examiners', None)

        instance = super().update(instance, validated_data)

        if supervisors is not None:
            # Determine newly added supervisors and notify them
            previous_ids = set(instance.supervisors.values_list('id', flat=True))
            new_ids = set([s.id if hasattr(s, 'id') else s for s in supervisors]) - previous_ids
            instance.supervisors.set(supervisors)

            try:
                request = self.context.get('request')
                assigned_by = request.user if request else None
                from apps.users.models import CustomUser
                for sup_id in new_ids:
                    try:
                        user = CustomUser.objects.get(id=sup_id)
                        send_supervisor_assignment_notification(user, instance, assigned_by=assigned_by)
                    except Exception:
                        pass
            except Exception:
                pass
        if examiners is not None:
            instance.proposed_examiners.set(examiners)
        return instance


class ExaminerAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for examiner assignments"""
    examiner_detail = BasicUserSerializer(source='examiner', read_only=True)
    presentation_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = ExaminerAssignment
        fields = ['id', 'examiner', 'examiner_detail', 'status', 'acceptance_date', 
                  'decline_reason', 'presentation_detail']
        read_only_fields = ['id', 'acceptance_date']
    
    def get_presentation_detail(self, obj):
        """Get detailed presentation info including student data for form pre-fill"""
        presentation = obj.assignment.presentation
        student = presentation.student
        # added testing code
        student_profile = getattr(student, 'student_profile', None)

        # Get student's school and programme names
        school_name = ''
        programme_name = ''
        if student.school:
            school_name = student.school.name
        if student.programme:
            programme_name = student.programme.name
        
        # Get supervisors
        supervisors = []
        for supervisor in presentation.supervisors.all():
            supervisors.append({
                'id': str(supervisor.id),
                'name': supervisor.get_full_name_with_title(),
                'email': supervisor.email
            })
        
        # Get presentation type info
        presentation_type_detail = None
        if presentation.presentation_type:
            presentation_type_detail = {
                'id': str(presentation.presentation_type.id),
                'name': presentation.presentation_type.name,
                'programme_type': presentation.presentation_type.programme_type,
            }
        
        return {
            'id': str(presentation.id),
            'research_title': presentation.research_title,
            'student_name': student.get_full_name_with_title(),
            'student_registration_number': student.registration_number or '',
            'student_school': school_name,
            'student_programme': programme_name,
            'proposed_date': presentation.proposed_date,
            'actual_date': presentation.actual_date or presentation.scheduled_date,
            'status': presentation.status,
            'supervisors': supervisors,
            'presentation_type_detail': presentation_type_detail,
             'student_profile': (
            StudentProfileSerializer(student_profile).data
                if student_profile else None
            ),
        }


class FormSerializer(serializers.ModelSerializer):
    """Serializer for the Form model that stores JSON payloads."""
    created_by_detail = BasicUserSerializer(source='created_by', read_only=True)
    blockchain_record_id = serializers.CharField(source='blockchain_record.id', read_only=True)
    email_sent = serializers.SerializerMethodField()
    email_status = serializers.SerializerMethodField()

    class Meta:
        model = None  # set below to avoid import cycles
        fields = ['id', 'name', 'form_role', 'presentation', 'data', 'created_by', 'created_by_detail',
                  'created_at', 'updated_at', 'blockchain_record', 'blockchain_record_id', 'email_sent', 'email_status']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at', 'blockchain_record', 'blockchain_record_id', 'email_sent', 'email_status']
    
    def get_email_sent(self, obj):
        """Return whether email was sent during create/update"""
        return getattr(obj, '_email_sent', False)
    
    def get_email_status(self, obj):
        """Return email status message"""
        return getattr(obj, '_email_status', 'not_sent')


# Import Form model here to avoid circular imports at module import time
from apps.presentations.models import Form as PresentationForm
FormSerializer.Meta.model = PresentationForm


class ExaminerChangeHistorySerializer(serializers.ModelSerializer):
    """Serializer for examiner change history"""
    changed_by_detail = BasicUserSerializer(source='changed_by', read_only=True)
    previous_examiners_detail = BasicUserSerializer(source='previous_examiners', many=True, read_only=True)
    new_examiners_detail = BasicUserSerializer(source='new_examiners', many=True, read_only=True)
    presentation_title = serializers.CharField(source='presentation.research_title', read_only=True)
    
    class Meta:
        model = ExaminerChangeHistory
        fields = ['id', 'presentation', 'presentation_title', 'changed_by', 'changed_by_detail',
                  'previous_examiners_detail', 'new_examiners_detail', 'change_reason', 'changed_at']
        read_only_fields = ['id', 'changed_at']


# Import PhdAssessmentItem model for serializer
from apps.presentations.models import PhdAssessmentItem

class PhdAssessmentItemSerializer(serializers.ModelSerializer):
    """Serializer for PhD Assessment Items"""
    
    class Meta:
        model = PhdAssessmentItem
        fields = ['id', 'sn', 'description', 'max_score', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
