from rest_framework import serializers
from .models import School, Programme, PresentationType


class SchoolSerializer(serializers.ModelSerializer):
    dean_name = serializers.CharField(source='dean.get_full_name', read_only=True, allow_null=True)
    programmes_count = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            'id', 'name', 'abbreviation', 'description', 'dean', 'dean_name',
            'contact_email', 'contact_phone', 'logo', 'is_active',
            'programmes_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'dean': {'required': False, 'allow_null': True},
            'contact_email': {'required': False, 'allow_blank': True},
            'contact_phone': {'required': False, 'allow_blank': True},
            'logo': {'required': False, 'allow_null': True},
            'description': {'required': False, 'allow_blank': True}
        }

    def get_programmes_count(self, obj):
        return obj.programmes.count()


class ProgrammeSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = Programme
        fields = [
            'id', 'name', 'code', 'description', 'school', 'school_name',
            'programme_type', 'duration_months', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PresentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PresentationType
        fields = [
            'id', 'name', 'description', 'programme_type',
            'duration_minutes', 'required_examiners', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'name': {'required': True},
            'description': {'required': False, 'allow_blank': True},
            'programme_type': {'required': True},
            'duration_minutes': {'required': False},
            'required_examiners': {'required': False}
        }
