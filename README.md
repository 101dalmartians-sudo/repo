# Aspire Academy Portal

Aspire Academy Portal is a Django-based school portal scaffold with user registration, admin approval, student and teacher dashboards, assignment uploads, grade tracking, notifications, and calendar support.

## Features

- Student, teacher, and admin user signup workflows
- Admin approval workflow with a 10-admin limit (first five admins are auto-approved)
- Student and teacher dashboards
- Assignment upload notifications
- Grade entry and Cambridge letter grade calculation
- Basic Celery/Redis-ready configuration
- GitHub Actions CI for migration and test verification

## Local setup

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Unix / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment

Copy `.env.example` to `.env` and update values for your environment.

Example variables:

```env
DJANGO_SECRET_KEY=replace-me
DEBUG=True
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@aspireacademy.local
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_ALWAYS_EAGER=True
```

## Testing

Run Django tests locally:

```bash
python manage.py test
```

## GitHub Actions

The CI workflow is defined in `.github/workflows/django.yml`. It installs dependencies, runs migrations, and executes the Django test suite on push and pull request events.

## Docker

A basic Docker setup is included for local containerized testing.

Build and start the app:

```bash
docker compose up --build
```

The web service listens on `http://localhost:8000` and applies migrations automatically at container startup.

## Celery and email

Development email is sent to the console by default. To start Celery with Redis:

```bash
docker compose up -d redis
docker compose run web celery -A aspireacademy worker --loglevel=info
```

If Redis is unavailable, use eager task execution in `.env`:

```env
CELERY_TASK_ALWAYS_EAGER=True
```

## Project structure

- `aspireacademy/` — Django project settings and URL configuration
- `apps/accounts/` — authentication, signup, admin approval
- `apps/students/` — student profile and dashboard
- `apps/teachers/` — teacher profile and dashboard
- `apps/assignments/` — assignment upload and notifications
- `apps/grades/` — grade models and calculation logic
- `apps/notifications/` — notification model and tests
- `templates/` — Tailwind-based frontend templates
