from django.contrib import admin
from .models import StudentInfo,Payment,StaffInfo,PendingStudent
from import_export.admin import ImportExportModelAdmin

class StaffInfoAdmin(admin.ModelAdmin):
    list_display=['name','email','mobile']

class PendingStudentAdmin(ImportExportModelAdmin,admin.ModelAdmin):
    list_display=['student_id','name','email','phone','staff','approved']


class StudentInfoAdmin(ImportExportModelAdmin,admin.ModelAdmin):
    list_display = ('student_id', 'name', 'email', 'phone','staff')
    search_fields = ('student_id', 'name')

class PaymentAdmin(ImportExportModelAdmin,admin.ModelAdmin):
    list_display = ('get_student_id', 'name', 'amount', 'status','payu_transaction_id', 'created_at')
    list_filter = ('status', 'created_at') 
    search_fields = ('payu_transaction_id', 'student__student_id')

    def get_student_id(self, obj):
        return obj.student.student_id
    get_student_id.short_description = 'Student ID'


admin.site.register(StudentInfo, StudentInfoAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(StaffInfo,StaffInfoAdmin)
admin.site.register(PendingStudent,PendingStudentAdmin)