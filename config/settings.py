import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-key-ganti-sebelum-produksi")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
DEV_BROWSER_AUTO_RELOAD = DEBUG and os.getenv("DJANGO_BROWSER_AUTO_RELOAD", "True").lower() == "true"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_NAME = os.getenv("APP_NAME", "SIKAP-PU")
APP_FULL_NAME = os.getenv(
    "APP_FULL_NAME",
    "SISTEM INFORMASI KENDALI ADMINISTRASI PERKARA TINDAK PIDANA UMUM PADA TAHAP PRA PENUNTUTAN BERBASIS WEB DENGAN AUTOMATIC REMINDER WHATSAPP DAN TELEGRAM",
)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "accounts", "django.contrib.staticfiles", "dashboard", "configurations", "cases", "notifications"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "config.context_processors.app_version", "notifications.context_processors.web_notifications"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {"ENGINE": "config.db.backends.mysql_legacy", "NAME": os.getenv("DB_NAME", "sikap_pu_db"), "USER": os.getenv("DB_USER", "root"), "PASSWORD": os.getenv("DB_PASSWORD", ""), "HOST": os.getenv("DB_HOST", "127.0.0.1"), "PORT": os.getenv("DB_PORT", "3306"), "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"}}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Makassar"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_MAX_REQUEST_SIZE", 8 * 1024 * 1024))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.UsernameOrEmailBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "accounts:login"
WA_GATEWAY_URL = os.getenv("WA_GATEWAY_URL", "http://127.0.0.1:3001").rstrip("/")
WA_GATEWAY_API_KEY = os.getenv("WA_GATEWAY_API_KEY", "")
WA_GATEWAY_SESSION = os.getenv("WA_GATEWAY_SESSION", "sikap-pu-main")
SIPEDE_SOP_FORM_02_ID = os.getenv("SIPEDE_SOP_FORM_02_ID", "8")
SIPEDE_SURATKELUAR_ID = os.getenv("SIPEDE_SURATKELUAR_ID", "125")
SIPEDE_SURATKELUAR_JENIS = os.getenv("SIPEDE_SURATKELUAR_JENIS", "100")
SIPEDE_SOP_FORM_03_ID = os.getenv("SIPEDE_SOP_FORM_03_ID", SIPEDE_SURATKELUAR_ID)
SIPEDE_P18_ID = os.getenv("SIPEDE_P18_ID", "8")
SIPEDE_P19_ID = os.getenv("SIPEDE_P19_ID", SIPEDE_SURATKELUAR_ID)
SIPEDE_P20_ID = os.getenv("SIPEDE_P20_ID", SIPEDE_SURATKELUAR_ID)
SIPEDE_P21_ID = os.getenv("SIPEDE_P21_ID", "9")
SIPEDE_SOP_FORM_07_ID = os.getenv("SIPEDE_SOP_FORM_07_ID", SIPEDE_SURATKELUAR_ID)
