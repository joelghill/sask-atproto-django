# SASK-ATPROTO-DJANGO Project Structure

## Overview
This document outlines the directory structure and key components of the SASK-ATPROTO-DJANGO project.

## Root Directory
- `Dockerfile` - Defines the Docker container for the application
- `LICENSE` - Project license file
- `Pipfile` & `Pipfile.lock` - Python package management files
- `README.md` - Project documentation
- `example.env` - Template for environment variables
- `gunicorn.conf.py` - Configuration for the Gunicorn WSGI server
- `manage.py` - Django's command-line utility for administrative tasks
- `publish_feed.py` - Script to publish the custom feed to the Bluesky network
- `pyproject.toml` - Configuration file for Python tools
- `pytest.ini` - Configuration for pytest testing framework
- `requirements.txt` - Lists Python package dependencies

## Bin Directory
- `docker_entrypoint` - Entry point script for Docker container

## Firehose App
Handles connection to the Bluesky firehose (real-time data stream)
```
firehose/
├── __init__.py
├── admin.py           # Registers models related to the Bluesky firehose data
├── apps.py           # Set up configurations for connecting to the Bluesky firehose
├── management/
│   └── commands/
│       └── start_feed.py  # Command to start the feed ingestion process
├── migrations/       # Database schema management
├── models.py        # Data models for storing firehose data
├── settings.py
├── subscription.py  # Manages subscription to the firehose
├── tests.py
└── views.py
```

## Flatlanders App
Core app for the custom feed algorithm
```
flatlanders/
├── __init__.py
├── admin.py         # Registers models for the custom feed algorithm
├── algorithms/
│   ├── errors.py
│   └── flatlanders_feed.py  # Custom feed algorithm implementation
├── apps.py         # Initialize components of the custom feed algorithm
├── keywords.py     # Defines Saskatchewan-related keywords for content filtering
├── labelers.py     # Implements content labeling functionality
├── management/
│   └── commands/
│       └── start_labeler.py  # Command to start content labeling
├── migrations/
├── models/
│   ├── labelers.py
│   ├── posts.py
│   └── users.py    # Data models for users, posts, and labelers
├── settings.py
├── tests.py
└── views.py        # Manage presentation and interaction with the feed algorithm
```

## Main Django Project
```
sk_atp_feed/
├── __init__.py
├── asgi.py         # Entry point for ASGI server
├── settings.py     # Django project settings
├── urls.py         # URL routing configuration
└── wsgi.py         # Entry point for WSGI server
```

## Frontend Assets
### Static Files
```
static/
├── css/
│   ├── bootstrap.min.css
│   └── bootstrap.min.css.map
└── js/
    ├── bootstrap.min.js
    └── bootstrap.min.js.map
```

### Templates
```
templates/
├── base.html
├── home.html
├── protected.html
└── registration/
    └── login.html
```

## Tests
```
tests/
├── __init__.py
└── flatlanders/
    ├── algorithms/
    │   └── test_indexer.py
    ├── models/
    │   └── test_post_model.py
    └── test_views.py
```
