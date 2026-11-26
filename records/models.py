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


class Challenge722(models.Model):
    """
    「我的 722 週」：一次連續 7 天、每天早晚各一次的量測挑戰。

    國健署建議 18 歲以上民眾每年至少用 722 原則在家量一次血壓，
    所以挑戰有明確的起訖日；結束後可以列印就醫報告，一年後再做一次。
    morning_time / evening_time 是使用者平常「起床後」「睡前」的時間，
    只用來產生行事曆提醒，不影響紀錄本身。
    """
    DAYS = 7

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="challenges", verbose_name="使用者")
    start_date = models.DateField("開始日期")
    morning_time = models.TimeField("早上提醒時間（起床後）")
    evening_time = models.TimeField("晚上提醒時間（睡前）")
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "722 週挑戰"
        verbose_name_plural = "722 週挑戰"

    def __str__(self):
        return f"{self.user} 722 週 {self.start_date:%Y-%m-%d}"

    @property
    def end_date(self):
        from datetime import timedelta
        return self.start_date + timedelta(days=self.DAYS - 1)

    def is_finished(self, today=None):
        from django.utils import timezone
        return (today or timezone.localdate()) > self.end_date
