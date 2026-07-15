from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='teachers_dashboard'),
    path('attendance/', views.attendance_workspace, name='teachers_attendance_workspace'),
    path('exams/', views.exams_workspace, name='teachers_exams_workspace'),
    path('exams/<int:exam_id>/results/', views.exam_results_workspace, name='teachers_exam_results_workspace'),
    path('resources/', views.learning_resources, name='teachers_learning_resources'),
]
