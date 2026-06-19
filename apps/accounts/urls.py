from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home, name='accounts_home'),
    path('signup/', views.signup_view, name='signup'),
    path('admin-approvals/', views.admin_approvals, name='admin_approvals'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-profiles/', views.manage_profiles, name='manage_profiles'),
    path('edit-profile/<str:profile_type>/<int:profile_id>/', views.edit_profile, name='edit_profile'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
