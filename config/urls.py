"""
URL Routing：分配首頁、衛教、測驗、紀錄等網址（提案第 08 頁）
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),   # 註冊／登入／登出
    path("records/", include("records.urls")),     # 血壓紀錄
    path("", include("education.urls")),           # 首頁、衛教主題、Quiz、檢查清單
]
