import logging

from celery import task

from apps.cryptics.models import Contest

logger = logging.getLogger(__name__)

@task(name="update_contest_status")
def update_contest_status(contest_id):
    """ Change a contest from open to voting or voting to closed """
    logger.info("Inside update_contest_status task for ID %d", contest_id)
    try:
        contest = Contest.objects.get(id=contest_id)
    except Contest.DoesNotExist:
        pass
    else:
        contest.check_if_too_old()
