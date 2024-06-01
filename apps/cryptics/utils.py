""" Utility functions for the cryptics module """
import logging
from functools import cache

from django.conf import settings
from django.contrib.sites.models import Site
from django.templatetags.static import static
import requests

logger = logging.getLogger(__name__)


@cache
def get_site_url():
	return "https://" + Site.objects.get_current().domain


def get_discord_pingable_role():
	""" Get the Discord role ID from settings (if it's defined) and format it appropriately """
	if settings.DISCORD_CRYPTIC_CONTEST_ROLE_ID:
		return f"<@&{settings.DISCORD_CRYPTIC_CONTEST_ROLE_ID}> "

	return ""


def to_discord(msg):
	""" Simple util to post messages to Discord

	Arguably, this should be moved to a Celery task so that the message can be sent to Discord
	asynchronously, but so far there hasn't been an issue.
	"""
	payload = {
		"content": msg,
		"username": "Machine to steal books (5)",
		"avatar_url": get_site_url() + static("cryptics/images/robot_face.png"),
	}

	if settings.DISCORD_URL:
		requests.post(f"https://discordapp.com/api/webhooks/{settings.DISCORD_URL}", json=payload)
		logger.info("Sent to Discord %s", payload)
	else:
		print(payload)
