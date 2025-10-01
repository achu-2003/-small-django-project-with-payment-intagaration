from django.contrib import admin
from .models import StudentInfo,Payment,StaffInfo,PendingStudent
from import_export.admin import ImportExportModelAdmin
from django.utils.html import format_html
from django.urls import reverse

class StaffInfoAdmin(admin.ModelAdmin):
    list_display=['name','email','mobile']

class PendingStudentAdmin(ImportExportModelAdmin,admin.ModelAdmin):
    list_display=['student_id','name','email','phone','staff','approved']


class StudentInfoAdmin(ImportExportModelAdmin,admin.ModelAdmin):
    list_display = ('student_id', 'name', 'email', 'phone','staff')
    search_fields = ('student_id', 'name')

class PaymentAdmin(ImportExportModelAdmin,admin.ModelAdmin):
    list_display = ('id','get_student_id', 'name', 'amount', 'status','payu_transaction_id','reject_button', 'created_at',"propelld_quote_id","admin_action")
    list_filter = ('status', 'created_at') 
    search_fields = ('payu_transaction_id', 'student__student_id')

    def reject_button(self, obj):
        if obj.status == "processing" and obj.propelld_quote_id:
            url = reverse("admin-reject-propelld", args=[obj.id])
            return format_html(
                '<a class="button" style="padding:3px 8px; background:red; color:white; border-radius:3px; text-decoration:none;" href="{}">Reject</a>',
                url
            )

    def get_student_id(self, obj):
        return obj.student.student_id
    get_student_id.short_description = 'Student ID'


admin.site.register(StudentInfo, StudentInfoAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(StaffInfo,StaffInfoAdmin)
admin.site.register(PendingStudent,PendingStudentAdmin)