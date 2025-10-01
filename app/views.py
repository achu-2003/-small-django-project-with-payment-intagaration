import hashlib,time,json
from django.shortcuts import render, get_object_or_404,redirect
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from .models import StudentInfo, Payment,PendingStudent
from .forms import StudentInfoForm
from django.views.generic import CreateView
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.db import IntegrityError
from django.contrib import messages
import requests,base64
from django.http import JsonResponse

def render_errors(msg=None):
    if msg:
        return msg
    return "An unexpected error occurred. Please try again later." 

class InitiatePaymentView(View):
    
    def get(self, request, student_id):
        try:
            try:
                student = StudentInfo.objects.get(student_id=student_id)
            except StudentInfo.DoesNotExist:
                return render(request,"error_page.html",
                    {"message": render_errors("Invalid student ID")})
            
            already_paid = Payment.objects.filter(
                student=student,
                status="paid"
            ).exists()

            if already_paid:
                return render(request,"error_page.html",
                    {"message": render_errors("You have already completed the payment")})
            
            product_name = "Course Fee"
            amount = "1.00"
            txnid = f"TXN{student_id}{str(time.time()).replace('.', '')[-10:]}"

            data = {
                'key': settings.PAYU_MERCHANT_KEY,
                'txnid': txnid,
                'amount': amount,
                'productinfo': product_name,
                'firstname': student.name.split()[0],
                'email': student.email,
                'phone': student.phone,
                'surl': request.build_absolute_uri(reverse('payment-success')),
                'furl': request.build_absolute_uri(reverse('payment-failure')),
                'hash': ''
            }

            hash_string = f"{data['key']}|{data['txnid']}|{data['amount']}|{data['productinfo']}|{data['firstname']}|{data['email']}|||||||||||{settings.PAYU_MERCHANT_SALT}"
            data['hash'] = hashlib.sha512(hash_string.encode()).hexdigest()

            payu_url = settings.PAYU_BASE_URL

            return render( request, 'redirect_to_payu.html',
                {'data': data,
                 'payu_url': payu_url,
                 'student': student})
        
        except Exception:
            return render(request,"error_page.html",
                {"message": render_errors("An unexpected error occurred. Please try again later.")})

    
@method_decorator(csrf_exempt, name='dispatch')
class PaymentSuccessView(View):
    def post(self, request):
        response_data = request.POST.dict()
        payu_hash = response_data.get("hash")

        hash_sequence = (
            f"{settings.PAYU_MERCHANT_SALT}|{response_data.get('status')}|||||||||||"
            f"{response_data.get('email')}|{response_data.get('firstname')}|"
            f"{response_data.get('productinfo')}|{response_data.get('amount')}|"
            f"{response_data.get('txnid')}|{response_data.get('key')}"
        )

        server_hash = hashlib.sha512(hash_sequence.encode()).hexdigest().lower()
      
        if payu_hash == server_hash and response_data.get("status") == "success":
            try:
                student = StudentInfo.objects.get(email=response_data.get("email"))                

                Payment.objects.create(
                    student=student,
                    name=response_data.get("firstname"),
                    amount=response_data.get("amount"),
                    payu_transaction_id=response_data.get("mihpayid"),
                    status="paid",
                )
                
                context = {
                    "student": student,
                    "amount": response_data.get("amount"),
                    "transaction_id": response_data.get("mihpayid"),
                }

                html_message = render_to_string("pay_success_email.html", context)

                email = EmailMessage(
                    subject="Payment Successful ✅",
                    body=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[student.email],
                )
                email.content_subtype = "html"
                email.send()
                
                return render_success(request, "💳 Payment successful and saved in the database!")
            
            except StudentInfo.DoesNotExist:
                return render(request,"error_page.html",
                    {"message": render_errors("Payment successful but student not found")}
                )
            except Exception:
                return render( request,"error_page.html",
                    {"message": render_errors("Payment successful but could not save details. Please contact support.")}
                )

        else:
             return render(request,"error_page.html",
                {"message": render_errors("Invalid transaction or payment failed")}
            )

    

@method_decorator(csrf_exempt, name='dispatch')
class PaymentFailureView(View):
    def post(self, request):
        response_data = request.POST.dict()
        print("Failure Response from PayU:", response_data)
        error_message = response_data.get('error_Message', 'Unknown error occurred')
        return render(request,"error_page.html",
            {"message": render_errors(f"Payment Failed! Reason: {error_message}")}
        )
    

class StudentCreateView(CreateView):
    model = PendingStudent
    form_class = StudentInfoForm   
    template_name = 'student_form.html'

    def form_valid(self, form):
        try:
            pending_student = form.save(commit=False)
            staff = form.cleaned_data["staff"] 

            pending_student = PendingStudent.objects.create(
            student_id=form.cleaned_data["student_id"],
            name=form.cleaned_data["name"],
            email=form.cleaned_data["email"],
            phone=form.cleaned_data["phone"],   
            staff =  staff
            )
        except ValidationError:
            return render(self.request,"error_page.html",
            {"message": render_errors("Invalid data provided. Please check your input.")}
        )
        except IntegrityError:
            return render(self.request,"error_page.html",
            {"message": render_errors("A student with this ID or email already exists.")}
        )
        except Exception:
            return render(self.request,"error_page.html",
            {"message": render_errors("An unexpected error occurred. Please try again later.")}
        )   
 
        self.send_approval_email(pending_student)

        return render_success(self.request, "📩 Your request has been sent to staff for approval!")



    def send_approval_email(self, pending_student):

        approve_url = settings.SITE_URL + reverse("approve_student", args=[pending_student.id])
        reject_url =  settings.SITE_URL + reverse("reject_student", args=[pending_student.id])

        context = {
            "student": pending_student,
            "approve_url": approve_url,
            "reject_url": reject_url
        }

        html_message = render_to_string("student_approval.html", context)
        
        email = EmailMessage(
            subject="Approval Needed for New Student",
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[pending_student.staff.email],
        )
        email.content_subtype = "html"
        email.send()


class ApproveStudentView(View):
    def get(self, request, pk):
        pending_student = get_object_or_404(PendingStudent, pk=pk)
        if not pending_student:
            return render(request, "error_page.html", {
                "message": "❌ Student record not found or already approved/rejected."
            })
        try:
            student = StudentInfo.objects.create(
                student_id=pending_student.student_id,
                name=pending_student.name,
                email=pending_student.email,
                phone=pending_student.phone,
                staff=pending_student.staff
            )

            payment_url = request.build_absolute_uri(
                reverse("choose-gateway", args=[student.student_id])
            )

            context = {
                "student": student,
                "payment_url": payment_url,
            }

            try:
                
                subject = "Your Registration is Approved 🎉"
                html_message = render_to_string("student_approved.html", context)

                email = EmailMessage(
                    subject=subject,
                    body=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[student.email],
                )
                email.content_subtype = "html"  
                email.send()

            except Exception as e:
                return render(request, "error_page.html", {
                    "message": render_errors(f"Email sending failed (approval): {e}")
                })

            pending_student.delete()
            return render_success(request, "🎉 Student approved, added to StudentInfo, and payment email sent!")


        except IntegrityError:
            return render(request, "error_page.html", {
                "message": render_errors("A student with this ID or email already exists.")
            })


class RejectStudentView(View):
    def get(self, request, pk):
        pending_student = get_object_or_404(PendingStudent, pk=pk)
        try:
            subject = "Your Registration Request was Rejected ❌"
            
            context = {
                "student_name": pending_student.name,
            }
      
            html_message = render_to_string("student_rejected.html", context)
     
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[pending_student.email],
            )
            email.content_subtype = "html"  
            email.send()

        except Exception as e:
            return render(request, "error_page.html", {
                "message": render_errors(f"Rejection email could not be sent. Error: {str(e)}")
            })
        
        pending_student.delete()
        return render_success(request, "❌ Student rejected, removed from PendingStudent, and email sent.")   


def render_success(request, msg):
    return render(request, "success_page.html", {"message": msg})
@never_cache
def choose_gateway(request, student_id):
    student = get_object_or_404(StudentInfo, student_id=student_id)

    cloud_payment = Payment.objects.filter(
        student=student,
        payu_transaction_id__startswith='CLOUD',
        status='processing'
    ).first()

    propelld_payment = Payment.objects.filter(
        student=student,
        propelld_quote_id__isnull=False,
        status="processing"
    ).first()

    return render(request, "choose_gateway.html", {
        "student": student,
        "cloud_payment": cloud_payment,
        "propelld_payment": propelld_payment
    })


 
@method_decorator(csrf_exempt, name='dispatch')
class OptionPaymentView(View):
    def post(self, request):
        response_data = request.POST.dict()
        student_id = response_data.get("student_id")
        print(response_data)

        if not student_id:
            return render(request, "error_page.html", {"message": "Student ID not provided."})

        try:
            student = StudentInfo.objects.get(student_id=student_id)
        except StudentInfo.DoesNotExist:
            return render(request, "error_page.html", {"message": "Student not found."})
        
        already_paid = Payment.objects.filter(
                student=student,
                status="paid"
            ).exists()

        if already_paid:
            return render(request,"error_page.html",
                {"message": render_errors("You have already completed the payment")})

        cloud_payment = Payment.objects.filter(
            student=student,
            payu_transaction_id__startswith="CLOUD",
            status="processing"
        ).first()

        if cloud_payment:
            payment = cloud_payment
        else:
            txn_id = f"CLOUD{id(student)}{student_id}"
            payment = Payment.objects.create(
                student=student,
                payu_transaction_id=txn_id,
                name=student.name.split()[0],
                amount=1.00,
                status="processing"
            )

        return render(request, "cloud_payment_confirmation.html", {"payment": payment})

    
@method_decorator(csrf_exempt, name='dispatch')
class ConfirmCloudPaymentView(View):
    def post(self, request):
        data = request.POST.dict()
  
        if not data:
            try:
                data = json.loads(request.body.decode())
            except Exception:
                data = {}
        print(data)
        txn_id = data.get("transaction_id")
        status = data.get("status")   

        if not txn_id or not status:
            return render(request, "error_page.html", {"message": "Invalid webhook payload"})

        allowed_statuses = {"processing", "disbursed", "success", "failed", "cancelled"}
        if status not in allowed_statuses:
            return render(request, "error_page.html", {"message": f"Unknown status '{status}'"})

        try:
            payment = Payment.objects.get(payu_transaction_id=txn_id)
        except Payment.DoesNotExist:
            return render(request, "error_page.html", {"message": "Payment record not found."})

        final_states = {"disbursed", "failed", "cancelled", "success"}
        if payment.status in final_states:
            return render(request, "success_page.html", {
                "message": f"Payment already in final state: {payment.status}"
            })

    
        status_map = {
            "processing": "processing",
            "success": "paid",       
            "disbursed": "disbursed",
            "failed": "failed",
            "cancelled": "cancelled"
        }
        payment.status = status_map.get(status, payment.status)
        payment.save()

        if status in ("success", "disbursed"):
            context = {
                "student": payment.student,
                "amount": payment.amount,
                "transaction_id": payment.payu_transaction_id,
                "status": status
            }
            html_message = render_to_string("pay_success_email.html", context)
            email_msg = EmailMessage(
                subject="Payment Successful ✅",
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[payment.student.email]
            )
            email_msg.content_subtype = "html"
            email_msg.send()
            return render(request, "success_page.html", {"message": f"💳 Payment {status}!"})

        elif status == "processing":
            return render(request, "success_page.html", {"message": "⏳ Payment is processing, please wait."})

        elif status in ("failed", "cancelled"):
            return render(request, "error_page.html", {"message": f"❌ Payment {status}."})

        return render(request, "error_page.html", {"message": "Unhandled payment status."})


 






@method_decorator(csrf_exempt, name="dispatch")
class InitiatePropelldView(View):
    def get(self, request, student_id):
        student = get_object_or_404(StudentInfo, student_id=student_id)

        payment = Payment.objects.create(
            student=student,
            name=student.name.split()[0],
            amount=51000,
            status="processing",
        )

        url = f"{settings.PROPELLD_API_URL}/product/apply/generic"
        # redirect_url = request.build_absolute_uri(reverse("propelld-webhook"))
        payload = {
            "CourseId": 16427,
            "FirstName": student.name.split()[0],
            "DiscountedCourseFee": int(payment.amount),
            "Email": student.email,
            "Mobile": student.phone,
            "ReferenceNumber": str(payment.id),
            # "RedirectUrl": redirect_url
        }

        headers = {
            "Content-Type": "application/json",
            "client-id": settings.PROPELLD_CLIENT_ID,
            "client-secret": settings.PROPELLD_CLIENT_SECRET
        }

        print("Payload:", payload)

        try:
            resp = requests.post(url, json=payload, headers=headers)
            # print("Status Code:", resp.status_code)
            # print("Response Text:", resp.text)

            resp_data = resp.json()
            payload_data = resp_data.get("PayLoad", {})

            quote_id = payload_data.get("QuoteId")
            redirection_url = payload_data.get("RedirectionUrl")

            if quote_id and redirection_url:
                payment.propelld_quote_id = quote_id
                payment.save()
                return redirect(redirection_url)
            else:
                payment.status = "failed"
                payment.save()
                return render(request, "error_page.html", {
                    "message": "Propelld did not return QuoteId or RedirectionUrl",
                    "response": resp.text,
                    "status_code": resp.status_code
                })

        except requests.exceptions.RequestException as e:
            payment.status = "failed"
            payment.save()
            return render(request, "error_page.html", {"message": f"Request error: {e}"})
        except ValueError:
            payment.status = "failed"
            payment.save()
            return render(request, "error_page.html", {"message": "Invalid JSON response"})


    

def admin_reject_propelld(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)

    if not payment.propelld_quote_id:
        messages.error(request, "No quote associated with this payment.")
        return redirect("/admin/app/payment/")   


    url = f"{settings.PROPELLD_API_URL}/quote/approve"
    QuoteId=payment.propelld_quote_id

    data = {
        "QuoteId": str(QuoteId),
        "Approved":  False  
    }

    headers = {
        "Content-Type": "application/json",
        "client-id": settings.PROPELLD_CLIENT_ID,
        "client-secret": settings.PROPELLD_CLIENT_SECRET
    }

    try:
        resp = requests.post(url, json=data, headers=headers)
        print("Status Code:", resp.status_code)
        print("Response Text:", resp.text)

        try:
            resp_data = resp.json()
        except ValueError:
            messages.error(request, f"Propelld returned invalid JSON. Response text: {resp.text}")
            return redirect("/admin/app/payment/")

    except requests.RequestException as e:
        messages.error(request, f"Error contacting Propelld: {e}")
        return redirect("/admin/app/payment/")

    if resp_data.get("Code") == 0:
        payment.status = "rejected"
        payment.admin_action = "Rejected by admin"
        payment.save()
        messages.success(request, f"Quote {payment.propelld_quote_id} rejected successfully in Propelld!")
    else:
        error_message = resp_data.get("Message") or resp_data.get("Errors")
        messages.error(request, f"Propelld did not reject the quote. Response: {error_message}")

    return redirect("/admin/app/payment/")






























@method_decorator(csrf_exempt, name='dispatch')
class ApproveRejectPropelldView(View):
    def post(self, request, payment_id):
        try:
            body = json.loads(request.body)
            approved = body.get("approved") is True   
        except Exception:
            return render(request, "error_page.html", {"message": "Invalid JSON body"})

        payment = get_object_or_404(Payment, id=payment_id)

        if not payment.propelld_quote_id:
            return render(request, "error_page.html", {"message": "No quote associated with this payment."})

        if payment.status != "processing":
            return render(request, "error_page.html", {"message": "Only processing quotes can be approved/rejected."})

        url = f"{settings.PROPELLD_API_URL}/quote/approve"
        payload = {
            "QuoteId": payment.propelld_quote_id, 
            "Approved": approved
        }

        headers = {
            "Content-Type": "application/json",
            "client-id": settings.PROPELLD_CLIENT_ID,
            "client-secret": settings.PROPELLD_CLIENT_SECRET        
        }
        print(payload)
        try:
            resp = requests.post(url, json=payload, headers=headers)
        except Exception as e:
            return render(request, "error_page.html", {"message": f"Error contacting Propelld: {e}"})
        print("Status Code:", resp.status_code)
        print("Response Text:", resp.text)
       
        try:
            resp_data = resp.json()
           
        except ValueError:
            return render(request, "error_page.html", {"message": f"Invalid JSON response from Propelld: {resp.text}"})

        if resp_data.get("StatusUpdated"):
            payment.status = "approved" if approved else "rejected"
            print(f"Quote {payment.propelld_quote_id} has been {payment.status}.")
            payment.save()
            return render_success(request, f"✅ Quote {payment.propelld_quote_id} updated successfully: {payment.status}")
        else:
            return render(request, "error_page.html", {"message": f"Propelld did not update the quote. Response: {resp_data}"})

















@method_decorator(csrf_exempt, name='dispatch')
class PropelldWebhookView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode())
        except Exception:
            data = {}

        quote_id = data.get("QuoteId")
        status = data.get("Status")

        if not quote_id or not status:
            return render(request, "error_page.html", {"message": "Invalid webhook payload"})

        try:
            payment = Payment.objects.get(propelld_quote_id=quote_id)
        except Payment.DoesNotExist:
            return render(request, "error_page.html", {"message": "Quote not found"})

        status_map = {
            "processing": "processing",
            "approved": "approved",
            "rejected": "rejected",
            "disbursed": "disbursed",
            "failed": "failed",
        }
        payment.status = status_map.get(status.lower(), payment.status)
        payment.save()

        return render_success(request, f"Webhook received. Quote {quote_id} status updated: {payment.status}")    