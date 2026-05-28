from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('students/', include('apps.students.urls')),
    path('teachers/', include('apps.teachers.urls')),
    path('assignments/', include('apps.assignments.urls')),
    path('grades/', include('apps.grades.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('calendar/', include('apps.calendarapp.urls')),
    path('news/', include('apps.news.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
