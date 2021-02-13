from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from .models import User, Contest, Submission

def index(request):
	""" Show the main page """
	context = {}

	context["open_contests"] = Contest.objects.filter(
		status=Contest.SUBMISSIONS
	).order_by("created_at")

	context["voting_contests"] = Contest.objects.filter(
		status=Contest.VOTING
	).order_by("created_at")

	context["past_contests"] = Contest.objects.ended_recently()
	context["current_champ"] = User.objects.sort_users()[0]
	context["recent_clues"] = Submission.objects.all().order_by("-created_at")[:3]

	return render(request, "cryptics/index.html", context)

@login_required
def create_contest(request):
	""" Let a user create a new contest """
	if request.method == "POST" and request.POST["word"]:
		max_length = Contest._meta.get_field("word").max_length
		if Contest.objects.filter(status=Contest.SUBMISSIONS, started_by=request.user):
			messages.error(request, "Each user can only have one active contest at a time.")
		elif len(request.POST["word"]) > max_length:
			messages.error(
				request,
				f"Maximum contest length is {max_length} characters; {request.POST['word']} is "
				f"{len(request.POST['word'])} characters long"
			)
		else:
			Contest.objects.add(word=request.POST["word"], started_by=request.user)

	return redirect("cryptics:index")

def show_contest(request, contest_id):
	""" Redirect show_contest requests with just the ID to ID and contest slug URL """
	contest = get_object_or_404(Contest, id=contest_id)
	return redirect("cryptics:show_contest_full", contest.id, contest.slugified)

def show_contest_full(request, contest_id, word=None):
	""" Show information about a specific contest """
	contest = get_object_or_404(Contest, id=contest_id)

	if word != contest.slugified:
		return redirect("cryptics:show_contest_full", contest.id, contest.slugified)

	contest.check_if_too_old()

	context = {
		"contest": contest,
		"sort_order": "sort_order" if contest.is_closed else "id",
		"highlight": int(request.GET.get("highlight", -1)),
		}

	return render(request, "cryptics/show.html", context)

@login_required
def create_submission(request):
	""" Let a user submit a clue to a given contest """
	if request.method != "POST":
		return redirect("cryptics:index")

	results = Submission.objects.add(request.POST, request.user)

	if not results["status"]:
		for error in results["errors"]:
			messages.error(request, error)
	else:
		messages.success(request, "Clue submitted!")

	return redirect("cryptics:show_contest", request.POST["contest_id"])

@login_required
def delete_submission(request, submission_id):
	""" Let a user delete a clue that they submitted """
	submission = get_object_or_404(Submission, id=submission_id)
	submission.contest.check_if_too_old()

	valid = True

	if request.user != submission.submitted_by:
		messages.error(request, "You can only delete clues that you submitted")
		valid = False
	elif not submission.contest.is_submissions:
		messages.error(request, "Sorry, you can't delete a clue once voting has begun")
		valid = False

	if valid and request.method == "GET":
		if "next" in request.GET:
			next_url = request.GET["next"]
		else:
			next_url = reverse(
				"cryptics:show_contest", kwargs={"contest_id": submission.contest_id}
			)
		context = {
			"sub": submission,
			"next_url": next_url
		}
		return render(request, "cryptics/delete_clue.html", context)

	if valid and request.method == "POST":
		submission.delete()

	if "next" in request.GET:
		return redirect(request.GET["next"])

	return redirect("cryptics:show_contest", submission.contest.id)

@login_required
def add_like(request, submission_id):
	""" Let a user like a given clue """
	submission = get_object_or_404(Submission, id=submission_id)
	submission.contest.check_if_too_old()
	if not submission.contest.is_voting:
		if submission.contest.is_submissions:
			messages.error(request, "Sorry, this contest is not taking votes yet")
		else:
			messages.error(request, "Sorry, this contest has closed")
	elif request.user == submission.submitted_by:
		messages.error(request, "Sorry, you can't vote for your own submissions")
	else:
		submission.likers.add(request.user)

	if "next" in request.GET:
		return redirect(request.GET["next"])

	return redirect("cryptics:show_contest", submission.contest.id)

@login_required
def remove_like(request, submission_id):
	""" Let a user unlike a given clue """
	submission = get_object_or_404(Submission, id=submission_id)
	submission.contest.check_if_too_old()
	if submission.contest.is_voting:
		submission.likers.remove(request.user)
	else:
		if submission.contest.is_submissions:
			messages.error(request, "Sorry, this contest is not taking votes yet")
		else:
			messages.error(request, "Sorry, this contest has closed")

	if "next" in request.GET:
		return redirect(request.GET["next"])

	return redirect("cryptics:show_contest", submission.contest.id)

def all_users(request):
	""" Show the list of all users """
	return render(request, "cryptics/all_users.html", {"users": User.objects.sort_users()})

def show_user(request, user_id):
	""" Show a specific user's page """
	user = get_object_or_404(User, id=user_id)

	context = {
		"this_user": user,
		"highlight": int(request.GET.get("highlight", -1)),
		}

	return render(request, "cryptics/user_show.html", context)

def all_closed_contests(request):
	""" Show the complete list of all finished contests

	In the future, this might need to be paginated
	"""
	context = {"contests": Contest.objects.filter(status=Contest.CLOSED).order_by("created_at")}
	return render(request, "cryptics/all_closed_contests.html", context)
