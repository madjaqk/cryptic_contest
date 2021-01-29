import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.staticfiles.templatetags.staticfiles import static

import requests

logger = logging.getLogger(__name__)

SITE_URL = "https://" + Site.objects.get_current().domain

def get_discord_pingable_role():
    logger.info("Inside get_discord_pingable_role")
    if settings.DISCORD_CRYPTIC_CONTEST_ROLE_ID:
        logger.info(f"settings.DISCORD_CRYPTIC_CONTEST_ROLE_ID={settings.DISCORD_CRYPTIC_CONTEST_ROLE_ID}")
        return f"<@&{settings.DISCORD_CRYPTIC_CONTEST_ROLE_ID}> "
    logger.info("No DISCORD_CRYPTIC_CONTEST_ROLE_ID")
    return ""

def to_discord(msg):
    """ Simple util to post messages to Discord """
    payload = {
        "content": msg,
        "username": "Machine to steal books (5)",
        "avatar_url": SITE_URL + static("cryptics/images/robot_face.png"),
    }

    if settings.DISCORD_URL:
        requests.post(f"https://discordapp.com/api/webhooks/{settings.DISCORD_URL}", json=payload)
    else:
        print(payload)
