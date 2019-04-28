from celery import task

@task(name="update_contest_status")
def update_contest_status(contest):
    """ Change a contest from open to voting or voting to closed """
    contest.check_if_too_old()
