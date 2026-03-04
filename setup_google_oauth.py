"""Setup Google OAuth Social Application"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_booking.settings.development')

import django
django.setup()

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from decouple import config

# Update site domain for development
site, _ = Site.objects.update_or_create(
    id=1,
    defaults={
        'domain': 'localhost:8000',
        'name': 'Marvel Safari (Dev)'
    }
)
print(f"Site: {site.domain}")

# Delete ALL social apps first
all_apps = SocialApp.objects.all()
print(f"Found {all_apps.count()} total social apps")
for app in all_apps:
    print(f"  Deleting ID {app.id}: {app.provider} - {app.name}")
all_apps.delete()
print("All social apps deleted")

# Get credentials from .env
client_id = config('GOOGLE_OAUTH_CLIENT_ID', default='')
client_secret = config('GOOGLE_OAUTH_CLIENT_SECRET', default='')

if not client_id or not client_secret:
    print("ERROR: GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in .env")
    exit(1)

print(f"Client ID: {client_id[:20]}...")

# Create the social app (we already deleted duplicates above)
app = SocialApp.objects.create(
    provider='google',
    name='Google',
    client_id=client_id,
    secret=client_secret,
)

# Associate with site
app.sites.add(site)

print("SUCCESS: Google OAuth Social Application created!")
print(f"App ID: {app.id}")
print("You can now use 'Login with Google' on your site.")
