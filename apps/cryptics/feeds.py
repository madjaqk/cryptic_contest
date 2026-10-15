""" RSS feed of contest phase changes.

Each contest can produce up to three items: submissions opening, voting opening, and the winner
announcement. Those are status changes on one row, so the feed synthesizes an item per phase.
"""
import datetime
from dataclasses import dataclass

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils import timezone

from .models import Contest

# A phase change updates the contest, so recently changed contests stay in this window.
CONTESTS_SCANNED = 40
EVENTS_PUBLISHED = 30


@dataclass(frozen=True)
class ContestEvent:
	""" One feed entry for a contest phase. """
	SUBMISSIONS = "submissions"
	VOTING = "voting"
	WINNER = "winner"

	contest: Contest
	kind: str
	published: datetime.datetime


def contest_events(contest: Contest, now: datetime.datetime) -> list[ContestEvent]:
	""" Return the phase announcements that have already happened for this contest. """
	events = [
		ContestEvent(contest, ContestEvent.SUBMISSIONS, contest.created_at),
	]
	if contest.status in (Contest.VOTING, Contest.CLOSED):
		events.append(ContestEvent(contest, ContestEvent.VOTING, contest.submissions_end_time))
	if contest.status == Contest.CLOSED:
		events.append(ContestEvent(contest, ContestEvent.WINNER, contest.voting_end_time))

	return [event for event in events if event.published <= now]


class ContestFeed(Feed):
	""" Submissions, voting, and winner announcements. """
	title = "Puzzlers Club Cryptic Clue Contests"
	description = "Contest submissions, voting periods, and winner announcements."
	item_guid_is_permalink = False

	def link(self):
		""" The site home page, which this feed describes. """
		return reverse("cryptics:index")

	def items(self):
		""" The most recent phase announcements across recent contests. """
		contests = Contest.objects.select_related(
			"started_by",
			"winning_entry",
			"winning_entry__submitted_by",
		).order_by("-updated_at")[:CONTESTS_SCANNED]

		now = timezone.now()
		events = []
		for contest in contests:
			events.extend(contest_events(contest, now))

		events.sort(key=lambda event: event.published, reverse=True)
		return events[:EVENTS_PUBLISHED]

	def item_title(self, item: ContestEvent) -> str:
		""" Phase name plus the contest word, so items are distinct in a reader. """
		labels = {
			ContestEvent.SUBMISSIONS: "Contest Submissions Open",
			ContestEvent.VOTING: "Contest Voting Period",
			ContestEvent.WINNER: "Contest Winner Announcement",
		}
		return f"{labels[item.kind]}: {item.contest.word}"

	def item_description(self, item: ContestEvent) -> str:
		""" Short announcement text. Clue explanations stay off the feed. """
		contest = item.contest
		if item.kind == ContestEvent.SUBMISSIONS:
			return f"{contest.started_by} started a new contest: {contest.word}."
		if item.kind == ContestEvent.VOTING:
			return f"Voting is now open for {contest.word}."
		if contest.winning_entry_id:
			entry = contest.winning_entry
			return (
				f"The winning clue for {contest.word}, submitted by {entry.submitted_by}, "
				f"is: {entry.clue}"
			)
		return f"Voting is closed for {contest.word}. No clues were submitted."

	def item_link(self, item: ContestEvent) -> str:
		""" Every phase links to that contest's page. """
		return item.contest.get_absolute_url()

	def item_pubdate(self, item: ContestEvent) -> datetime.datetime:
		""" When the phase started, not when a background task happened to notice. """
		return item.published

	def item_guid(self, item: ContestEvent) -> str:
		""" Stable id per phase, since all three phases share one contest URL. """
		return f"contest-{item.contest.id}-{item.kind}"
