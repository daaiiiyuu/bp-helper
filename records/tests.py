"""
執行：python manage.py test
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from education.content import CHECKLIST_ITEMS

from .models import BloodPressureRecord


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
        self.assertEqual(r.context["progress"]["sessions"], 3)

    def test_edit_and_delete(self):
        rec = self._make(self.user, 0)
        self.client.post(reverse("records:edit", args=[rec.pk]), {
            "measured_at": self.now.strftime("%Y-%m-%dT%H:%M"), "period": "evening",
            "systolic": 118, "diastolic": 76, "pulse": 66, "note": "改"})
        rec.refresh_from_db()
        self.assertEqual(rec.systolic, 118)
        self.client.post(reverse("records:delete", args=[rec.pk]))
        self.assertFalse(BloodPressureRecord.objects.exists())
