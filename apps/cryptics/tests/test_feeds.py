""" Test the contest RSS feed """
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Contest, Submission, SUBMISSIONS_LENGTH, VOTING_LENGTH


class ContestFeedTestCase(TestCase):
	""" Each contest phase is its own feed item, and only after that phase has started. """

	def setUp(self):
		self.user = User.objects.create_user(username="setter")
		self.solver = User.objects.create_user(username="solver")
		self.url = reverse("cryptics:feed")

	def _contest(self, word, *, status, created_at, winning_clue=None):
		contest = Contest.objects.create(word=word, started_by=self.user, status=status)
		contest.created_at = created_at
		contest.save()
		if winning_clue:
			entry = Submission.objects.create(
				clue=winning_clue,
				explanation="The explanation stays off the feed.",
				contest=contest,
				submitted_by=self.solver,
			)
			contest.winning_entry = entry
			contest.winning_user = self.solver
			contest.save()
		return contest

	def test_open_contest_only_announces_submissions(self):
		""" A contest still taking clues does not announce voting or a winner early. """
		self._contest("FRESH (5)", status=Contest.SUBMISSIONS, created_at=timezone.now())

		res = self.client.get(self.url)

		self.assertContains(res, "Contest Submissions Open: FRESH (5)")
		self.assertContains(res, "setter started a new contest: FRESH (5).")
		self.assertNotContains(res, "Contest Voting Period")
		self.assertNotContains(res, "Contest Winner Announcement")

	def test_voting_contest_announces_submissions_and_voting(self):
		""" Once voting starts, both earlier announcements are present and the winner is not. """
		created_at = timezone.now() - SUBMISSIONS_LENGTH - datetime.timedelta(hours=1)
		self._contest("VOTING (6)", status=Contest.VOTING, created_at=created_at)

		res = self.client.get(self.url)
		body = res.content.decode()

		self.assertContains(res, "Contest Submissions Open: VOTING (6)")
		self.assertContains(res, "Contest Voting Period: VOTING (6)")
		self.assertContains(res, "Voting is now open for VOTING (6).")
		self.assertNotContains(res, "Contest Winner Announcement")
		self.assertLess(
			body.index("Contest Voting Period: VOTING (6)"),
			body.index("Contest Submissions Open: VOTING (6)"),
		)

	def test_closed_contest_announces_the_winner(self):
		""" A finished contest publishes all three items, newest phase first. """
		created_at = timezone.now() - SUBMISSIONS_LENGTH - VOTING_LENGTH
		contest = self._contest(
			"CLOSED (6)",
			status=Contest.CLOSED,
			created_at=created_at,
			winning_clue="Winning clue (6)",
		)

		res = self.client.get(self.url)
		body = res.content.decode()

		self.assertEqual(res.status_code, 200)
		self.assertIn("application/rss+xml", res["Content-Type"])
		self.assertContains(res, "Contest Submissions Open: CLOSED (6)")
		self.assertContains(res, "Contest Voting Period: CLOSED (6)")
		self.assertContains(res, "Contest Winner Announcement: CLOSED (6)")
		self.assertContains(
			res,
			"The winning clue for CLOSED (6), submitted by solver, is: Winning clue (6)",
		)
		self.assertNotContains(res, "The explanation stays off the feed.")
		self.assertLess(
			body.index("Contest Winner Announcement: CLOSED (6)"),
			body.index("Contest Voting Period: CLOSED (6)"),
		)
		self.assertLess(
			body.index("Contest Voting Period: CLOSED (6)"),
			body.index("Contest Submissions Open: CLOSED (6)"),
		)
		self.assertContains(res, f"contest-{contest.id}-submissions")
		self.assertContains(res, f"contest-{contest.id}-voting")
		self.assertContains(res, f"contest-{contest.id}-winner")

	def test_closed_contest_without_entries_says_so(self):
		""" A contest that closes with no clues still gets a winner announcement. """
		created_at = timezone.now() - SUBMISSIONS_LENGTH - VOTING_LENGTH
		self._contest("EMPTY (5)", status=Contest.CLOSED, created_at=created_at)

		res = self.client.get(self.url)

		self.assertContains(res, "Contest Winner Announcement: EMPTY (5)")
		self.assertContains(res, "Voting is closed for EMPTY (5). No clues were submitted.")

	def test_pages_advertise_the_feed(self):
		""" Public pages point feed readers at the RSS URL. """
		res = self.client.get(reverse("cryptics:about"))
		feed_url = reverse("cryptics:feed")

		self.assertContains(
			res,
			(
				'<link rel="alternate" type="application/rss+xml" '
				'title="Puzzlers Club Cryptic Clue Contests" '
				f'href="{feed_url}">'
			),
		)
		self.assertContains(res, f'<a href="{feed_url}">RSS</a>')
