from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.RememberMeLoginView.as_view(), name="login"),
    # Django 5 起登出必須用 POST（base.html 裡是一個小表單按鈕）
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("settings/", views.settings_page, name="settings"),
    path("password/", views.password_change, name="password_change"),
    path("delete/", views.delete_account, name="delete"),
]
