from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='teachers_dashboard'),
]
