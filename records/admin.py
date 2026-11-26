from django.contrib import admin

from .models import BloodPressureRecord


@admin.register(BloodPressureRecord)
class BloodPressureRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "measured_at", "period", "systolic", "diastolic", "pulse",
                    "readings_count", "checklist_done")
    list_filter = ("period", "checklist_done", "measured_at")
    search_fields = ("user__username", "note")
    date_hierarchy = "measured_at"
