import os


DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('PG_DATABASE'),
        'USER': os.environ.get('PG_USER'),
        'PASSWORD': os.environ.get('PG_PASSWORD'),
        'HOST': os.environ.get('PG_HOST', 'localhost'),
        'PORT': os.environ.get('PG_PORT', ''),
    }
}

EMAIL_HOST = os.environ.get('EMAIL_HOST')

EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')

EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

EMAIL_USE_SSL = bool(os.environ.get('EMAIL_USE_SSL', True))

# Do not run anything if SECRET_KEY is not set.
SECRET_KEY = os.environ['SECRET_KEY']
