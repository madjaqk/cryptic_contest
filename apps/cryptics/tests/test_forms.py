""" Test cryptic-related forms """
from unittest import mock

from django.test import TestCase
from parameterized import parameterized

from apps.cryptics.forms import ContestForm, SubmissionForm
from apps.cryptics.models import Contest, Submission, User


class TestContestForm(TestCase):
    """ Test custom validations on the ContestForm class """
    def setUp(self):
        self.user = User.objects.create_user("user")

    def test_contest_form_errors_if_user_has_another_open_contest(self):
        """ Show validation error if a user attempts to start a new contest while one they started is already open """
        Contest.objects.create(word="EXISTING (8)", started_by=self.user, status=Contest.SUBMISSIONS)

        data = {"word": "NEW (3)", "started_by": self.user.id}
        form = ContestForm(data)

        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["started_by"]), 1)
        expected_msg = "Each user can only have one active contest at a time"
        self.assertIn(expected_msg, form.errors["started_by"][0])

    def test_contest_form_errors_if_word_is_too_long(self):
        """ Show validation error if the word is too long

        This is handled by Django built-ins, so to some extent it's testing that the library does what it says it
        does, but shrug emoji.
        """
        data = {"word": "A" * 200, "started_by": self.user.id}
        form = ContestForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["word"]), 1)
        expected_msg = f"Ensure this value has at most 150 characters (it has {len(data['word'])})"
        self.assertIn(expected_msg, form.errors["word"][0])


class TestSubmissionForm(TestContestForm):
    """ Test custom validations on the SubmissionForm class """

    def setUp(self):
        self.user = User.objects.create_user("user")
        self.contest = Contest.objects.create(word="EXAMPLE (7)", started_by=self.user)
        self.form_data = {
            "clue": "Letter with abundant illustration (7)",
            "explanation": "letter=EX, abundant=AMPLE",
            "contest": self.contest.id,
            "submitted_by": self.user,
        }

    def test_submission_form_errors_if_user_needs_to_like_more_clues(self):
        """ Show validation error if a user needs to like more clues before submitting """
        other_contest = Contest.objects.create(word="FAKE (4)", started_by=self.user)
        for i in range(5):
            Submission.objects.create(
                clue=f"Fake clue {i}",
                explanation=f"Fake explanation {i}",
                contest=other_contest,
                submitted_by=self.user
            )

        form = SubmissionForm(self.form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["submitted_by"]), 1)
        # Our user has 5 submissions and has given 0 likes.  The rule is at least one like for
        # every two submissions, rounded down, so they would need to like two more submissions
        # before submitting again.
        self.assertIn("Please like at least 2 more clues", form.errors["submitted_by"][0])

    @parameterized.expand([(Contest.VOTING,), (Contest.CLOSED,)])
    def test_submission_form_errors_if_contest_has_closed(self, status):
        """ Show validation error if the contest is no longer open for submissions """
        self.contest.status = status
        self.contest.save()

        form = SubmissionForm(self.form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["contest"]), 1)
        self.assertIn("Sorry, this contest has closed", form.errors["contest"][0])

    @mock.patch("apps.cryptics.forms.Submission.objects.add")
    def test_submission_form_calls_custom_submission_add_method(self, mock_add: mock.MagicMock):
        """ The SubmissionForm uses the custom Submission.objects.add manager method """
        form = SubmissionForm(self.form_data)
        self.assertTrue(form.is_valid())
        form.save()
        mock_add.assert_called_once()
