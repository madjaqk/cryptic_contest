from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.staticfiles.templatetags.staticfiles import static

import requests

SITE_URL = "http://" + Site.objects.get_current().domain

def to_discord(msg):
    """ Simple util to post messages to Discord """
    payload = {
        "content": msg,
        "username": "Machine to steal books (5)",
        "avatar_url": SITE_URL + static("cryptics/images/robot_face.png"),
    }

    for url in settings.DISCORD_URLS:
        requests.post(f"https://discordapp.com/api/webhooks/{url}", json=payload)