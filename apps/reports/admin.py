from django.contrib import admin
from .models import Report, DashboardWidget, Audit


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'generated_at', 'generated_by']
    list_filter = ['report_type', 'generated_at']
    search_fields = ['name', 'generated_by__username']


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'widget_type', 'role', 'position', 'is_active']
    list_filter = ['role', 'widget_type', 'is_active']


@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'resource_type', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'resource_type']
    readonly_fields = ['user', 'action', 'resource_type', 'timestamp']
