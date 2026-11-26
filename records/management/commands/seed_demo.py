"""
建立展示用帳號與 7 天的示範紀錄（期末展示用）

    python manage.py seed_demo            # 帳號 demo / 密碼 demo722bp
    python manage.py seed_demo --reset    # 先清掉 demo 的舊紀錄再重建

示範數值是隨機產生的假資料，只用來展示畫面，沒有任何醫療意義。
"""
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from records.models import BloodPressureRecord, Challenge722


class Command(BaseCommand):
    help = "建立 demo 帳號與 7 天示範血壓紀錄"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **opts):
        user, created = User.objects.get_or_create(username="demo")
        if created:
            user.set_password("demo722bp")
            user.save()
        if opts["reset"]:
            user.bp_records.all().delete()
            user.challenges.all().delete()

        rng = random.Random(722)
        today = timezone.localtime().replace(second=0, microsecond=0)
        n = 0
        for d in range(6, -1, -1):
            day = today - timedelta(days=d)
            for period, hour in (("morning", 7), ("evening", 22)):
                when = day.replace(hour=hour, minute=rng.randint(0, 40))
                if when > today or (d == 2 and period == "evening"):  # 故意漏一次，展示進度格
                    continue
                BloodPressureRecord.objects.create(
                    user=user, measured_at=when, period=period,
                    systolic=rng.randint(116, 134), diastolic=rng.randint(74, 86),
                    pulse=rng.randint(64, 80), readings_count=2, checklist_done=True)
                n += 1
        # 進行中的 722 週：5 天前開始，今天是第 6 天
        if not user.challenges.exists():
            Challenge722.objects.create(user=user, start_date=today.date() - timedelta(days=5),
                                        morning_time="07:00", evening_time="22:00")
        self.stdout.write(self.style.SUCCESS(f"demo / demo722bp，新增 {n} 筆示範紀錄與 1 個 722 週"))
