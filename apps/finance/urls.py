from django.urls import path

from . import views

app_name = 'finance'


urlpatterns = [
    path('', views.finance_dashboard, name='finance_dashboard'),
    path('expenses/', views.expense_list, name='finance_expenses'),
    path('expenses/add/', views.expense_create, name='finance_expense_add'),
    path('expenses/<int:pk>/edit/', views.expense_update, name='finance_expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='finance_expense_delete'),
    path('budget-management/', views.budget_management, name='finance_budget_management'),
    path('budget-management/<int:pk>/edit/', views.budget_update, name='finance_budget_edit'),
    path('profit-loss/', views.profit_and_loss, name='finance_profit_loss'),
    path('monthly-reports/', views.monthly_reports, name='finance_monthly_reports'),
    path('income/', views.income_management, name='finance_income_management'),
    path('export/<str:report_type>/', views.export_excel, name='finance_export_excel'),
]
