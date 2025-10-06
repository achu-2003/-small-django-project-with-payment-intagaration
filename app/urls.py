from django.urls import path
from . import views

urlpatterns = [
    path('pay/<str:student_id>/', views.InitiatePaymentView.as_view(), name='initiate-payment'),
    path('success/', views.PaymentSuccessView.as_view(), name='payment-success'),
    path('failure/', views.PaymentFailureView.as_view(), name='payment-failure'),
    path('StudentCreate/',views.StudentCreateView.as_view(),name='create-student'),
    path("approve/<int:pk>/",views. ApproveStudentView.as_view(), name="approve_student"),
    path("reject/<int:pk>/", views.RejectStudentView.as_view(), name="reject_student"),
    path("choose-gateway/<str:student_id>/", views.choose_gateway, name="choose-gateway"),
    path("option-payment-webhook/", views.OptionPaymentView.as_view(), name="option-payment-webhook"),
    path('confirm-cloud-payment/', views.ConfirmCloudPaymentView.as_view(), name='confirm-cloud-payment'),
    path("propelld-initiate/<str:student_id>/", views.InitiatePropelldView.as_view(), name="initiate-propelld"),
    path("propelld-approve-reject/<int:payment_id>/", views.ApproveRejectPropelldView.as_view(), name="approve-reject-propelld"),
    path('reject-propelld/<int:payment_id>/', views.admin_reject_propelld, name='admin-reject-propelld'),
]
