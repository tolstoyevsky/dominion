import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR + '/templates/',
        ],
    },
]

CHANNEL_NAME = 'build-log-{image_id}'

CONTAINER_NAME = 'pieman-{image_id}'

EMAIL_HOST = os.environ.get('EMAIL_HOST')

EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'info@cusdeb.com')

EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'

POLLING_FREQUENCY = int(os.getenv('POLLING_FREQUENCY', '15'))  # in seconds

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', '127.0.0.1')

RABBITMQ_PORT = os.getenv('RABBITMQ_PORT', '5672')

REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')

REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

TIMEOUT = int(os.getenv('TIMEOUT', '3600'))  # in seconds (an hour by default)

BUILD_RESULT_PATH = os.environ['BUILD_RESULT_PATH']

#
# Celery
#

QUEUE_BEAT_NAME = 'beat'

QUEUE_BUILD_NAME = 'build'

QUEUE_EMAIL_NAME = 'email'

QUEUE_WATCH_NAME = 'watch'

CELERY_BEAT_SCHEDULE = {
    'kick-off-build-tasks': {
        'task': 'dominion.tasks.spawn',
        'schedule': 5,
        'options': {'queue': QUEUE_BEAT_NAME},
    },
}

CELERY_BROKER_URL = f'amqp://guest:guest@{RABBITMQ_HOST}:{RABBITMQ_PORT}//'
