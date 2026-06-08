from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='students_dashboard'),
    path('profile/', views.profile_detail, name='student_profile'),
    path('payment/<str:receipt_number>/', views.payment_receipt, name='payment_receipt'),
]
