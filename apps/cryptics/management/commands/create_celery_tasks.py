""" Schedule Celery tasks to close currently-open contests """
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cryptics.models import Contest, SUBMISSIONS_LENGTH, VOTING_LENGTH
from apps.cryptics.tasks import update_contest_status

class Command(BaseCommand):
	help = "Create Celery tasks to end contests automatically"

	def handle(self, *args, **kwargs):
		earliest_time = timezone.now() - SUBMISSIONS_LENGTH - VOTING_LENGTH
		for contest in Contest.objects.filter(created_at__gt=earliest_time):
			if contest.voting_end_time > timezone.now():
				update_contest_status.apply_async(
					args=(contest.id,),
					eta=contest.voting_end_time+timedelta(seconds=1)
				)
				self.stdout.write(f"Created end voting task for {contest.word}")
				# This is intentionally one level deeper
				if contest.submissions_end_time > timezone.now():
					update_contest_status.apply_async(
						args=(contest.id,),
						eta=contest.submissions_end_time+timedelta(seconds=1)
					)
					self.stdout.write(f"Created end submission task for {contest.word}")
		self.stdout.write(self.style.SUCCESS("Finished!"))
