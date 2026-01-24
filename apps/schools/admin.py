from django.contrib import admin
from .models import School, Programme, PresentationType


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'dean', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'abbreviation', 'contact_email']


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'school', 'programme_type', 'is_active']
    list_filter = ['school', 'programme_type', 'is_active']
    search_fields = ['name', 'code']


@admin.register(PresentationType)
class PresentationTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'programme_type', 'duration_minutes', 'is_active']
    list_filter = ['programme_type', 'is_active']
