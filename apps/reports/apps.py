"""Reports app configuration"""
from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'
    verbose_name = 'Student Reports'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.reports.signals
