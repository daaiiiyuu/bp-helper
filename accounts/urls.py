from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html",
                                                       redirect_authenticated_user=True), name="login"),
    # Django 5 起登出必須用 POST（base.html 裡是一個小表單按鈕）
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
