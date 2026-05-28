from django.urls import path
from . import views

urlpatterns = [
    path('', views.news_list, name='news_list'),
    path('<int:pk>/', views.news_detail, name='news_detail'),
    path('manage/', views.manage_news, name='manage_news'),
    path('create/', views.create_news, name='create_news'),
    path('<int:pk>/edit/', views.edit_news, name='edit_news'),
    path('<int:pk>/delete/', views.delete_news, name='delete_news'),
    path('<int:news_pk>/image/<int:image_pk>/delete/', views.delete_image, name='delete_image'),
    path('<int:news_pk>/document/<int:doc_pk>/delete/', views.delete_document, name='delete_document'),
]
