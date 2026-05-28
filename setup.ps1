# PowerShell setup script
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
Write-Host "Setup complete. Run: venv\Scripts\Activate.ps1 then python manage.py runserver"
