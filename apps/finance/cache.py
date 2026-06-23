"""
Dashboard Cache Management

Handles caching of dashboard metrics to improve performance
and ensure data consistency across the portal.
"""

from django.core.cache import cache
from django.db.models import Q, F, Sum
from decimal import Decimal
from django.utils import timezone

from apps.students.models import FinancialRecord, Payment, StudentProfile
from apps.finance.models import Expense, Income, Budget
from apps.grades.models import Grade
from apps.students.models import AttendanceRecord


CACHE_TIMEOUT = 300  # 5 minutes for dashboard data


class DashboardCache:
    """Manage dashboard caching"""
    
    @staticmethod
    def get_admin_financial_dashboard():
        """
        Get admin financial dashboard data from cache or compute it.
        
        Returns:
            dict with financial dashboard metrics
        """
        cache_key = 'admin_financial_dashboard'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        # Compute fresh data
        from apps.finance.services import FinancialService
        data = FinancialService.get_financial_dashboard_summary()
        
        # Cache it
        cache.set(cache_key, data, CACHE_TIMEOUT)
        return data
    
    @staticmethod
    def get_student_financial_dashboard(student_id):
        """
        Get student financial dashboard data from cache or compute it.
        
        Args:
            student_id: StudentProfile ID
            
        Returns:
            dict with student financial metrics
        """
        cache_key = f'student_financial_dashboard_{student_id}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        try:
            student = StudentProfile.objects.get(id=student_id)
            from apps.finance.services import FinancialService
            data = FinancialService.get_student_financial_summary(student)
            
            # Cache it
            cache.set(cache_key, data, CACHE_TIMEOUT)
            return data
        except StudentProfile.DoesNotExist:
            return None
    
    @staticmethod
    def get_monthly_financial_summary(year, month):
        """
        Get monthly financial summary from cache or compute it.
        
        Args:
            year: Year
            month: Month
            
        Returns:
            dict with monthly metrics
        """
        cache_key = f'monthly_financial_summary_{year}_{month}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        # Compute from database
        income = Income.objects.filter(
            date__year=year,
            date__month=month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        expenses = Expense.objects.filter(
            date__year=year,
            date__month=month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        payments = Payment.objects.filter(
            payment_date__year=year,
            payment_date__month=month,
            is_approved=True,
            status='approved',
            is_reversed=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        data = {
            'year': year,
            'month': month,
            'income': income,
            'expenses': expenses,
            'payments': payments,
            'total_revenue': income + payments,
            'net_profit_loss': (income + payments) - expenses,
            'computed_at': timezone.now().isoformat()
        }
        
        # Cache it
        cache.set(cache_key, data, CACHE_TIMEOUT)
        return data
    
    @staticmethod
    def get_student_academic_summary(student_id):
        """
        Get student academic summary from cache or compute it.
        
        Args:
            student_id: StudentProfile ID
            
        Returns:
            dict with academic metrics
        """
        cache_key = f'student_academic_summary_{student_id}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        try:
            student = StudentProfile.objects.get(id=student_id)
            
            grades = Grade.objects.filter(student=student)
            
            avg_percentage = grades.aggregate(
                avg=Sum('percentage') / (Sum('percentage') / 100) if grades.count() > 0 else 0
            )
            
            data = {
                'total_subjects': grades.count(),
                'average_percentage': float(avg_percentage.get('avg', 0)),
                'last_grade_date': grades.order_by('-term').first().term if grades.exists() else None,
                'grade_count': grades.count(),
            }
            
            cache.set(cache_key, data, CACHE_TIMEOUT)
            return data
        except StudentProfile.DoesNotExist:
            return None
    
    @staticmethod
    def get_attendance_summary(student_id):
        """
        Get attendance summary from cache or compute it.
        
        Args:
            student_id: StudentProfile ID
            
        Returns:
            dict with attendance metrics
        """
        cache_key = f'student_attendance_summary_{student_id}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        try:
            student = StudentProfile.objects.get(id=student_id)
            
            records = student.attendance_records.all()
            total = records.count()
            
            if total == 0:
                return {
                    'total_records': 0,
                    'present': 0,
                    'absent': 0,
                    'late': 0,
                    'attendance_rate': 0
                }
            
            present = records.filter(status='present').count()
            absent = records.filter(status='absent').count()
            late = records.filter(status='late').count()
            
            data = {
                'total_records': total,
                'present': present,
                'absent': absent,
                'late': late,
                'attendance_rate': (present / total) * 100 if total > 0 else 0
            }
            
            cache.set(cache_key, data, CACHE_TIMEOUT)
            return data
        except StudentProfile.DoesNotExist:
            return None
    
    @staticmethod
    def invalidate_admin_dashboard():
        """Invalidate admin dashboard cache"""
        cache.delete('admin_financial_dashboard')
    
    @staticmethod
    def invalidate_student_dashboard(student_id):
        """Invalidate all student dashboard caches"""
        keys = [
            f'student_financial_dashboard_{student_id}',
            f'student_academic_summary_{student_id}',
            f'student_attendance_summary_{student_id}',
        ]
        cache.delete_many(keys)
    
    @staticmethod
    def invalidate_monthly_summary(year, month):
        """Invalidate monthly summary cache"""
        cache.delete(f'monthly_financial_summary_{year}_{month}')
