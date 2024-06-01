""" Test the views in the cryptics app

These are generally testing user-facing behavior as a way to avoid regression issues; it would be
nice at some point in the future to cover more "under the hood" stuff and edge cases.
"""
import datetime
from http import HTTPStatus
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized

from ..models import Contest, Submission


class CreateContestTestCase(TestCase):
	""" Test the index POST view used to create new contests """
	def setUp(self):
		user_data = {
			"username": "fake_user",
			"password": "password",
		}
		self.user = User.objects.create_user(**user_data)
		self.client.login(**user_data)

		self.url = reverse("cryptics:index")

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
		expected_msg = f"Ensure this value has at most 150 characters (it has {len(post_data['word'])})"
		# Checking that the response contains the given text is kind of a blunt tool, but this was written before the
		# site was updated to use Django forms, so it serves as a regression test that's not implemenation-specific
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
	def test_create_contest_uses_request_user_not_form_data_to_determine_started_by(self, mock_task, mock_discord):
		""" Creating a contest sets started_by based on the logged-in user

		The ContestForm includes a started_by field, but it should be set by the view; if this information is included
		in the POST body, it should be silently ignored.
		"""
		post_data = {
			"word": "CONTEST (7)",
			"started_by": self.user.id + 1,
		}

		self.assertFalse(Contest.objects.filter(word=post_data["word"]).exists())

		self.client.post(self.url, post_data)

		contest = Contest.objects.get(word=post_data["word"])
		self.assertEqual(contest.started_by, self.user)

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
		user = User.objects.create_user(username="fake_user")
		old_contest = Contest.objects.create(word="EXAMPLE CONTEST (7, 7)", started_by=user)
		old_contest.created_at = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
		old_contest.save()
		self.assertEqual(old_contest.status, Contest.SUBMISSIONS)

		url_kwargs = {"contest_id": old_contest.id, "word": old_contest.slugified}
		url = reverse("cryptics:show_contest_full", kwargs=url_kwargs)
		self.client.get(url)

		old_contest.refresh_from_db()
		self.assertEqual(old_contest.status, Contest.CLOSED)

	@parameterized.expand([(Contest.SUBMISSIONS,), (Contest.VOTING,)])
	def test_show_contest_sorts_submissions_by_date_created_if_contest_is_not_closed(self, current_status: str):
		""" Before a contest is closed and a winner determined, show_contest should list clues in submission order

		It shouldn't be possible for a contest in the SUBMISSIONS phase to have submissions that have votes, but
		that's business logic, not enforced by the database
		"""
		users = [User.objects.create(username=f"user_{i}") for i in range(3)]
		contest = Contest.objects.create(word="EXAMPLE (7)", started_by=users[0], status=current_status)

		# Five clues, with vote totals 1, 0, 2, 2, and 1, but for these statuses it doesn't matter, we just want
		# submission order

		clues = [contest.submissions.create(clue=str(i)*50, submitted_by=users[0]) for i in range(5)]
		clues[0].likers.add(users[1])
		clues[1].likers.add()  # This line isn't necessarily, I just think it's clearer to include it in the sequence
		clues[2].likers.add(users[1], users[2])
		clues[3].likers.add(users[1], users[2])
		clues[4].likers.add(users[1])

		url = reverse("cryptics:show_contest_full", kwargs={"contest_id": contest.id, "word": contest.slugified})
		res = self.client.get(url)

		res_content = res.content.decode("utf-8")
		self.assertLess(res_content.index(clues[0].clue), res_content.index(clues[1].clue))
		self.assertLess(res_content.index(clues[1].clue), res_content.index(clues[2].clue))
		self.assertLess(res_content.index(clues[2].clue), res_content.index(clues[3].clue))
		self.assertLess(res_content.index(clues[3].clue), res_content.index(clues[4].clue))

	def test_show_contest_sorts_submissions_by_number_of_votes_if_contest_is_closed(self):
		""" After a contest is closed, show_contest should list clues in descending order of votes

		In case of a tie, it should use the date submitted
		"""
		users = [User.objects.create(username=f"user_{i}") for i in range(3)]
		contest = Contest.objects.create(word="EXAMPLE (7)", started_by=users[0], status=Contest.CLOSED)

		# Five clues, with vote totals 1, 0, 2, 2, and 1, so the correct order is clue 2, 3, 0, 4, 1

		clues = [contest.submissions.create(clue=str(i) * 50, submitted_by=users[0]) for i in range(5)]
		clues[0].likers.add(users[1])
		clues[1].likers.add()  # This line isn't necessarily, I just think it's clearer to include it in the sequence
		clues[2].likers.add(users[1], users[2])
		clues[3].likers.add(users[1], users[2])
		clues[4].likers.add(users[1])

		url = reverse("cryptics:show_contest_full", kwargs={"contest_id": contest.id, "word": contest.slugified})
		res = self.client.get(url)

		res_content = res.content.decode("utf-8")
		self.assertLess(res_content.index(clues[2].clue), res_content.index(clues[3].clue))
		self.assertLess(res_content.index(clues[3].clue), res_content.index(clues[0].clue))
		self.assertLess(res_content.index(clues[0].clue), res_content.index(clues[4].clue))
		self.assertLess(res_content.index(clues[4].clue), res_content.index(clues[1].clue))

	def test_show_contest_handles_queries_efficiently(self):
		""" The show_contest_full endpoint gets the number of likes for each clue with a constant number of queries

		This should be 4 queries total:
		1. Select the contest with the specified ID and related objects (done in get_object_or_404 inside
			show_contest_full)
		2. Check if any submissions exist (in the show.html template, to determine if the table of submissions should
			be shown at all)
		3. Select all submissions for this contest, including the like count (in contest.submissions_sorted, called in
			the show.html template, to construct the table of submissions)
		4. Select information about all users who liked any clues for this contest (as part of the prefetch_related
			clause in the contest.submissions_sorted query referenced above—for people not familiar, a
			prefetch_related clause is used for many-to-many relationships; Django will select rows from table A in
			one query, table B in another, and then join that data at the Python level)
		"""
		users = [User.objects.create(username=f"user_{i}") for i in range(3)]
		contest = Contest.objects.create(word="EXAMPLE (7)", started_by=users[0], status=Contest.CLOSED)

		# The specific pattern of clues and likes doesn't matter at all for this test
		clues = [contest.submissions.create(clue=str(i) * 50, submitted_by=users[1]) for i in range(10)]
		clues[1].likers.add(users[1])
		clues[3].likers.add(users[1], users[2])

		contest.declare_winner()

		url = reverse("cryptics:show_contest_full", kwargs={"contest_id": contest.id, "word": contest.slugified})
		with self.assertNumQueries(4):
			res = self.client.get(url)
		self.assertEqual(res.status_code, HTTPStatus.OK)


class CreateSubmissionTestCase(TestCase):
	""" Test POSTing to the show_contest_full view """
	def setUp(self):
		user_data = {
			"username": "fake_user",
			"password": "password",
		}
		self.user = User.objects.create_user(**user_data)
		self.client.login(**user_data)

		self.contest = Contest.objects.create(word="EXAMPLE (7)", started_by=self.user)

		self.url = reverse(
			"cryptics:show_contest_full", kwargs={"contest_id": self.contest.id, "word": self.contest.slugified}
		)

	@mock.patch("apps.cryptics.models.to_discord")
	def test_create_submission_succeeds(self, mock_discord):
		""" Creating a submission succeeds with valid data """
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
		}

		self.assertFalse(Submission.objects.filter(clue=post_data["clue"]).exists())
		res = self.client.post(self.url, post_data, follow=True)
		self.assertEqual(res.status_code, HTTPStatus.OK, res.content)
		self.assertTrue(Submission.objects.filter(clue=post_data["clue"]).exists())

	def test_create_submission_fails_when_missing_clue(self):
		""" Display an error message when submitting with no clue """
		post_data = {
			"explanation": "letter=EX, abundant=AMPLE",
		}
		res = self.client.post(self.url, post_data, follow=True)
		self.assertContains(res, "Clue is required")

	def test_create_submission_fails_when_missing_explanation(self):
		""" Display an error message when submitting with no explanation """
		post_data = {
			"clue": "Letter with abundant illustration (7)",
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
		}
		res = self.client.post(self.url, post_data, follow=True)
		# Our user has 5 submissions and has given 0 likes.  The rule is at least one like for
		# every two submissions, rounded down, so they would need to like two more submissions
		# before submitting again.
		expected_msg = "Please like at least 2 more clues"
		self.assertContains(res, expected_msg)

	@mock.patch("apps.cryptics.models.to_discord")
	def test_create_contest_uses_request_user_not_form_data_to_determine_submitted_by(self, mock_discord):
		""" Creating a submission sets submitted_by based on the logged-in user

		The SubmissionForm includes a submitted_by field, but it should be set by the view; if this information is
		included in the POST body, it should be silently ignored.
		"""
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
			"submitted_by": self.user.id + 1,
		}

		self.assertFalse(Submission.objects.filter(clue=post_data["clue"]).exists())
		self.client.post(self.url, post_data)
		clue = Submission.objects.get(clue=post_data["clue"])
		self.assertEqual(clue.submitted_by, self.user)

	@mock.patch("apps.cryptics.models.to_discord")
	def test_create_contest_uses_url_not_form_data_to_determine_contest(self, mock_discord):
		""" Creating a submission sets contest based on the URL that was POSTed to

		The SubmissionForm includes a contest field, but it should be set by the view; if this information is included
		in the POST body, it should be silently ignored.
		"""
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
			"contest": self.contest.id + 1,
		}

		self.assertFalse(Submission.objects.filter(clue=post_data["clue"]).exists())
		self.client.post(self.url, post_data)
		clue = Submission.objects.get(clue=post_data["clue"])
		self.assertEqual(clue.contest, self.contest)

	@mock.patch("apps.cryptics.models.to_discord")
	def test_create_submission_sends_message_to_discord(self, mock_discord: mock.MagicMock):
		""" Send a message to Discord when a contest is created """
		post_data = {
			"clue": "Letter with abundant illustration (7)",
			"explanation": "letter=EX, abundant=AMPLE",
		}
		self.client.post(self.url, post_data)

		expected_msg_fragment = f"New submission for {self.contest.word}: {post_data['clue']}"
		mock_discord.assert_called_once()
		msg = mock_discord.call_args[0][0]
		self.assertIn(expected_msg_fragment, msg)


class ShowUserTestCase(TestCase):
	""" Test the show_user endpoint """
	def test_show_user_sorts_submissions_by_number_of_votes_if_contest_is_closed(self):
		""" The show_user page should list clues in descending order of votes

		In case of a tie, it should use the date submitted
		"""
		users = [User.objects.create(username=f"user_{i}") for i in range(3)]
		contest = Contest.objects.create(word="EXAMPLE (7)", started_by=users[0], status=Contest.CLOSED)

		# Five clues, with vote totals 1, 0, 2, 2, and 1, so the correct order is clue 2, 3, 0, 4, 1

		clues = [contest.submissions.create(clue=str(i) * 50, submitted_by=users[0]) for i in range(5)]
		clues[0].likers.add(users[1])
		clues[1].likers.add()  # This line isn't necessarily, I just think it's clearer to include it in the sequence
		clues[2].likers.add(users[1], users[2])
		clues[3].likers.add(users[1], users[2])
		clues[4].likers.add(users[1])

		url = reverse("cryptics:show_user", kwargs={"user_id": users[0].id})
		res = self.client.get(url)

		res_content = res.content.decode("utf-8")
		self.assertLess(res_content.index(clues[2].clue), res_content.index(clues[3].clue))
		self.assertLess(res_content.index(clues[3].clue), res_content.index(clues[0].clue))
		self.assertLess(res_content.index(clues[0].clue), res_content.index(clues[4].clue))
		self.assertLess(res_content.index(clues[4].clue), res_content.index(clues[1].clue))

	@parameterized.expand([(Contest.SUBMISSIONS,), (Contest.VOTING,)])
	def test_show_user_does_not_show_clues_for_contests_that_are_not_closed(self, status):
		""" The show_user page hides clues for contests that are still open or in voting

		This is because clues are supposed to be anonymous until after the winner is revealed
		"""
		user = User.objects.create(username="user")
		closed_contest = Contest.objects.create(word="ONE (3)", started_by=user, status=Contest.CLOSED)
		not_closed_contest = Contest.objects.create(word="TWO (3)", started_by=user, status=status)

		closed_clue = closed_contest.submissions.create(clue="Clue for a closed contest", submitted_by=user)
		not_closed_clue = not_closed_contest.submissions.create(clue="Other contest clue", submitted_by=user)

		url = reverse("cryptics:show_user", kwargs={"user_id": user.id})
		res = self.client.get(url)
		self.assertEqual(res.status_code, HTTPStatus.OK, msg=res.content)
		self.assertContains(res, closed_clue.clue)
		self.assertNotContains(res, not_closed_clue.clue)

	def test_show_user_handles_queries_efficiently(self):
		""" The show_user page gets the number of likes for each clue with a constant number of queries

		The five queries total should be:
		1. Retrieve information about the user (done in get_object_or_404 inside show_user)
		2. Select contests the user started (in user_show.html)
		3. Select contests the user won (in user_show.html)
		4. Check if the user has any submissions whatsoever (in user_show.html, to determine if the table of
			submissions should be rendered)
		5. Retrieve information about all of the user's submissions (in user_show.html, specifically calling
			this_user.submissions.all_order_by_like_count)
		6. Select information about all users who liked any clues for this contest (as part of a prefetch_related
			clause in this_user.submissions.all_order_by_like_count)

		Queries 2 and 3 could be replaced with prefetch_related, but since we'd only be prefetching for one object,
		it'll work out to the same number of queries.
		"""
		user = User.objects.create(username="user")
		liking_user = User.objects.create(username="liking_user")
		contest = Contest.objects.create(word="CONTEST (7)", started_by=user, status=Contest.CLOSED)
		for i in range(10):
			submission = contest.submissions.create(clue=f"Clue {i}", submitted_by=user)
			if i % 2 == 0:
				submission.likers.add(liking_user)

		url = reverse("cryptics:show_user", kwargs={"user_id": user.id})
		with self.assertNumQueries(6):
			res = self.client.get(url)

		self.assertEqual(res.status_code, HTTPStatus.OK, msg=res.content)


class AllClosedContestsTestCase(TestCase):
	""" Test the all_closed_contests endpoint """
	def test_all_closed_contests_handles_queries_efficiently(self):
		""" all_closed_contests should use select_related to use a single query to gather all relevant information

		Because the all_closed_contests template uses information about each contest's started_by user, winning entry,
		and winning user, there's a potential N+1 (or, really, 3N+1) query problem
		"""
		user = User.objects.create(username="user")
		for i in range(10):
			contest = Contest.objects.create(
				word=f"CONTEST {i} (7 1)", started_by=user, status=Contest.CLOSED, winning_user=user
			)
			submission = contest.submissions.create(clue=f"Clue {i}", submitted_by=user)
			contest.winning_entry = submission
			contest.save()

		with self.assertNumQueries(1):
			res = self.client.get(reverse("cryptics:all_closed_contests"))

		self.assertEqual(res.status_code, HTTPStatus.OK)


class ContestSearchTestCase(TestCase):
	""" Test the contest_search_json endpoint """
	def setUp(self):
		self.user = User.objects.create(username="user")
		self.url = reverse("cryptics:contest_search")

		# A contest that doesn't shouldn't be returned for any search
		Contest.objects.create(word="EXTRANEOUS (10)", started_by=self.user)

	def test_contest_search_success(self):
		""" contest_search correctly returns a contest matching the search term (including partial matches) """
		contest = Contest.objects.create(word="CONTEST (7)", started_by=self.user)
		res = self.client.get(self.url, data={"search": "TEST"})
		self.assertEqual(res.status_code, HTTPStatus.OK, msg=res.content)
		res_data = res.json()
		self.assertEqual(len(res_data["contests"]), 1)
		self.assertEqual(res_data["contests"][0]["word"], contest.word)
		self.assertEqual(res_data["contests"][0]["url"], contest.get_absolute_url())

	def test_contest_search_with_multiple_matches(self):
		""" contest_search returns all contests matching the search term (in order of creation date) """
		contests = [
			Contest.objects.create(word="CONTEST (7)", started_by=self.user),
			Contest.objects.create(word="TEST (4)", started_by=self.user),
		]

		res = self.client.get(self.url, data={"search": "TES"})
		self.assertEqual(res.status_code, HTTPStatus.OK, msg=res.content)

		res_data = res.json()
		self.assertEqual(len(res_data["contests"]), 2)

		self.assertEqual(res_data["contests"][0]["word"], contests[0].word)
		self.assertEqual(res_data["contests"][0]["url"], contests[0].get_absolute_url())

		self.assertEqual(res_data["contests"][1]["word"], contests[1].word)
		self.assertEqual(res_data["contests"][1]["url"], contests[1].get_absolute_url())

	def test_contest_search_with_no_matches(self):
		""" contest_search returns an empty array if no contests match """
		res = self.client.get(self.url, data={"search": "NO MATCH"})
		self.assertEqual(res.status_code, HTTPStatus.OK, msg=res.content)
		res_data = res.json()
		self.assertEqual(res_data["contests"], [])

	def test_contest_search_is_case_insensitive(self):
		""" contest_search does a case-insensitive search """
		contest = Contest.objects.create(word="CONTEST (7)", started_by=self.user)
		res = self.client.get(self.url, data={"search": "test"})
		self.assertEqual(res.status_code, HTTPStatus.OK, msg=res.content)
		res_data = res.json()
		self.assertEqual(len(res_data["contests"]), 1)
		self.assertEqual(res_data["contests"][0]["word"], contest.word)
		self.assertEqual(res_data["contests"][0]["url"], contest.get_absolute_url())

	def test_contest_search_errors_with_blank_search(self):
		""" contest_search returns an error if the required search term is missing """
		res = self.client.get(self.url)
		self.assertEqual(res.status_code, HTTPStatus.BAD_REQUEST, msg=res.content)
		res_data = res.json()
		self.assertEqual(res_data["errors"], {"search": ["This field is required."]})

	def test_contest_search_errors_if_too_many_matching_contests_found(self):
		""" contest_search will return an error if too many contests match the search term

		This behavior is because currently the endpoint is only used to check for duplicate contests; if there are
		more than a handful of matches, just knowing that should be good enough.
		"""
		for i in range(10):
			Contest.objects.create(word=f"CONTEST {i} (7 1)", started_by=self.user)

		res = self.client.get(self.url, data={"search": "TEST"})
		self.assertEqual(res.status_code, HTTPStatus.BAD_REQUEST)
		res_data = res.json()
		self.assertEqual(res_data["errors"], {"search": ["Too many matching contests found (10)."]})

	def test_contest_search_handles_queries_efficiently(self):
		""" contest_search should gather all required information with a constant number of queries """
		for i in range(9):
			Contest.objects.create(word=f"CONTEST {i} (7 1)", started_by=self.user)

		# The two queries are to get the count of matching contests, then retrieve the actual information
		with self.assertNumQueries(2):
			res = self.client.get(self.url, data={"search": "TEST"})

		self.assertEqual(res.status_code, HTTPStatus.OK)
