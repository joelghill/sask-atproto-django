"""
Configures the gunicorn server for SolusGuard services.
"""
import os
import multiprocessing

loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')

bind = "0.0.0.0:3000"
if os.getenv("DJANGO_DEBUG", "TRUE").upper() == "TRUE":
    workers = 2
    reload = True
else:
    workers = multiprocessing.cpu_count() * 2 - 1

capture_output = True
timeout = 60