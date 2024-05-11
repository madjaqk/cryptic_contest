# Cryptic Crossword Contests

This is a Django server for running [cryptic crossword] clue-writing contests, of the sort run on 
the [DIY COW forums], among other places.

In addition to standard Django, this project uses:
* [`django-allauth`] for social authentication.  As of now, it only uses Discord, but adding more 
    providers should just be a matter of updating the `settings.py` file and creating the relevant 
    DB entries.
* [`python-decouple`] to hide secret data from version control.  This requires that a `.env` file 
    exist in the project's root directory (sibling to this README); you can see an example with the 
    expected keys in [the `.env-example` file](.env-example).
* Celery tasks with a RabbitMQ backend to ensure that contests are automatically closed after 
    enough time has passed.  A very short Docker Compose file to run a RabbitMQ server locally 
    during development is provided.
* Simple webhooks to post updates to given Discord servers when contests are started or closed and 
    clues are submitted.

## To-Do

I've learned about Django in the years since I started this project, so there are some updates that 
would be nice.

* Replace the hand-written data validation in `cryptics/views.py` and `cryptics/models.py` with 
    Django forms, and possibly replace the view functions with class-based views that have 
    form-handling baked in.
* Replace the default `django.contrib.auth.models` User with a custom model.  (Note that per the 
    docs [changing the User model for an existing project][new User model] is quite messy, so 
    this might not be worth the effort, unfortunately.)
* Add significantly more unit testing, and possibly Travis/GitHub Actions/some other CI system.
* In production, this uses Python's `logging.handlers.RotatingFileHandler` for logging, but there 
    was an issue that the `celery` user by default didn't have permission to write to the file in 
    question, causing Celery to immediately fail silently.  I was able to use [`setfacl`] to fix 
    the issue in the short-term, but a better solution would be to create a dedicated `cryptic` 
    group on the server or to switch to `syslog`-based logging (or both).
* I feel like production site is kind of sluggish, so I'd like to do some profiling--there's a 
    decent chance that some of the SQL queries can be optimized without affecting functionality.

## Deployment

This is as much a reminder for me as anyone else.

1. Tag current version and push to GitHub (something like `git tag v1.0`, `git push --tags`)
2. `git pull` on the server
3. `systemctl --signal SIGHUP kill gunicorn` (and also `... celery` if the change affects the 
    Celery tasks, which at the moment would just be things that touch the 
    `Contest.check_if_too_old` method)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

[cryptic crossword]: https://en.wikipedia.org/wiki/Cryptic_crossword
[DIY COW forums]: http://www.ukpuzzle.com/phpBB3/viewforum.php?f=4&sid=9d9a94fd347c73cf2660829640df5935
[`django-allauth`]: https://django-allauth.readthedocs.io/en/latest/installation.html
[`python-decouple`]: https://github.com/henriquebastos/python-decouple
[new User model]: https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#changing-to-a-custom-user-model-mid-project
[`setfacl`]: https://askubuntu.com/a/809562
