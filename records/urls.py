from django.urls import path

from . import views

app_name = "records"

urlpatterns = [
    path("", views.record_list, name="list"),                    # ⑥ 歷史紀錄
    path("new/", views.record_create, name="create"),            # ⑤ 輸入血壓
    path("<int:pk>/edit/", views.record_edit, name="edit"),
    path("<int:pk>/delete/", views.record_delete, name="delete"),
    path("export.csv", views.export_csv, name="export"),
]
