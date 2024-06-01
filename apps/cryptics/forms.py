from django import forms
from django.core.exceptions import ValidationError
from django.template.defaultfilters import pluralize

from .models import Contest, Submission


class ContestForm(forms.ModelForm):

    word = forms.CharField(widget=forms.TextInput(attrs={"id": "new_contest_word"}))

    class Meta:
        model = Contest
        fields = ["word", "started_by"]

    template_name = "cryptics/contest_form.html"
    # Note that this template to hard-coded to only display the "word" field—if I add additional fields to this form
    # in the future (unlikely, but one never knows), the template will need to be rewritten.  Also note that
    # started_by is a field on this form for validation/model creation purposes, but it isn't included on the form
    # itself; the view will need to manually add that (based on request.user) to the POST data before instantiating
    # the form.

    def clean_started_by(self):
        """ Make sure a user only has a single open contest at a time """
        started_by = self.cleaned_data["started_by"]
        if started_by.contests_started.filter(status=Contest.SUBMISSIONS).exists():
            raise ValidationError("Each user can only have one active contest at a time.", code="already_open_contest")
        return started_by

    def save(self, commit=True):
        obj = super().save(commit=False)  # This includes a check that there were no errors
        if commit:
            return Contest.objects.add(**self.cleaned_data)
        else:
            return obj


class SubmissionForm(forms.ModelForm):
    clue = forms.CharField(
        widget=forms.TextInput(attrs={"size": 60, "id": "new_submission"}),
        error_messages={"required": "Clue is required."}
    )
    explanation = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "cols": 40}), error_messages={"required": "Explanation is required."}
    )

    class Meta:
        model = Submission
        fields = ["clue", "explanation", "contest", "submitted_by"]

    template_name = "cryptics/submission_form.html"

    def clean_submitted_by(self):
        """ Make sure a user likes a certain number of other people's submissions for each clue they submit

        I do this to encourage more participation.  At the moment, it's very loose—you have to give at least one like
        for every two clues you submit.
        """
        submitter = self.cleaned_data["submitted_by"]
        likes_needed_to_give = submitter.submissions.count() // 2 - submitter.clues_liked.count()

        if likes_needed_to_give > 0:
            raise ValidationError(
                f"Please like at least {likes_needed_to_give} more clue{pluralize(likes_needed_to_give)}"
            )

        return submitter

    def clean_contest(self):
        contest = self.cleaned_data["contest"]
        contest.check_if_too_old()
        if not contest.is_submissions:
            raise ValidationError("Sorry, this contest has closed.")
        return contest

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            return Submission.objects.add(**self.cleaned_data)
        else:
            return obj


class ContestSearchForm(forms.Form):
    """ Form for the GET params of the contest search field

    This is overkill now, but can be extended if we want to accept more complicated search/filtering (such as
    different sort orders or pagination)
    """
    search = forms.CharField()
