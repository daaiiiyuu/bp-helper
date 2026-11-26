from django.urls import path

from . import views

app_name = "education"

urlpatterns = [
    path("", views.home, name="home"),                                   # ① 首頁
    path("learn/", views.topic_list, name="topics"),                     # ② 選擇主題
    path("learn/<slug:slug>/", views.topic_step, name="topic"),          # ③ 圖文學習（第 1 頁）
    path("learn/<slug:slug>/<int:step>/", views.topic_step, name="topic_step"),
    path("quiz/", views.quiz_start, name="quiz_start"),                  # ④ Quiz 確認
    path("quiz/result/", views.quiz_result, name="quiz_result"),
    path("quiz/<int:order>/", views.quiz_question, name="quiz_question"),
    path("checklist/", views.checklist, name="checklist"),               # 量測前檢查清單
    path("qr/", views.qr_code, name="qr"),                               # 手機掃碼開啟
]
