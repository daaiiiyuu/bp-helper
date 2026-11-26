"""
執行：python manage.py test
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from education.content import CHECKLIST_ITEMS

from .models import BloodPressureRecord, Challenge722
from .progress import compute_progress


def checklist_post():
    return {f"check_{k}": "on" for k, _ in CHECKLIST_ITEMS}


class RecordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amy", password="pass12345")
        self.other = User.objects.create_user("bob", password="pass12345")
        self.client.login(username="amy", password="pass12345")
        self.now = timezone.localtime().replace(second=0, microsecond=0)

    def post_record(self, **extra):
        data = {
            "measured_at": self.now.strftime("%Y-%m-%dT%H:%M"),
            "period": "morning",
            "systolic_1": 128, "diastolic_1": 82, "pulse_1": 70,
            "systolic_2": 125, "diastolic_2": 79, "pulse_2": 71,
            **checklist_post(),
        }
        data.update(extra)
        return self.client.post(reverse("records:create"), data)

    def test_login_required(self):
        self.client.logout()
        r = self.client.get(reverse("records:list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r.url)

    def test_two_readings_are_averaged(self):
        r = self.post_record()
        self.assertRedirects(r, reverse("records:list"))
        rec = BloodPressureRecord.objects.get()
        # (128+125)/2 = 126.5 → 127；(82+79)/2 = 80.5 → 81；(70+71)/2 = 70.5 → 71（四捨五入）
        self.assertEqual((rec.systolic, rec.diastolic, rec.pulse), (127, 81, 71))
        self.assertEqual(rec.readings_count, 2)
        self.assertTrue(rec.checklist_done)
        self.assertEqual(rec.user, self.user)

    def test_single_reading(self):
        self.post_record(systolic_2="", diastolic_2="", pulse_2="")
        rec = BloodPressureRecord.objects.get()
        self.assertEqual((rec.systolic, rec.readings_count), (128, 1))

    def test_partial_second_reading_rejected(self):
        r = self.post_record(diastolic_2="", pulse_2="")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(BloodPressureRecord.objects.count(), 0)

    def test_checklist_required(self):
        data = checklist_post()
        data.pop(next(iter(data)))
        r = self.client.post(reverse("records:create"), {
            "measured_at": self.now.strftime("%Y-%m-%dT%H:%M"), "period": "morning",
            "systolic_1": 120, "diastolic_1": 80, "pulse_1": 70, **data})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(BloodPressureRecord.objects.count(), 0)

    def test_checklist_page_skips_inline_checklist(self):
        # 在檢查清單頁全勾後，輸入血壓頁不用再勾一次
        self.client.post(reverse("education:checklist"), {k: "on" for k, _ in CHECKLIST_ITEMS})
        r = self.client.post(reverse("records:create"), {
            "period": "evening",
            "systolic_1": 120, "diastolic_1": 80, "pulse_1": 70})
        self.assertRedirects(r, reverse("records:list"))

    def test_systolic_must_exceed_diastolic(self):
        self.post_record(systolic_1=80, diastolic_1=120, systolic_2="", diastolic_2="", pulse_2="")
        self.assertEqual(BloodPressureRecord.objects.count(), 0)

    def test_out_of_range_rejected(self):
        self.post_record(systolic_1=1200, systolic_2="", diastolic_2="", pulse_2="")
        self.assertEqual(BloodPressureRecord.objects.count(), 0)

    def test_time_defaults_to_now(self):
        # 沒勾「補登」：不管表單送來什麼時間，一律用伺服器的現在時間
        before = timezone.now() - timedelta(minutes=1)
        self.post_record(measured_at="", systolic_2="", diastolic_2="", pulse_2="")
        rec = BloodPressureRecord.objects.get()
        self.assertGreaterEqual(rec.measured_at, before)
        self.assertLessEqual(rec.measured_at, timezone.now())

    def test_backfill_uses_given_time(self):
        past = (self.now - timedelta(days=2)).replace(hour=7, minute=15)
        self.post_record(backfill="on", measured_at=past.strftime("%Y-%m-%dT%H:%M"))
        rec = BloodPressureRecord.objects.get()
        self.assertEqual(timezone.localtime(rec.measured_at), past)

    def test_backfill_requires_time(self):
        r = self.post_record(backfill="on", measured_at="")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "補登紀錄請填寫量測日期與時間")
        self.assertEqual(BloodPressureRecord.objects.count(), 0)

    def test_future_time_rejected(self):
        future = (self.now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.post_record(backfill="on", measured_at=future)
        self.assertEqual(BloodPressureRecord.objects.count(), 0)

    def _make(self, user, days_ago, sys=120, dia=80, period="morning"):
        return BloodPressureRecord.objects.create(
            user=user, measured_at=self.now - timedelta(days=days_ago),
            period=period, systolic=sys, diastolic=dia, pulse=70)

    def test_users_only_see_own_records(self):
        self._make(self.user, 0, sys=131)
        theirs = self._make(self.other, 0, sys=177)
        r = self.client.get(reverse("records:list"))
        self.assertContains(r, "131/80")
        self.assertNotContains(r, "177/80")
        # 也不能修改或刪除別人的紀錄
        self.assertEqual(self.client.get(reverse("records:edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("records:delete", args=[theirs.pk])).status_code, 404)

    def test_date_filter_and_csv(self):
        self._make(self.user, 0, sys=141)
        self._make(self.user, 20, sys=151)
        start = (self.now - timedelta(days=3)).date().isoformat()
        r = self.client.get(reverse("records:list"), {"start": start})
        self.assertContains(r, "141/80")
        self.assertNotContains(r, "151/80")
        csv = self.client.get(reverse("records:export"), {"start": start}).content.decode("utf-8-sig")
        self.assertIn("141", csv)
        self.assertNotIn("151", csv)

    def test_722_progress(self):
        self._make(self.user, 0, period="morning")
        self._make(self.user, 0, period="evening")
        self._make(self.user, 1, period="morning")
        self._make(self.user, 10, period="morning")  # 超過 7 天，不算
        r = self.client.get(reverse("records:list"))
        self.assertEqual(r.context["progress"]["done"], 3)

    def test_edit_and_delete(self):
        rec = self._make(self.user, 0)
        self.client.post(reverse("records:edit", args=[rec.pk]), {
            "measured_at": self.now.strftime("%Y-%m-%dT%H:%M"), "period": "evening",
            "systolic": 118, "diastolic": 76, "pulse": 66, "note": "改"})
        rec.refresh_from_db()
        self.assertEqual(rec.systolic, 118)
        self.client.post(reverse("records:delete", args=[rec.pk]))
        self.assertFalse(BloodPressureRecord.objects.exists())


class ChallengeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amy", password="pass12345")
        self.client.login(username="amy", password="pass12345")
        self.today = timezone.localdate()

    def start(self, when="0"):
        r = self.client.post(reverse("records:challenge_start"), {
            "start_when": when, "morning_time": "07:00", "evening_time": "21:30"})
        return Challenge722.objects.latest("created_at"), r

    def rec(self, day_offset, period, sys=120, hour=None):
        hour = hour if hour is not None else (7 if period == "morning" else 21)
        when = timezone.make_aware(timezone.datetime.combine(
            self.today + timedelta(days=day_offset), timezone.datetime.min.time()).replace(hour=hour))
        return BloodPressureRecord.objects.create(
            user=self.user, measured_at=when, period=period,
            systolic=sys, diastolic=80, pulse=70, checklist_done=True)

    def test_start_today_and_tomorrow(self):
        ch, r = self.start("0")
        self.assertRedirects(r, reverse("records:challenge", args=[ch.pk]))
        self.assertEqual(ch.start_date, self.today)
        self.assertEqual(ch.end_date, self.today + timedelta(days=6))
        ch2, _ = self.start("1")
        self.assertEqual(ch2.start_date, self.today + timedelta(days=1))

    def test_progress_counts_only_challenge_window(self):
        ch, _ = self.start("0")
        self.rec(0, "morning")
        self.rec(-1, "morning")             # 挑戰開始前，不算
        self.rec(0, "other", hour=14)       # 「其他時間」不算 722
        p = compute_progress(self.user, ch.start_date)
        self.assertEqual((p["done"], p["total"]), (1, 14))
        self.assertEqual(p["today_no"], 1)
        r = self.client.get(reverse("records:list"))
        self.assertEqual(r.context["panel"], "active")

    def test_missed_slots(self):
        ch = Challenge722.objects.create(user=self.user, start_date=self.today - timedelta(days=2),
                                         morning_time="07:00", evening_time="21:30")
        self.rec(-2, "morning")
        p = compute_progress(self.user, ch.start_date)
        # 前兩天共 4 格，量了 1 格 → 錯過 3 格
        self.assertEqual((p["done"], p["missed"]), (1, 3))

    def test_finished_panel_and_report(self):
        ch = Challenge722.objects.create(user=self.user, start_date=self.today - timedelta(days=8),
                                         morning_time="07:00", evening_time="21:30")
        r1 = self.rec(-8, "morning", sys=130)
        r1.note = "昨晚睡不好"
        r1.save()
        self.rec(-8, "evening", sys=120)
        self.assertEqual(self.client.get(reverse("records:list")).context["panel"], "finished")
        r = self.client.get(reverse("records:challenge_report", args=[ch.pk]))
        self.assertContains(r, "居家血壓 722 量測紀錄")
        self.assertContains(r, "130/80")
        self.assertContains(r, "昨晚睡不好")
        self.assertEqual(r.context["progress"]["avg"]["sys"], 125)

    def test_ics_calendar(self):
        ch = Challenge722.objects.create(user=self.user, start_date=self.today + timedelta(days=1),
                                         morning_time="07:00", evening_time="21:30")
        r = self.client.get(reverse("records:challenge_ics", args=[ch.pk]))
        self.assertEqual(r["Content-Type"], "text/calendar; charset=utf-8")
        body = r.content.decode("utf-8")
        # 7 天 × 2 次 + 一年後提醒 = 15 個事件
        self.assertEqual(body.count("BEGIN:VEVENT"), 15)
        self.assertEqual(body.count("BEGIN:VALARM"), 15)
        # 台北 07:00 = UTC 前一天 23:00
        d = ch.start_date
        self.assertIn(f"DTSTART:{(d - timedelta(days=1)):%Y%m%d}T230000Z", body)
        # 每行不超過 75 bytes、用 CRLF 換行
        for line in body.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        self.assertTrue(body.endswith("END:VCALENDAR\r\n"))

    def test_ics_skips_past_slots(self):
        ch = Challenge722.objects.create(user=self.user, start_date=self.today - timedelta(days=3),
                                         morning_time="07:00", evening_time="21:30")
        body = self.client.get(reverse("records:challenge_ics", args=[ch.pk])).content.decode()
        self.assertLess(body.count("BEGIN:VEVENT"), 15)

    def test_other_users_challenge_404(self):
        other = User.objects.create_user("bob", password="pass12345")
        ch = Challenge722.objects.create(user=other, start_date=self.today,
                                         morning_time="07:00", evening_time="21:30")
        for name in ("records:challenge", "records:challenge_ics", "records:challenge_report"):
            self.assertEqual(self.client.get(reverse(name, args=[ch.pk])).status_code, 404, name)


class ChecklistModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amy", password="pass12345")
        self.client.login(username="amy", password="pass12345")

    def post(self, **extra):
        return self.client.post(reverse("records:create"), {
            "period": "morning", "systolic_1": 120, "diastolic_1": 80, "pulse_1": 70, **extra})

    def test_switches_to_quick_after_three_records(self):
        self.assertEqual(self.client.get(reverse("records:create")).context["checklist_mode"], "full")
        for _ in range(3):
            self.post(**checklist_post())
        self.assertEqual(self.client.get(reverse("records:create")).context["checklist_mode"], "quick")
        # 熟練模式只要一個總確認
        r = self.post(check_all="on")
        self.assertRedirects(r, reverse("records:list"))
        # 沒勾總確認不能存
        r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(BloodPressureRecord.objects.count(), 4)
