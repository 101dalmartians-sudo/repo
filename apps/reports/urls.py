from django.urls import path

from . import views


app_name = 'reports'

urlpatterns = [
    path('teacher/', views.teacher_periods, name='teacher_periods'),
    path('teacher/<int:period_id>/student/<int:student_id>/', views.teacher_report_editor, name='teacher_report_editor'),
    path('admin-dashboard/', views.admin_reports_dashboard, name='admin_reports_dashboard'),
    path('student/', views.student_reports, name='student_reports'),
    path('student/<int:report_id>/', views.student_report_detail, name='student_report_detail'),
    path('student/<int:report_id>/print/', views.student_report_print, name='student_report_print'),
    path('student/<int:report_id>/download/', views.student_report_download, name='student_report_download'),
]