import datetime
import logging

from django.db import models, transaction
from django.db.models import Count
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from . import tasks
from .utils import get_discord_pingable_role, get_site_url, to_discord

logger = logging.getLogger(__name__)

SUBMISSIONS_LENGTH = datetime.timedelta(days=2, minutes=2)
VOTING_LENGTH = datetime.timedelta(days=2, minutes=2)
RECENT_LENGTH = datetime.timedelta(days=7)


class ContestManager(models.Manager):
	""" Custom manager for the Contest model """
	def add(self, word, started_by):
		""" Create a new contest, post Discord message, and queue Celery tasks """
		new_contest = self.create(word=word.upper(), started_by=started_by)

		msg = (
			f"{get_discord_pingable_role()}{new_contest.started_by} started a new contest: "
			f"{new_contest.word} -- {get_site_url()}{new_contest.get_absolute_url()}"
		)
		to_discord(msg)

		tasks.update_contest_status.apply_async(
			args=(new_contest.id,),
			eta=new_contest.submissions_end_time+datetime.timedelta(seconds=1)
		)
		tasks.update_contest_status.apply_async(
			args=(new_contest.id,),
			eta=new_contest.voting_end_time+datetime.timedelta(seconds=1)
		)

		return new_contest

	def ended_recently(self):
		""" Return contests that closed recently """
		return self.filter(
			status=Contest.CLOSED,
			created_at__gt=timezone.now()-(SUBMISSIONS_LENGTH+VOTING_LENGTH+RECENT_LENGTH)
		).order_by("-created_at")


class Contest(models.Model):
	""" A contest (a word for which cryptic clues should be written) """
	word = models.CharField(max_length=150)
	started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contests_started")

	winning_entry = models.OneToOneField(
		"Submission",
		on_delete=models.CASCADE,
		related_name="contest_this_won",
		null=True,
		blank=True
	)
	winning_user = models.ForeignKey(
		User, on_delete=models.CASCADE, related_name="contests_won", null=True, blank=True
	)

	SUBMISSIONS = "S"
	VOTING = "V"
	CLOSED = "C"

	STATUS_CHOICES = (
		(SUBMISSIONS, "submissions"),
		(VOTING, "voting"),
		(CLOSED, "closed"),
	)

	status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=SUBMISSIONS)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = ContestManager()

	class Meta:
		ordering = ["created_at"]

	@property
	def submissions_end_time(self):
		return self.created_at + SUBMISSIONS_LENGTH

	@property
	def voting_end_time(self):
		return self.created_at + SUBMISSIONS_LENGTH + VOTING_LENGTH

	# These properties are so that I can check status on templates without hardcoding in
	# `contest.status == "S"` (or whatever)
	@property
	def is_submissions(self):
		return self.status == self.SUBMISSIONS

	@property
	def is_voting(self):
		return self.status == self.VOTING

	@property
	def is_closed(self):
		return self.status == self.CLOSED

	@property
	def slugified(self):
		return slugify(self.word)

	def __str__(self):
		return f"Contest: {self.word}"

	def get_absolute_url(self):
		url_kwargs = {
			"contest_id": self.id,
			"word": self.slugified,
		}
		return reverse("cryptics:show_contest_full", kwargs=url_kwargs)

	def submissions_sorted(self):
		""" Return submissions sorted by like count if a contest is closed, creation date otherwise """
		submissions = self.submissions.select_related("submitted_by")
		if self.is_closed:
			return submissions.prefetch_related(
				"likers"
			).annotate(
				like_count=Count("likers")
			).order_by(
				"-like_count", "created_at"
			)
		return submissions.order_by("created_at")

	def declare_winner(self):
		""" Mark the submission with the most votes as the contest's winner and notify Discord """
		send_message = False
		if self.submissions.exists():
			with transaction.atomic():
				self.refresh_from_db()
				if self.winning_entry is None:
					winning_entry = self.submissions.annotate(
						likes=models.Count("likers")
					).order_by(
						"-likes", "created_at"
					).first()
					self.winning_entry = winning_entry
					self.winning_user = winning_entry.submitted_by
					self.save()
					send_message = True

		if send_message:
			msg = (
				f"Voting is closed for {self.word}!  The winning clue is:\n"
				f"**{self.winning_entry.clue}**\nSubmitted by {self.winning_entry.submitted_by}.  "
				f"Congratulations!  {get_site_url()}{self.get_absolute_url()}"
			)
			to_discord(msg)

	def deactivate(self):
		""" Declare a winner and close the contest """
		self.declare_winner()

		self.status = self.CLOSED
		self.save()

	def switch_to_voting(self):
		""" Change the phase to voting and notify Discord """
		send_message = False
		with transaction.atomic():
			self.refresh_from_db()
			if self.status == self.SUBMISSIONS:
				self.status = self.VOTING
				self.save()
				send_message = True

		if send_message:
			msg = (
				f"{get_discord_pingable_role()}Voting is now open for {self.word}! "
				f"{get_site_url()}{self.get_absolute_url()}"
			)
			to_discord(msg)

	def check_if_too_old(self):
		""" Move contest to the next phase if enough time has passed """
		if self.is_closed:
			return None
		if timezone.now() > self.voting_end_time:
			logger.info("Closing contest %s", self.word)
			self.deactivate()
		elif self.is_submissions and timezone.now() > self.submissions_end_time:
			logger.info("Switching contest %s to voting", self.word)
			self.switch_to_voting()


class SubmissionQuerySet(models.query.QuerySet):
	def order_by_like_count(self, *, reverse=False):
		""" Order submissions by number of likes (default descending).

		This will also annotate the queryset with like count and select/prefetch related fields. """
		submissions = self.select_related("contest").prefetch_related("likers")

		if reverse:
			sort_fields = ("like_count", "created_at")
		else:
			sort_fields = ("-like_count", "created_at")

		return submissions.annotate(like_count=models.Count("likers")).order_by(*sort_fields)


class SubmissionManager(models.Manager):
	""" Custom manager for the Submission model """
	def get_queryset(self):
		return SubmissionQuerySet(self.model, using=self._db)

	def add(self, clue: str, explanation: str, contest: Contest, submitted_by: User):
		""" Validate a clue submission and create it if there are no errors """
		new_sub = self.create(clue=clue, explanation=explanation, contest=contest, submitted_by=submitted_by)

		msg = (
			f"New submission for {new_sub.contest.word}: {new_sub.clue} -- "
			f"<{get_site_url()}{new_sub.get_absolute_url()}>"
		)
		to_discord(msg)

		return new_sub


class Submission(models.Model):
	""" A clue submitted to a given contest """
	clue = models.TextField()
	explanation = models.TextField()
	contest = models.ForeignKey(Contest, related_name="submissions", on_delete=models.CASCADE)
	# TODO: Change the submitted_by on_delete to allow clues to continue existing, just with the user
	# listed as "deleted user" or somesuch
	submitted_by = models.ForeignKey(User, related_name="submissions", on_delete=models.CASCADE)
	likers = models.ManyToManyField(User, related_name="clues_liked", blank=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = SubmissionManager()

	class Meta:
		ordering = ["created_at"]

	@property
	def sort_order(self):
		""" This is used to sort submissions on the contest show page. """
		return (-self.likers.count(), self.created_at)

	def __str__(self):
		return f"Submission: {self.clue}, by {self.submitted_by}"

	def get_absolute_url(self):
		url_kwargs = {
			"contest_id": self.contest.id,
			"word": self.contest.slugified,
		}
		url = (
			reverse("cryptics:show_contest_full", kwargs=url_kwargs)
			+ f"?highlight={self.id}#clue{self.id}"
		)
		return url


def sort_users():
	""" Sort users based on the number of contests won and average number of likes

	This function is monkey patched into the User manager, because it's a built-in I don't have
	direct access to.  (The correct way to do this would have been a proxy model, but this works
	so it's not a pressing concern.)

	For people (such as me in the future) who wonder why this only annotates the total number of
	likes rather all of the fields: It turns out there's a longstanding Django issue about
	multiple annotations that causes them to report the wrong values--effectively,
	Model.objects.annotate(a_count=Count("a"), b_count=Count("b")) ends up reporting both a_count
	and b_count as a*b.  The simplest workaround is to use distinct=True inside the count, but
	that doesn't work for counting total number of likes received--it results in the total number
	of users who have liked _any_ clue from this user, not a total of likes they've received
	across every clue.  There are more complicated workarounds using subqueries, but I didn't have
	luck with them and what's below already gives a 20x speed-up over what I had before, so I
	don't think it's pressing.

	Django ticket here: https://code.djangoproject.com/ticket/10060
	"""
	users = User.objects.annotate(
		total_likes=Count("submissions__likers")
	).prefetch_related("contests_won", "submissions", "clues_liked")
	users_list = []
	for user in users:
		contests_won = user.contests_won.all().count()
		total_submissions = user.submissions.all().count()
		total_likes = user.total_likes
		average_likes = total_likes/total_submissions if total_submissions else 0
		clues_liked = user.clues_liked.count()
		users_list.append({
			"user": user,
			"contests_won": contests_won,
			"total_submissions": total_submissions,
			"total_likes": total_likes,
			"average_likes": average_likes,
			"clues_liked": clues_liked,
		})

	users_list.sort(key=lambda x: (-x["contests_won"], -x["average_likes"]))

	return users_list


User.objects.sort_users = sort_users
