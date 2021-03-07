# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project 
adheres roughly to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2021-03-06

* FIX: Moved Celery task creation to `ContestManager.add` method
* DOC: Added README, LICENSE, and CHANGELOG (this also became version 1.0.0 by default, replacing 
	the previous version number system, a shrugging emoji)
* TST: Started writing tests for cryptic contest views
* STY: Pylint-inspired fixes, including line length and standardizing tabs versus spaces single 
	versus double quotes
