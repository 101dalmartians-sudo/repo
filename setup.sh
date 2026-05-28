# POSIX setup script
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
echo "Setup complete. Run: source venv/bin/activate then python manage.py runserver"
