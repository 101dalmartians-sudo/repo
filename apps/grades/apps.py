from django.apps import AppConfig


class GradesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.grades'
    
    def ready(self):
        """Register signals when app is ready"""
        import apps.grades.signals
