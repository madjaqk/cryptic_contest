from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ContestForm, ContestSearchForm, SubmissionForm
from .models import User, Contest, Submission


def index(request):
	""" Show the main page """
	if request.method == "POST":
		if request.user.is_anonymous:
			return redirect("account_login")

		form = ContestForm({"word": request.POST.get("word"), "started_by": request.user})

		if form.is_valid():
			form.save()
			return redirect("cryptics:index")
	else:
		form = ContestForm()

	context = {"form": form}

	context["open_contests"] = Contest.objects.filter(status=Contest.SUBMISSIONS).order_by("created_at")

	context["voting_contests"] = Contest.objects.filter(status=Contest.VOTING).order_by("created_at")

	context["past_contests"] = Contest.objects.ended_recently()
	context["current_champ"] = User.objects.sort_users()[0]
	context["recent_clues"] = Submission.objects.all().order_by("-created_at")[:3]

	return render(request, "cryptics/index.html", context)


def about(request):
	""" Show the about page """
	return render(request, "cryptics/about.html")


def show_contest(request, contest_id):
	""" Redirect show_contest requests with just the ID to ID and contest slug URL """
	contest = get_object_or_404(Contest, id=contest_id)
	return redirect("cryptics:show_contest_full", contest.id, contest.slugified)


def show_contest_full(request, contest_id, word=None):
	""" Show information about a specific contest """
	contest = get_object_or_404(
		Contest.objects.select_related("started_by", "winning_entry", "winning_entry__submitted_by"), id=contest_id
	)

	if word != contest.slugified:
		return redirect("cryptics:show_contest_full", contest.id, contest.slugified)

	contest.check_if_too_old()

	if request.method == "POST":
		if request.user.is_anonymous:
			# This is ugly but apparently the only way to get query params into the redirect
			redirect_url = reverse("account_login") + "?next=" + request.path
			return redirect(redirect_url)

		form = SubmissionForm(
			{
				"submitted_by": request.user,
				"contest": contest_id,
				"clue": request.POST.get("clue"),
				"explanation": request.POST.get("explanation"),
			}
		)

		if form.is_valid():
			form.save()
			return redirect("cryptics:show_contest", contest_id)

	else:
		form = SubmissionForm()

	context = {
		"contest": contest,
		"form": form,
		"highlight": int(request.GET.get("highlight", -1)),
	}

	return render(request, "cryptics/show.html", context)


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
	contests = Contest.objects.filter(status=Contest.CLOSED).order_by("created_at")
	contests = contests.select_related("started_by", "winning_entry", "winning_user")
	context = {"contests": contests}
	return render(request, "cryptics/all_closed_contests.html", context)


def contest_search_json(request):
	""" Return a list of contests matching a given string

	Currently this endpoint is only used for the "check for repeats" functionality, but could be adapted if the full
	archives page is switched to be paginated with AJAX
	"""
	search_data = ContestSearchForm(request.GET)
	if not search_data.is_valid():
		return JsonResponse({"errors": search_data.errors}, status=HTTPStatus.BAD_REQUEST)

	contests = Contest.objects.filter(word__icontains=search_data.cleaned_data["search"]).order_by("created_at")
	if (err_count := contests.count()) >= 10:
		return JsonResponse(
			{"errors": {"search": [f"Too many matching contests found ({err_count})."]}},
			status=HTTPStatus.BAD_REQUEST
		)

	contests = [{"word": contest.word, "url": contest.get_absolute_url()} for contest in contests]
	return JsonResponse({"contests": contests})
