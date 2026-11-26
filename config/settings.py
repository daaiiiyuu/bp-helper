"""
居家血壓量測衛教與紀錄系統 — Django 設定檔

開發時直接 `python manage.py runserver` 即可；
部署上線時用環境變數覆蓋 SECRET_KEY / DEBUG / ALLOWED_HOSTS（見 README）。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- 安全性相關：上線時務必用環境變數覆蓋 ----
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-change-me-before-deploy",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
# 上線（DEBUG=0）卻還在用預設金鑰 → 直接報錯，避免把不安全的設定推上線
if not DEBUG and SECRET_KEY.startswith("dev-only-"):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("上線前請設定環境變數 DJANGO_SECRET_KEY")

# 例如部署到 PythonAnywhere：DJANGO_CSRF_TRUSTED_ORIGINS=https://xxx.pythonanywhere.com
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 本專案的三個 app
    "education",  # 衛教主題、Quiz、量測前檢查清單
    "records",    # 血壓紀錄（新增、查詢、趨勢圖、CSV）
    "accounts",   # 註冊／登入
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # 共用版型 base.html 放這裡
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---- 資料庫：SQLite（提案第 08 頁）----
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# ---- 語系與時區：繁體中文、台北時間 ----
LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

# ---- 靜態檔 ----
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # 部署時 collectstatic 的輸出位置

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- 登入相關導向 ----
# ---- 上線時的安全設定（只在 DEBUG=0 時啟用，本機開發不受影響）----
if not DEBUG:
    SESSION_COOKIE_SECURE = True      # Cookie 只透過 HTTPS 傳送
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # PythonAnywhere / Render 前面有反向代理
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_REFERRER_POLICY = "same-origin"

# 登入維持 90 天：長輩忘記密碼就等於流失（登入頁可取消「記住我」）
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "records:list"
LOGOUT_REDIRECT_URL = "education:home"
