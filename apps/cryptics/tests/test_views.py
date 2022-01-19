""" Test the views in the cryptics app

These are generally testing user-facing behavior as a way to avoid regression issues; it would be
nice at some point in the future to cover more "under the hood" stuff and edge cases.
"""
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Contest, Submission

class CreateContestTestCase(TestCase):
	""" Test the create_contest view """
	def setUp(self):
		user_data = {
			"username": "fake_user",
			"password": "password",
		}
		self.user = User.objects.create_user(**user_data)
		self.client.login(**user_data)

		self.url = reverse("cryptics:create_contest")

	@mock.patch("apps.cryptics.models.to_discord")
	@mock.patch("apps.cryptics.models.tasks.update_contest_status.apply_async")
	def test_create_contest_success(self, mock_task: mock.MagicMock, mock_discord):
		""" Creating a contest succeeds with valid data """

		post_data = {
			"word": "EXAMPLE CONTEST (7, 7)",
		}

		self.assertFalse(Contest.objects.filter(word=post_data["word"]).exists())
		self.client.post(self.url, post_data)
		self.assertTrue(Contest.objects.filter(word=post_data["word"]).exists())

	def test_create_contest_fails_with_too_long_word(self):
		""" Display an error message if a contest word is too long """
		post_data = {
			"word": "X" * 200,
		}
		res = self.client.post(self.url, post_data, follow=True)
		expected_msg = (
			f"Maximum contest length is 150 characters; {post_data['word']} is "
			f"{len(post_data['word'])} characters long"
		)
		# Checking that the response contains the given text is kind of a blunt tool versus
		# checking request.messages or similar, but my eventual goal is to use Django forms to do
		# the validations and this specific test should continue to work regardless
		self.assertContains(res, expected_msg)

	@mock.patch("apps.cryptics.models.to_discord")
	@mock.patch("apps.cryptics.models.tasks.update_contest_status.apply_async")
	def test_create_contest_fails_with_another_open_contest(self, mock_task, mock_discord):
		""" Display error if a user opens a contest while they have another running """
		first_contest = Contest.objects.create(word="CONTEST (7)", started_by=self.user)
		post_data = {
			"word": "ANOTHER CONTEST (7, 7)",
		}
		res = self.client.post(self.url, post_data, follow=True)
		expected_msg = "Each user can only have one active contest at a time."
		self.assertContains(res, expected_msg)

		first_contest.status = Contest.VOTING
		first_contest.save()

		res = self.client.post(self.url, post_data, follow=True)
		expected_msg = "Each user can only have one active contest at a time."
		self.assertNotContains(res, expected_msg)

	@mock.patch("apps.cryptics.models.to_discord")
	@mock.patch("apps.cryptics.models.tasks.update_contest_status.apply_async")
	def test_create_contest_sends_message_to_discord(
		self, mock_task, mock_discord: mock.MagicMock
	):
		""" Send a message to Discord when a contest is created """
		post_data = {
			"word": "EXAMPLE CONTEST (7, 7)",
		}
		self.client.post(self.url, post_data)

		mock_discord.assert_called_once()
		expected_msg_fragment = f"{self.user.username} started a new contest: {post_data['word']}"
		# mock.call_args returns a tuple, where the first value is a tuple of positional args and
		# the second a dictionary of keyword args, so call_args[0][0] is the first positional arg.
		# Python 3.8 adds call_args.args as an alias to call_args[0], which would be somewhat more
		# readable.
		msg = mock_discord.call_args[0][0]
		self.assertIn(expected_msg_fragment, msg)

	@mock.patch("apps.cryptics.models.to_discord")
	@mock.patch("apps.cryptics.models.tasks.update_contest_status.apply_async")
	def test_create_contest_queues_celery_tasks(self, mock_task: mock.MagicMock, mock_discord):
		""" Creating a contest should queue Celery tasks to update their status """
		post_data = {
			"word": "EXAMPLE CONTEST (7, 7)",
		}
		self.client.post(self.url, post_data)
		contest = Contest.objects.get(word=post_data["word"])

		one_sec = datetime.timedelta(seconds=1)
		mock_task.assert_any_call(args=(contest.id,), eta=contest.submissions_end_time+one_sec)
		mock_task.assert_any_call(args=(contest.id,), eta=contest.voting_end_time+one_sec)

class ShowContestTestCase(TestCase):
	""" Test the show_contest and show_contest_full views """
	def test_show_contest_checks_if_too_old(self):
		""" The show_contest page will check if the contest is too old and needs to be closed """
		user = User.objects.create_user("fake_user")
		old_contest = Contest.objects.create(word="EXAMPLE CONTEST (7, 7)", started_by=user)
		old_contest.created_at = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
		old_contest.save()
		self.assertEqual(old_contest.status, Contest.SUBMISSIONS)

		url_kwargs = {"contest_id": old_contest.id, "word": old_contest.slugified}
		url = reverse("cryptics:show_contest_full", kwargs=url_kwargs)
		self.client.get(url)

		old_contest.refresh_from_db()
		self.assertEqual(old_contest.status, Contest.CLOSED)

class CreateSubmissionTestCase(TestCase):
	""" Test the create_submission view """
	def setUp(self):
		user_data = {
			"username": "fake_user",
			"password": "password",
		}
		self.user = User.objects.create_user(**user_data)
		self.client.login(**user_data)

		self.contest = Contest.objects.create(word="EXAMPLE (7)", started_by=self.user)

		self.url = reverse("cryptics:create_submission")

	@mock.patch("apps.cryptics.models.to_discord")
	def test_create_submission_succeeds(self, mock_discord):
		""" Creating a submission succeeds with valid data """
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
			"contest_id": self.contest.id,
		}

		self.assertFalse(Submission.objects.filter(clue=post_data["clue"]).exists())
		self.client.post(self.url, post_data)
		self.assertTrue(Submission.objects.filter(clue=post_data["clue"]).exists())

	def test_create_submission_fails_when_missing_clue(self):
		""" Display an error message when submitting with no clue """
		post_data = {
			"explanation": "letter=EX, abundant=AMPLE",
			"contest_id": self.contest.id,
		}
		res = self.client.post(self.url, post_data, follow=True)
		self.assertContains(res, "Clue is required")

	def test_create_submission_fails_when_missing_explanation(self):
		""" Display an error message when submitting with no explanation """
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"contest_id": self.contest.id,
		}
		res = self.client.post(self.url, post_data, follow=True)
		self.assertContains(res, "Explanation is required")

	def test_create_submission_fails_if_user_needs_to_like_more_clues(self):
		""" Display an error message if a user needs to like more clues before submitting """
		other_contest = Contest.objects.create(word="FAKE (4)", started_by=self.user)
		for i in range(5):
			Submission.objects.create(
				clue=f"Fake clue {i}",
				explanation=f"Fake explanation {i}",
				contest=other_contest,
				submitted_by=self.user
			)
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
			"contest_id": self.contest.id,
		}
		res = self.client.post(self.url, post_data, follow=True)
		# Our user has 5 submissions and has given 0 likes.  The rule is at least one like for
		# every two submissions, rounded down, so they would need to like two more submissions
		# before submitting again.
		expected_msg = "Please like at least 2 more clues"
		self.assertContains(res, expected_msg)

	@mock.patch("apps.cryptics.models.to_discord")
	def test_create_submission_sends_message_to_discord(self, mock_discord: mock.MagicMock):
		""" Send a message to Discord when a contest is created """
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
			"contest_id": self.contest.id,
		}
		self.client.post(self.url, post_data)

		expected_msg_fragment = f"New submission for {self.contest.word}: {post_data['clue']}"
		msg = mock_discord.call_args[0][0]
		self.assertIn(expected_msg_fragment, msg)
