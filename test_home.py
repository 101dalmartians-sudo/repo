#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aspireacademy.settings')
django.setup()

from django.test import Client

# Test home page
c = Client()
response = c.get('/', HTTP_HOST='127.0.0.1')

print("=" * 60)
print("HOME URL TEST RESULTS")
print("=" * 60)
print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.get('content-type', 'Not set')}")
print(f"Response Length: {len(response.content)} bytes")
print()

# Check for key elements
html = response.content.decode('utf-8')
checks = {
    "Has 'Aspire Academy' title": 'Aspire Academy' in html,
    "Has 'Aspiring for excellence' subtitle": 'Aspiring for excellence' in html,
    "Has Gallery section": 'Gallery' in html,
    "Has News highlights": 'News highlights' in html,
    "Has Student Login button": 'Student Login' in html,
    "Has Teacher Login button": 'Teacher Login' in html,
    "Has Admin Login button": 'Admin Login' in html,
    "Has background image reference": 'home_bg.jpg' in html,
    "Has gallery slideshow script": 'gallerySlides' in html,
    "Gallery images loaded": 'gallery-slide' in html,
}

print("CONTENT CHECKS:")
for check, result in checks.items():
    status = "✓" if result else "✗"
    print(f"  {status} {check}")

print()
print("=" * 60)
if response.status_code == 200 and all(checks.values()):
    print("✓ HOME PAGE IS FULLY FUNCTIONAL")
else:
    print("✗ HOME PAGE HAS ISSUES - See above")
print("=" * 60)
