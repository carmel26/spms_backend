from rest_framework import serializers
from .models import CustomUser, StudentProfile, SupervisorProfile, ExaminerProfile, CoordinatorProfile, UserGroup, SystemSettings, AuditLog


class UserGroupSerializer(serializers.ModelSerializer):
    """Serializer for UserGroup model"""
    
    class Meta:
        model = UserGroup
        fields = ['id', 'name', 'display_name', 'description', 'permissions', 'is_active', 
                  'blockchain_hash', 'blockchain_timestamp', 'created_at', 'updated_at']
        read_only_fields = ['id', 'blockchain_hash', 'blockchain_timestamp', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """Ensure name is lowercase with underscores"""
        if not value:
            raise serializers.ValidationError("Name is required")
        # Convert to lowercase and replace spaces with underscores
        cleaned_name = value.lower().strip().replace(' ', '_')
        # Remove any non-alphanumeric characters except underscores
        import re
        cleaned_name = re.sub(r'[^\w]', '_', cleaned_name)
        return cleaned_name
    
    def validate_display_name(self, value):
        """Ensure display name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Display name is required")
        return value.strip()


class CustomUserSerializer(serializers.ModelSerializer):
    roles_display = serializers.SerializerMethodField()
    user_groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserGroup.objects.all(),
        required=False
    )
    user_groups_details = serializers.SerializerMethodField()
    title_display = serializers.CharField(source='get_title_display', read_only=True)
    full_name_with_title = serializers.CharField(source='get_full_name_with_title', read_only=True)
    supervisor_profiles = serializers.SerializerMethodField()
    examiner_profiles = serializers.SerializerMethodField()
    coordinator_profiles = serializers.SerializerMethodField()
    student_profile = serializers.SerializerMethodField()
    has_student_profile = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'middle_name', 'last_name',
            'title', 'title_display', 'full_name_with_title',
            'user_groups', 'user_groups_details', 'roles_display',
            'phone_number', 'registration_number',
            'school', 'programme', 'is_active', 'is_approved', 'approved_date', 
            'supervisor_profiles', 'examiner_profiles', 'coordinator_profiles', 
            'student_profile', 'has_student_profile',
            'password', 'last_login_date', 'date_created'
        ]
        read_only_fields = ['id', 'date_created', 'last_login_date', 'approved_by', 'roles_display']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'allow_blank': True},
            'title': {'required': False}
        }
    
    def get_user_groups_details(self, obj):
        """Get detailed information about user's groups/roles including permissions"""
        return [
            {
                'id': group.id,
                'name': group.name,
                'display_name': group.display_name,
                'permissions': group.permissions or []
            }
            for group in obj.user_groups.all()
        ]
    
    def get_roles_display(self, obj):
        """Get display names of all roles"""
        return obj.get_role_display_name()
    
    def get_supervisor_profiles(self, obj):
        """Get all supervisor profiles for the user"""
        profiles = obj.supervisor_profiles.filter(is_active=True)
        return SupervisorProfileSerializer(profiles, many=True).data
    
    def get_examiner_profiles(self, obj):
        """Get all examiner profiles for the user"""
        profiles = obj.examiner_profiles.filter(is_active=True)
        return ExaminerProfileSerializer(profiles, many=True).data
    
    def get_coordinator_profiles(self, obj):
        """Get all coordinator profiles for the user"""
        profiles = obj.coordinator_profiles.filter(is_active=True)
        return CoordinatorProfileSerializer(profiles, many=True).data
    
    def get_student_profile(self, obj):
        """Get student profile if exists"""
        if hasattr(obj, 'student_profile'):
            return StudentProfileSerializer(obj.student_profile).data
        return None
    
    def get_has_student_profile(self, obj):
        """Check if user has a student profile"""
        return hasattr(obj, 'student_profile') and obj.student_profile is not None
    
    def validate_email(self, value):
        """Ensure email is unique"""
        if not value:
            raise serializers.ValidationError("Email is required")
        
        # Normalize email to lowercase
        value = value.lower().strip()
        
        # Check if email already exists (exclude current instance for updates)
        if self.instance:
            # Updating existing user - exclude current user from uniqueness check
            if CustomUser.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        else:
            # Creating new user
            if CustomUser.objects.filter(email=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        
        return value
    
    def validate(self, data):
        """Validate that students can only have student role"""
        user_groups = data.get('user_groups', [])
        
        # Check if student role is in the groups
        student_groups = [g for g in user_groups if g.name == 'student']
        
        if student_groups and len(user_groups) > 1:
            raise serializers.ValidationError({
                'user_groups': 'Students cannot have multiple roles. Please select only the student role.'
            })
        
        return data

    def create(self, validated_data):
        if not validated_data.get('username'):
            validated_data['username'] = validated_data.get('email')
        password = validated_data.pop('password', None)
        user_groups = validated_data.pop('user_groups', [])
        
        user = CustomUser.objects.create(**validated_data)
        
        # Add user groups (multiple roles)
        if user_groups:
            user.user_groups.set(user_groups)
        
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        # Handle password update separately - only update if provided
        password = validated_data.pop('password', None)
        user_groups = validated_data.pop('user_groups', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update user groups if provided
        if user_groups is not None:
            instance.user_groups.set(user_groups)
        
        # Only update password if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

    def create(self, validated_data):
        if not validated_data.get('username'):
            validated_data['username'] = validated_data.get('email')
        password = validated_data.pop('password', None)
        must_change_password = validated_data.pop('must_change_password', False)
        user_groups = validated_data.pop('user_groups', [])
        
        # If user_group is provided, sync the role field for backward compatibility
        if 'user_group' in validated_data and validated_data['user_group']:
            validated_data['role'] = validated_data['user_group'].name
        
        user = CustomUser.objects.create(**validated_data)
        
        # Add user groups (multiple roles)
        if user_groups:
            user.user_groups.set(user_groups)
        
        if password:
            user.set_password(password)
            # Set password_changed flag based on must_change_password
            if must_change_password:
                user.password_changed = False
            user.save()
        return user
    
    def update(self, instance, validated_data):
        # Handle password update separately - only update if provided
        password = validated_data.pop('password', None)
        user_groups = validated_data.pop('user_groups', None)
        
        # If user_group is being updated, sync the role field
        if 'user_group' in validated_data and validated_data['user_group']:
            validated_data['role'] = validated_data['user_group'].name
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update user groups if provided
        if user_groups is not None:
            instance.user_groups.set(user_groups)
        
        # Only update password if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class SystemSettingsSerializer(serializers.ModelSerializer):
    """Serializer for SystemSettings model"""
    
    class Meta:
        model = SystemSettings
        fields = [
            'id', 'system_name', 'system_email', 'system_url',
            'max_presentations', 'presentation_duration', 'qa_duration',
            'email_on_registration', 'email_on_presentation_request', 'email_on_approval',
            'updated_at', 'updated_by'
        ]
        read_only_fields = ['id', 'updated_at']


class SupervisorProfileSerializer(serializers.ModelSerializer):
    """Serializer for supervisor profile metadata"""
    class Meta:
        model = SupervisorProfile
        fields = ['id', 'user', 'specialization', 'department', 'is_active', 'total_supervised']
        read_only_fields = ['id', 'total_supervised']


class ExaminerProfileSerializer(serializers.ModelSerializer):
    """Serializer for examiner profile metadata"""
    class Meta:
        model = ExaminerProfile
        fields = ['id', 'user', 'specialization', 'is_active', 'total_assessments']
        read_only_fields = ['id', 'total_assessments']


class CoordinatorProfileSerializer(serializers.ModelSerializer):
    """Serializer for coordinator profile metadata"""
    school_name = serializers.CharField(source='school.name', read_only=True)
    
    class Meta:
        model = CoordinatorProfile
        fields = ['id', 'user', 'school', 'school_name', 'is_active']
        read_only_fields = ['id']


class StudentProfileSerializer(serializers.ModelSerializer):
    """Serializer for student profile (one-to-one with user)"""
    supervisor_name = serializers.CharField(source='supervisor.get_full_name', read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'programme_level',
            'supervisor', 'supervisor_name', 'admission_year', 'enrollment_year',
            'expected_graduation', 'is_active_student', 'is_admitted',
            'progress_percentage', 'total_presentations', 'completed_presentations'
        ]
        read_only_fields = ['id', 'progress_percentage', 'total_presentations', 'completed_presentations']


class StudentProfileDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for student profile"""
    supervisor_name = serializers.CharField(source='supervisor.get_full_name', read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'supervisor', 'supervisor_name',
            'admission_year', 'enrollment_year', 'expected_graduation',
            'programme_level', 'is_admitted', 'is_active_student'
        ]


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    class Meta:
        fields = ['username', 'password']


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    new_password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        fields = ['old_password', 'new_password', 'new_password_confirm']
    
    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match'})
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model"""
    
    user_display = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_display', 'user_role', 'action', 'action_display',
            'model_name', 'object_id', 'object_repr', 'description',
            'changes', 'ip_address', 'user_agent', 'request_path',
            'request_method', 'success', 'error_message', 'timestamp',
            'blockchain_hash', 'blockchain_block_number'
        ]
        read_only_fields = fields
    
    def get_user_display(self, obj):
        """Get user's full name or 'System' if no user"""
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'System'
    
    def get_user_role(self, obj):
        """Get user's role(s)"""
        if obj.user:
            roles = obj.user.user_groups.all()
            if roles:
                return ', '.join([role.display_name for role in roles])
            return 'No Role'
        return 'System'
