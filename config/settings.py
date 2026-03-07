from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment configuration
env = environ.Env(
    DEBUG=(bool, False),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# Request parsing limits (admin bulk actions, large forms)
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int("DATA_UPLOAD_MAX_NUMBER_FIELDS", default=10000)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY no esta configurada.")

if not DEBUG and SECRET_KEY == "pon_una_clave_segura_solo_para_desarrollo":
    raise ImproperlyConfigured(
        "SECRET_KEY usa un valor de desarrollo. Define una clave real para produccion."
    )

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS no puede estar vacio con DEBUG=False.")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "axes",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    # Project apps
    "accounts",
    "structure",
    "schemas",
    "ingest",
    "validation",
    "kpis",
    "audit",
    "performance",
    "core",
    "projects",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "axes.middleware.AxesMiddleware",
    "accounts.middleware.PasswordChangeRequiredMiddleware",
    "ingest.middleware.AutoIngestCleanupMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.admin_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "es"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

FILE_UPLOAD_MAX_MEMORY_SIZE = env.int(
    "FILE_UPLOAD_MAX_MEMORY_SIZE",
    default=2_621_440,
)
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int(
    "DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=10_485_760,
)
MAX_INGEST_UPLOAD_BYTES = env.int("MAX_INGEST_UPLOAD_BYTES", default=10_485_760)
MAX_SUPPORT_IMAGE_BYTES = env.int("MAX_SUPPORT_IMAGE_BYTES", default=5_242_880)
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# Automatic ingest file cleanup policy
AUTO_INGEST_CLEANUP_ENABLED = env.bool("AUTO_INGEST_CLEANUP_ENABLED", default=True)
AUTO_INGEST_CLEANUP_INTERVAL_SECONDS = env.int("AUTO_INGEST_CLEANUP_INTERVAL_SECONDS", default=21600)
AUTO_INGEST_CLEANUP_LOCK_TIMEOUT_SECONDS = env.int("AUTO_INGEST_CLEANUP_LOCK_TIMEOUT_SECONDS", default=600)
AUTO_INGEST_INSTANCE_RETENTION_DAYS = env.int("AUTO_INGEST_INSTANCE_RETENTION_DAYS", default=90)
AUTO_INGEST_BATCH_RETENTION_DAYS = env.int("AUTO_INGEST_BATCH_RETENTION_DAYS", default=180)
AUTO_INGEST_ORPHAN_RETENTION_DAYS = env.int("AUTO_INGEST_ORPHAN_RETENTION_DAYS", default=7)
AUTO_INGEST_SKIP_ORPHANS = env.bool("AUTO_INGEST_SKIP_ORPHANS", default=False)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth redirects
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "landing"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = env.int("AXES_COOLOFF_TIME", default=1)
AXES_RESET_ON_SUCCESS = True

OTP_TOTP_ISSUER = env("OTP_TOTP_ISSUER", default="SICGAD")

# Production security switches (useful for PythonAnywhere HTTPS deployments)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = env("CSRF_COOKIE_SAMESITE", default="Lax")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", default="same-origin")
SECURE_CROSS_ORIGIN_OPENER_POLICY = env(
    "SECURE_CROSS_ORIGIN_OPENER_POLICY",
    default="same-origin",
)
X_FRAME_OPTIONS = env("X_FRAME_OPTIONS", default="DENY")
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS",
    default=3600 if not DEBUG else 0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=not DEBUG,
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)



