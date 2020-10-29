import os


DEBUG = False

# Do not run anything if SECRET_KEY is not set.
SECRET_KEY = os.environ['SECRET_KEY']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('PG_DATABASE', 'cusdeb'),
        'USER': os.environ.get('PG_USER', 'postgres'),
        'PASSWORD': os.environ.get('PG_PASSWORD', 'secret'),
        'HOST': os.environ.get('PG_HOST', 'localhost'),
        'PORT': os.environ.get('PG_PORT', '5432'),
    }
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',

    'images',
]

EMAIL_HOST = os.environ.get('EMAIL_HOST')

EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')

EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

EMAIL_USE_SSL = bool(os.environ.get('EMAIL_USE_SSL', True))

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', '127.0.0.1')

RABBITMQ_PORT = os.getenv('RABBITMQ_PORT', '5672')

REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')

REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

QUEUE_BEAT_NAME = 'beat'

QUEUE_BUILD_NAME = 'build'

CELERY_BEAT_SCHEDULE = {
    'kick-off-build': {
        'task': 'dominion.tasks.spawn_builds',
        'schedule': 5,
        'options': {'queue': QUEUE_BEAT_NAME},
    },
}

CELERY_BROKER_URL = f'amqp://guest:guest@{RABBITMQ_HOST}:{RABBITMQ_PORT}//'
