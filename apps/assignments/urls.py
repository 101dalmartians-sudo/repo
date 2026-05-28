from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_assignment, name='assignment_upload'),
    path('', views.index, name='assignments_index'),
]
