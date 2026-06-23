from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = 'Finance'
    
    def ready(self):
        """Register signals when app is ready"""
        import apps.finance.signals
