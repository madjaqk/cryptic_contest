# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project 
adheres roughly to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-05-31

* FEAT: Use built-in Django forms rather than rolling my own
* FEAT: Add "Check for repeats" link to contest create form
* FEAT: Added new `contest_search_json` view, which returns a JSON of matching contests.  (Currently, this is only used for the "Check for repeats" link.)
* FIX: Use `select_related`, `prefetch_related`, and generally smarter queries to greatly speed up many views, most notably the full archive view
* FIX: The auto-enumeration option for new contests will now include non-ASCII letters and ASCII digits in the enumeration.  (That is, `ÉPÉE` and `R2D2` will now both auto-enumerate to `(4)` instead of `(2)`.)

## [1.1.0] - 2022-01-24

* FIX: Use a more efficient query to generate stats, greatly reducing load time
* FIX: Round average number of likes on user stats page
* FIX: In Discord messages, don't wrap the clue in a `code block`.  (Some users like to put more risqué clues inside of spoiler tags, which the code block would suppress.)

## [1.0.0] - 2021-03-06

* FIX: Moved Celery task creation to `ContestManager.add` method
* DOC: Added README, LICENSE, and CHANGELOG (this also became version 1.0.0 by default, replacing 
	the previous version number system, a shrugging emoji)
* TST: Started writing tests for cryptic contest views
* STY: Pylint-inspired fixes, including line length and standardizing tabs versus spaces and single 
	versus double quotes
