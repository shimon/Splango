from django.contrib import admin

from splango.models import Subject, Goal, GoalRecord, Enrollment, Experiment, ExperimentReport

admin.site.register(Subject)

class GoalAdmin(admin.ModelAdmin):
    list_display = ("name","created")
admin.site.register(Goal, GoalAdmin)

class GoalRecordAdmin(admin.ModelAdmin):
    list_display = ("goal","subject","created","req_HTTP_REFERER")
admin.site.register(GoalRecord, GoalRecordAdmin)

class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("subject","experiment","variant","created")
admin.site.register(Enrollment, EnrollmentAdmin)

class ExperimentAdmin(admin.ModelAdmin):
    list_display = ("name","variants_commasep","created")
admin.site.register(Experiment, ExperimentAdmin)

class ExperimentReportAdmin(admin.ModelAdmin):
    list_display = ("title", "experiment")
admin.site.register(ExperimentReport, ExperimentReportAdmin)

