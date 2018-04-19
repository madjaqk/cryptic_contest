import datetime
import threading

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.template.defaultfilters import pluralize

def to_seconds(td):
	return td.days*24*60*60 + td.seconds + td.microseconds

# SUBMISSIONS_LENGTH = datetime.timedelta(days=2, minutes=2)
# VOTING_LENGTH = datetime.timedelta(days=2, minutes=2)

SUBMISSIONS_LENGTH = datetime.timedelta(minutes=10)
VOTING_LENGTH = datetime.timedelta(minutes=10)

class ContestManager(models.Manager):
	def add(self, word, started_by):
		new_contest = self.create(word=word.upper(), started_by=started_by)
		t = threading.Timer(to_seconds(SUBMISSIONS_LENGTH), new_contest.switch_to_voting)
		t.start()

class Contest(models.Model):
	word = models.CharField(max_length=50)
	started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contests_started")

	winning_entry = models.OneToOneField("Submission", on_delete=models.CASCADE, related_name="contest_this_won", null=True, blank=True)
	winning_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contests_won", null=True, blank=True)

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

	@property
	def submissions_end_time(self):
		if self.is_submissions:
			return self.created_at + SUBMISSIONS_LENGTH

	@property
	def voting_end_time(self):
		if self.is_voting or self.is_submissions:
			return self.created_at + SUBMISSIONS_LENGTH + VOTING_LENGTH

	# These properties are so that I can check status on templates without hardcoding in `contest.status == "S"` (or whatever)
	@property
	def is_submissions(self):
		return self.status == self.SUBMISSIONS

	@property
	def is_voting(self):
		return self.status == self.VOTING

	@property
	def is_closed(self):
		return self.status == self.CLOSED

	def __str__(self):
		return f"Contest: {self.word}"

	def declare_winner(self):
		if self.submissions.exists():
			winning_entry = self.submissions.annotate(likes=models.Count("likers")).order_by("-likes", "created_at").first()
			self.winning_entry = winning_entry
			self.winning_user = winning_entry.submitted_by
			self.save()

	def deactivate(self):
		self.declare_winner()

		self.status = self.CLOSED
		self.save()

	def switch_to_voting(self):
		self.status = self.VOTING
		self.save()
		t = threading.Timer(to_seconds(VOTING_LENGTH), self.deactivate)
		t.start()

	def check_if_too_old(self):
		if self.is_closed:
			return None
		if timezone.now() > self.voting_end_time:
			self.deactivate()
		elif self.is_submissions and timezone.now() > self.submissions_end_time:
			self.switch_to_voting()

class SubmissionManager(models.Manager):
	def add(self, data, user):
		errors = []
		if not data["clue"]:
			errors.append("Clue is required")
		if not data["explanation"]:
			errors.append("Explanation is required")
		if not data["contest_id"]:
			errors.append("No contest was specified (somehow)")
		if not user:
			errors.append("Must be logged in to submit a clue (this specific error shouldn't trigger)")

		likes_needed_to_give = user.submissions.count() // 2 - user.clues_liked.count()

		if likes_needed_to_give > 0:
			errors.append(f"Please like at least {likes_needed_to_give} more clue{pluralize(likes_needed_to_give)}")

		contest = Contest.objects.get(id=data["contest_id"])

		contest.check_if_too_old()

		if not contest.is_submissions:
			errors.append("Sorry, this contest has closed")

		if errors:
			return {"status": False, "errors": errors}
		else:
			new_sub = Submission(clue=data["clue"], explanation=data["explanation"], contest=contest, submitted_by=user)
			new_sub.save()
			return {"status": True}

class Submission(models.Model):
	clue = models.TextField()
	explanation = models.TextField()
	contest = models.ForeignKey(Contest, related_name="submissions", on_delete=models.CASCADE)
	submitted_by = models.ForeignKey(User, related_name="submissions", on_delete=models.CASCADE)
	likers = models.ManyToManyField(User, related_name="clues_liked", blank=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = SubmissionManager()

	def sort_order(self):
		return (-self.likers.count(), self.created_at)

	def __str__(self):
		return f"Submission: {self.clue}, by {self.submitted_by}"

def sort_users():
	# sort_users method to monkeypatch into User manager, because it's a built-in I don't have direct access to.
	# The correct way to do this would have been a proxy model, but this works so not a pressing change.
	users = User.objects.all()
	users_list = []
	for user in users:
		contests_won = user.contests_won.all().count()
		total_submissions = user.submissions.all().count()
		total_likes = sum(sub.likers.all().count() for sub in user.submissions.all())
		average_likes = total_likes/total_submissions if total_submissions else 0
		users_list.append({
			"user": user,
			"contests_won": contests_won,
			"total_submissions": total_submissions,
			"total_likes": total_likes,
			"average_likes": average_likes
			})

	# The above for-loop is an ugly mess and probably pretty inefficient.  It seems like it should be possible to accomplish this with the Django ORM and annotate queries, but I couldn't get it to work (specifically, I couldn't wrangle the correct answers for total number of likes of all submissions, and the division added additional wrinkles).  I would love if someone could figure out the "proper" way to achieve this.

	users_list.sort(key=lambda x:(-x["contests_won"], -x["average_likes"]))

	return users_list

User.objects.sort_users = sort_users