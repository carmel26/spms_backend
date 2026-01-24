from django.contrib import admin
from .models import (
    PresentationRequest, 
    PresentationAssignment,
    SupervisorAssignment,
    ExaminerAssignment, 
    PresentationSchedule, 
    PresentationAssessment,
    ExaminerChangeHistory
)


@admin.register(PresentationRequest)
class PresentationRequestAdmin(admin.ModelAdmin):
    list_display = ['student', 'presentation_type', 'research_title', 'status', 'proposed_date', 'created_at']
    list_filter = ['status', 'presentation_type', 'created_at']
    search_fields = ['student__username', 'student__email', 'research_title']


@admin.register(PresentationAssignment)
class PresentationAssignmentAdmin(admin.ModelAdmin):
    list_display = ['presentation', 'coordinator', 'created_at']
    search_fields = ['coordinator__username', 'presentation__student__username']


@admin.register(SupervisorAssignment)
class SupervisorAssignmentAdmin(admin.ModelAdmin):
    list_display = ['supervisor', 'assignment', 'status', 'acceptance_date']
    list_filter = ['status', 'acceptance_date']
    search_fields = ['supervisor__username']


@admin.register(ExaminerAssignment)
class ExaminerAssignmentAdmin(admin.ModelAdmin):
    list_display = ['examiner', 'assignment', 'status', 'acceptance_date']
    list_filter = ['status', 'acceptance_date']
    search_fields = ['examiner__username']


@admin.register(PresentationSchedule)
class PresentationScheduleAdmin(admin.ModelAdmin):
    list_display = ['presentation', 'venue', 'start_time', 'is_virtual']
    list_filter = ['is_virtual', 'start_time']


@admin.register(PresentationAssessment)
class PresentationAssessmentAdmin(admin.ModelAdmin):
    list_display = ['examiner_assignment', 'grade', 'submitted_at']
    list_filter = ['grade', 'submitted_at']


@admin.register(ExaminerChangeHistory)
class ExaminerChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ['presentation', 'changed_by', 'changed_at', 'get_previous_count', 'get_new_count']
    list_filter = ['changed_at']
    search_fields = ['presentation__research_title', 'changed_by__username']
    readonly_fields = ['changed_at']
    
    def get_previous_count(self, obj):
        return obj.previous_examiners.count()
    get_previous_count.short_description = 'Previous Examiners'
    
    def get_new_count(self, obj):
        return obj.new_examiners.count()
    get_new_count.short_description = 'New Examiners'
