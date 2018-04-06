from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, FloatField

from .models import User, Contest, Submission

def index(request):
	context = {}
	context["open_contests"] = Contest.objects.filter(active=True)
	context["past_contests"] = Contest.objects.filter(active=False)
	context["current_champ"] = User.objects.sort_users()[0]

	return render(request, "cryptics/index.html", context)

@login_required
def create_contest(request):
	if request.method == "POST" and request.POST["word"]:
		if Contest.objects.filter(active=True, started_by=request.user):
			messages.error(request, "Each user can only have one active contest at a time.")
		else:
			Contest.objects.add(word=request.POST["word"], started_by=request.user)
	return redirect("cryptics:index")

def show_contest(request, contest_id):
	contest = get_object_or_404(Contest, id=contest_id)
	contest.check_if_too_old()
	return render(request, "cryptics/show.html", {"contest": contest})	

@login_required
def create_submission(request):
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
def add_like(request, submission_id):
	submission = get_object_or_404(Submission, id=submission_id)
	submission.contest.check_if_too_old()
	if submission.contest.active:
		submission.likers.add(request.user)
	else:
		messages.error(request, "Sorry, this contest has closed")
	return redirect("cryptics:show_contest", submission.contest.id)

@login_required
def remove_like(request, submission_id):
	submission = get_object_or_404(Submission, id=submission_id)
	submission.contest.check_if_too_old()
	if submission.contest.active:
		submission.likers.remove(request.user)
	else:
		messages.error(request, "Sorry, this contest has closed")	
	return redirect("cryptics:show_contest", submission.contest.id)

def all_users(request):
	return render(request, "cryptics/all_users.html", {"users": User.objects.sort_users()})

def show_user(request, user_id):
	user = get_object_or_404(User, id=user_id)
	return render(request, "cryptics/user_show.html", {"this_user": user})