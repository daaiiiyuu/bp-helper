"""
血壓紀錄資料結構（提案第 08 頁）

欄位：id（Django 自動產生的主鍵）、systolic、diastolic、pulse、measured_at
另外加上：
  user           — 「個人帳號」：每個人只看得到自己的紀錄
  period         — 早上／晚上，用來計算 722 進度
  readings_count — 這筆是 1 遍或 2 遍的平均
  checklist_done — 是否完成量測前檢查清單
  note           — 備註（例如：今天有點頭暈）
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class BloodPressureRecord(models.Model):
    class Period(models.TextChoices):
        MORNING = "morning", "早上（起床後）"
        EVENING = "evening", "晚上（睡覺前）"
        OTHER = "other", "其他時間"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="bp_records", verbose_name="使用者",
    )
    measured_at = models.DateTimeField("量測日期與時間")
    period = models.CharField("量測時段", max_length=10, choices=Period.choices,
                              default=Period.MORNING)
    # 數值範圍只是「防止打錯字」的輸入檢查（例如多打一個 0），不是醫療判讀標準
    systolic = models.PositiveSmallIntegerField(
        "收縮壓（mmHg）", validators=[MinValueValidator(50), MaxValueValidator(260)])
    diastolic = models.PositiveSmallIntegerField(
        "舒張壓（mmHg）", validators=[MinValueValidator(30), MaxValueValidator(160)])
    pulse = models.PositiveSmallIntegerField(
        "心跳（次／分鐘）", validators=[MinValueValidator(30), MaxValueValidator(220)])
    readings_count = models.PositiveSmallIntegerField("量測遍數", default=2)
    checklist_done = models.BooleanField("已完成量測前檢查", default=False)
    note = models.CharField("備註", max_length=200, blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        ordering = ["-measured_at"]
        verbose_name = "血壓紀錄"
        verbose_name_plural = "血壓紀錄"
        indexes = [models.Index(fields=["user", "measured_at"])]

    def __str__(self):
        return f"{self.user} {self.measured_at:%Y-%m-%d %H:%M} {self.systolic}/{self.diastolic}"
