import datetime
import threading

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.template.defaultfilters import pluralize

CONTEST_LENGTH = datetime.timedelta(days=2)
CONTEST_LENGTH_IN_SECONDS = CONTEST_LENGTH.days*24*60*60 + CONTEST_LENGTH.seconds

class ContestManager(models.Manager):
	def add(self, word, started_by):
		new_contest = self.create(word=word.upper(), started_by=started_by)
		t = threading.Timer(CONTEST_LENGTH_IN_SECONDS, new_contest.deactivate)
		t.start()

class Contest(models.Model):
	word = models.CharField(max_length=50)
	active = models.BooleanField(default=True)
	started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contests_started")

	winning_entry = models.OneToOneField("Submission", on_delete=models.CASCADE, related_name="contest_this_won", null=True, blank=True)
	winning_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contests_won", null=True, blank=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = ContestManager()

	@property
	def end_time(self):
		return self.created_at + CONTEST_LENGTH

	def __str__(self):
		return f"Contest: {self.word}"

	def declare_winner(self):
		if self.submissions.exists():
			winning_entry = self.submissions.annotate(likes=models.Count("likers")).order_by("-likers", "created_at").first()
			self.winning_entry = winning_entry
			self.winning_user = winning_entry.submitted_by
			self.save()

	def deactivate(self):
		self.declare_winner()

		self.active = False
		self.save()

	def check_if_too_old(self):
		if self.active and timezone.now() > self.end_time:
			self.deactivate()

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

		if not contest.active:
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
	likers = models.ManyToManyField(User, related_name="clues_liked")

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = SubmissionManager()

	def sort_order(self):
		return (-self.likers.count(), self.created_at)

def sort_users():
	# sort_users method to monkeypatch into User manager, because it's a built-in I don't have direct access to.
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