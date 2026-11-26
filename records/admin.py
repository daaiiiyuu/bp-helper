from django.contrib import admin

from .models import BloodPressureRecord, Challenge722


@admin.register(BloodPressureRecord)
class BloodPressureRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "measured_at", "period", "systolic", "diastolic", "pulse",
                    "readings_count", "checklist_done")
    list_filter = ("period", "checklist_done", "measured_at")
    search_fields = ("user__username", "note")
    date_hierarchy = "measured_at"


@admin.register(Challenge722)
class Challenge722Admin(admin.ModelAdmin):
    list_display = ("user", "start_date", "morning_time", "evening_time", "created_at")
