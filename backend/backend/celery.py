import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Configuration
app.conf.beat_schedule = {
    'dynamically_update_links_every_15minutes': {
        'task': 'analytics.tasks.update_links',
        'schedule': 18000.0,  # Every five hours
        'options': {'queue': 'update_links'},
    },
}
