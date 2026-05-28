from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='grades_index'),
    path('entry/', views.entry, name='grades_entry'),
    path('me/', views.student_view, name='grades_student_view'),
]
