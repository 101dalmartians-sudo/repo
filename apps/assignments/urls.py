from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_assignment, name='assignment_upload'),
    path('attachments/<int:assignment_id>/', views.download_attachment, name='assignment_attachment_download'),
    path('', views.index, name='assignments_index'),
]
