"""
Configuración de KeyByMe.
Lee valores sensibles desde variables de entorno (.env) usando django-environ.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
# Lee el archivo .env en la raíz del proyecto (si existe)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Detrás de un load balancer o reverse proxy (nginx, DigitalOcean App Platform),
# las requests le llegan a Django por HTTP con este header indicando que en
# realidad son HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
# Por default, seguras solo si no es DEBUG — pero si el servidor todavía no
# tiene HTTPS real (ej. sin dominio/certificado), hay que forzar esto a False
# en el .env, o el navegador nunca mandará estas cookies y el login fallará.
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)

# Llave de cifrado para los passwords guardados en el vault (VaultPassword).
# Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
VAULT_ENCRYPTION_KEY = env("VAULT_ENCRYPTION_KEY", default=None)

# Correo saliente (usado por `manage.py send_due_reminders` para avisar de
# los recordatorios). Cuenta única del sistema, no la del usuario: así se
# evitan los problemas de entrega de spoofear el remitente por usuario.
# En DEBUG, si no se configura EMAIL_BACKEND explícitamente, los correos se
# imprimen en consola en vez de enviarse de verdad (no requiere SMTP en dev).
_default_email_backend = (
    "django.core.mail.backends.console.EmailBackend" if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_BACKEND = env("EMAIL_BACKEND", default=_default_email_backend)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="KeyByMe <no-reply@keybyme.com>")

# Token compartido para que un cron externo (ej. GitHub Actions) pueda disparar
# `send_due_reminders` vía POST a /vault/cron/send-reminders/ (header X-Cron-Token).
# Generar con: python -c "import secrets; print(secrets.token_urlsafe(32))"
CRON_SECRET = env("CRON_SECRET", default="")

# Path to the tesseract binary, for RouteSheetUpload OCR (see vault/ocr.py).
# Empty by default: on the EC2 box `apt install tesseract-ocr` puts it on
# PATH, so pytesseract finds it with no config. On Windows it's usually NOT
# on PATH after installing (e.g. via winget) — set this to the full path,
# typically `C:\Program Files\Tesseract-OCR\tesseract.exe`.
TESSERACT_CMD = env("TESSERACT_CMD", default="")

# Free-tier API key for LocationIQ (geocoding — see vault/routing.py), used
# by Rutas' "Directions" and MCPS "Lefts & Rights". Get one at
# https://locationiq.com/ (no credit card). Replaced OpenStreetMap's own
# public Nominatim on 2026-08-09 after Nominatim started blanket-429ing
# every request from prod's EC2 IP.
LOCATIONIQ_API_KEY = env("LOCATIONIQ_API_KEY", default="")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # requerido por django-allauth

    # Login: email/password propio + "Sign in with Google" (ver accounts/adapters.py).
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Apps propias de KeyByMe
    'accounts',
    'menus',
    'vault',
    'finanzas',
    'schools',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "config" / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database — PostgreSQL, configurable vía DATABASE_URL en el .env.
# El default sqlite es solo un placeholder para que `collectstatic` (que
# corre en el build, sin acceso real a la BD) no truene si DATABASE_URL
# todavía no está disponible en esa fase. En runtime siempre debe existir
# la real, o cualquier request que toque la BD fallará.
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///build-placeholder.db'),
}


# Modelo de usuario personalizado
AUTH_USER_MODEL = "accounts.CustomUser"


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# US number format (9,999,999.99) — Django's en-us default.
USE_THOUSAND_SEPARATOR = True


# Static & media files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# En App Platform el disco del contenedor es efímero: los archivos subidos a
# MediaFile deben ir a DigitalOcean Spaces (S3-compatible) en vez del disco
# local. USE_SPACES=True activa ese storage; en desarrollo local se queda en disco.
USE_SPACES = env.bool("USE_SPACES", default=False)

if USE_SPACES:
    AWS_ACCESS_KEY_ID = env("SPACES_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("SPACES_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("SPACES_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = env("SPACES_ENDPOINT_URL")  # ej: https://nyc3.digitaloceanspaces.com
    AWS_S3_REGION_NAME = env("SPACES_REGION", default="nyc3")
    AWS_DEFAULT_ACL = "private"
    AWS_QUERYSTRING_AUTH = True  # URLs firmadas y temporales para los archivos del vault
    AWS_S3_FILE_OVERWRITE = False
    AWS_LOCATION = "media"

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# Tamaño máximo por archivo subido (en bytes). Ajustable según necesidad.
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB en memoria antes de usar disco temporal
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "vault:contact_list"  # sin uso real: KeyByMeAccountAdapter.get_login_redirect_url manda al primer módulo del usuario
LOGOUT_REDIRECT_URL = "index"


# ---------------------------------------------------------------------------
# django-allauth: signup con email propio o con Google, aprobación manual.
# Toda cuenta nueva (por email o por Google) queda con is_active=False hasta
# que el admin la aprueba desde /admin — ver accounts/adapters.py.
# ---------------------------------------------------------------------------
ACCOUNT_ADAPTER = "accounts.adapters.KeyByMeAccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapters.KeyByMeSocialAccountAdapter"
ACCOUNT_FORMS = {"signup": "accounts.forms.SignupForm"}

ACCOUNT_LOGIN_METHODS = {"email"}
# Sin "username*": el username se sigue generando solo (adapter.populate_username),
# el usuario nunca lo ve ni lo elige.
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
# Los links de los correos (verificación, reset de password) usan este esquema.
# Cloudflare ya sirve keybyme.com por HTTPS al visitante aunque el origin (EC2)
# hable HTTP plano (ver CLAUDE.md) — por eso el default es "https" incluso ahí.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = env("ACCOUNT_DEFAULT_HTTP_PROTOCOL", default="https")
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False  # sigue is_active=False hasta que el admin apruebe

# Google ya verificó el email por su cuenta: no hace falta otra verificación,
# y auto-signup evita un paso extra de "confirmá tus datos" para el usuario.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
    },
}