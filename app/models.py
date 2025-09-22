
from django.db import models

class StaffInfo(models.Model):
    name = models.CharField(max_length=50)
    email = models.CharField(max_length=50,unique=True)
    mobile = models.CharField(max_length=11)

    def __str__(self):
        return self.name


class StudentInfo(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    staff = models.ForeignKey(StaffInfo, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.student_id} - {self.name}"

class Payment(models.Model):
    student = models.ForeignKey(StudentInfo, on_delete=models.CASCADE)
    name = models.CharField(max_length=100) 
    amount = models.DecimalField(max_digits=10, decimal_places=2) 
    payu_transaction_id = models.CharField(max_length=100, blank=True) 
    status = models.CharField(max_length=20, default='Pending') 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.payu_transaction_id} - {self.status}"
    
class PendingStudent(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    staff = models.ForeignKey('StaffInfo', on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)  

    def __str__(self):
        return f"Pending: {self.student_id} - {self.name}"
