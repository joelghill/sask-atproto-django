"""
Configures the gunicorn server for SolusGuard services.
"""
import os

loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')

bind = "0.0.0.0:3000"
if os.getenv("DJANGO_DEBUG", "TRUE").upper() == "TRUE":
    workers = 2
    reload = True
else:
    workers = 2

capture_output = True
timeout = 60