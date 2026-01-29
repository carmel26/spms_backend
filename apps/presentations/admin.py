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
from apps.notifications.utils import send_presentation_time_reminder
from django.contrib import messages


@admin.register(PresentationRequest)
class PresentationRequestAdmin(admin.ModelAdmin):
    list_display = ['student', 'presentation_type', 'research_title', 'status', 'proposed_date', 'created_at']
    list_filter = ['status', 'presentation_type', 'created_at']
    search_fields = ['student__username', 'student__email', 'research_title']
    actions = ['send_15_min_reminder', 'send_30_min_reminder']

    def _send_reminder_for_queryset(self, request, queryset, minutes):
        sent = 0
        for pr in queryset:
            try:
                send_presentation_time_reminder(pr, minutes_before=minutes)
                sent += 1
            except Exception:
                # continue to next
                continue
        self.message_user(request, f'Sent reminders for {sent} presentation(s) (minutes_before={minutes})', level=messages.SUCCESS)

    def send_15_min_reminder(self, request, queryset):
        """Admin action: send 15-minute reminders for selected presentations"""
        self._send_reminder_for_queryset(request, queryset, 15)
    send_15_min_reminder.short_description = 'Send 15-minute reminder for selected presentations'

    def send_30_min_reminder(self, request, queryset):
        """Admin action: send 30-minute reminders for selected presentations"""
        self._send_reminder_for_queryset(request, queryset, 30)
    send_30_min_reminder.short_description = 'Send 30-minute reminder for selected presentations'


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
