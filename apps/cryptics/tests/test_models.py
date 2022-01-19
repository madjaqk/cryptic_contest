""" Test the models in the cryptics app """
from django.contrib.auth.models import User
from django.test import TestCase

from ..models import Contest, Submission

class UsersTestCase(TestCase):
    """ Test the custom functions on the User model and manager """
    def setUp(self):
        self.user1 = User.objects.create_user(username="first_user", password="password")
        self.user2 = User.objects.create_user(username="second_user", password="password")
        self.user3 = User.objects.create_user(username="third_user", password="password")

        contest = Contest.objects.create(
            word="EXAMPLE CONTEST (7, 7)", started_by=self.user1, status=Contest.CLOSED
        )
        sub1 = Submission.objects.create(
            clue="Clue 1 (7, 7)", contest=contest, submitted_by=self.user3
        )
        sub2 = Submission.objects.create(
            clue="Clue 2 (7, 7)", contest=contest, submitted_by=self.user3
        )
        sub3 = Submission.objects.create(
            clue="Clue 3 (7, 7)", contest=contest, submitted_by=self.user2
        )
        contest.winning_submission = sub3
        contest.winning_user = self.user3
        contest.save()

        sub1.likers.add(self.user1, self.user2)
        sub2.likers.add(self.user2)
        sub3.likers.add(self.user1)

    def test_sort_users_has_correct_stats(self):
        """ User.objects.sort_users shows the correct statistics for each user """
        expected_stats = {
            self.user1.username: {
                "contests_won": 0,
                "total_submissions": 0,
                "total_likes": 0,
                "average_likes": 0,
                "clues_liked": 2,
            },
            self.user2.username: {
                "contests_won": 0,
                "total_submissions": 1,
                "total_likes": 1,
                "average_likes": 1,
                "clues_liked": 2,
            },
            self.user3.username: {
                "contests_won": 1,
                "total_submissions": 2,
                "total_likes": 3,
                "average_likes": 1.5,
                "clues_liked": 0,
            },
        }

        for user_data in User.objects.sort_users():
            with self.subTest(user_data=user_data):
                expected = expected_stats[user_data["user"].username]
                for field in expected:
                    with self.subTest(field=field):
                        self.assertEqual(
                            user_data[field],
                            expected[field],
                            msg=f"{user_data['user'].username} {field}"
                        )

    def test_sort_users_sorts_in_correct_order(self):
        """ User.objects.sort_users returns the users in the correct order """
        expected_order = [self.user3, self.user2, self.user1]
        actual_order = [user["user"] for user in User.objects.sort_users()]
        self.assertEqual(actual_order, expected_order)
