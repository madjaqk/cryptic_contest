from django.urls import path
from . import views

app_name = "cryptics"

urlpatterns = [
	path("", views.index, name="index"),
	path("about", views.about, name="about"),
	path("create_contest", views.create_contest, name="create_contest"),
	path("contest/<int:contest_id>", views.show_contest, name="show_contest"),
	path("contest/<int:contest_id>-<word>", views.show_contest_full, name="show_contest_full"),
	path("create_submission", views.create_submission, name="create_submission"),
	path("submission/<int:submission_id>/like", views.add_like, name="add_like"),
	path("submission/<int:submission_id>/dislike", views.remove_like, name="remove_like"),
	path("all_users", views.all_users, name="all_users"),
	path("user/<int:user_id>", views.show_user, name="show_user"),
	path(
		"submission/<int:submission_id>/delete",
		views.delete_submission,
		name="delete_submission"
	),
	path("archives", views.all_closed_contests, name="all_closed_contests"),
]
