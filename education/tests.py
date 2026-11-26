from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .content import TOPICS
from .models import Question


class EducationPageTests(TestCase):
    def test_public_pages_ok(self):
        for name in ["education:home", "education:topics", "education:checklist", "education:qr",
                     "accounts:login", "accounts:signup"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_every_topic_step_renders(self):
        for t in TOPICS:
            for i in range(1, len(t["steps"]) + 1):
                r = self.client.get(reverse("education:topic_step", args=[t["slug"], i]))
                self.assertEqual(r.status_code, 200, f"{t['slug']} {i}")
        self.assertEqual(self.client.get(reverse("education:topic_step", args=["prepare", 99])).status_code, 404)

    def test_topic_marked_done_after_last_step(self):
        t = TOPICS[0]
        self.client.get(reverse("education:topic_step", args=[t["slug"], len(t["steps"])]))
        r = self.client.get(reverse("education:topics"))
        self.assertEqual(r.context["done_count"], 1)


class QuizTests(TestCase):
    def test_seeded_five_questions_one_correct_each(self):
        self.assertEqual(Question.objects.count(), 5)
        for q in Question.objects.all():
            self.assertEqual(q.choices.filter(is_correct=True).count(), 1)

    def test_quiz_flow_scoring(self):
        r = self.client.get(reverse("education:quiz_start"))
        self.assertRedirects(r, reverse("education:quiz_question", args=[1]))
        r = self.client.post(reverse("education:quiz_question", args=[1]), {"choice": "B"})
        self.assertContains(r, "正確")
        r = self.client.post(reverse("education:quiz_question", args=[2]), {"choice": "A"})
        self.assertContains(r, "再複習一下")
        self.assertContains(r, "返回重新複習")
        r = self.client.get(reverse("education:quiz_result"))
        self.assertEqual(r.context["score"], 1)


class SignupTests(TestCase):
    def test_signup_logs_in(self):
        r = self.client.post(reverse("accounts:signup"), {
            "username": "newuser", "password1": "Bp-722-check", "password2": "Bp-722-check"})
        self.assertRedirects(r, reverse("records:list"))
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_signup_blocks_external_next(self):
        r = self.client.post(reverse("accounts:signup") + "?next=https://evil.example.com/", {
            "username": "u2", "password1": "Bp-722-check", "password2": "Bp-722-check"})
        self.assertRedirects(r, reverse("records:list"))


class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amy", password="Bp-722-check")

    def test_remember_me_unchecked_expires_on_browser_close(self):
        self.client.post(reverse("accounts:login"), {"username": "amy", "password": "Bp-722-check"})
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_remember_me_checked_keeps_90_days(self):
        self.client.post(reverse("accounts:login"),
                         {"username": "amy", "password": "Bp-722-check", "remember_me": "on"})
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 90)

    def test_password_change_keeps_login(self):
        self.client.login(username="amy", password="Bp-722-check")
        r = self.client.post(reverse("accounts:password_change"), {
            "old_password": "Bp-722-check", "new_password1": "New-pass-722", "new_password2": "New-pass-722"})
        self.assertRedirects(r, reverse("accounts:settings"))
        self.assertEqual(self.client.get(reverse("records:list")).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-pass-722"))

    def test_delete_account_requires_password_and_cascades(self):
        from records.models import BloodPressureRecord
        from django.utils import timezone
        self.client.login(username="amy", password="Bp-722-check")
        BloodPressureRecord.objects.create(user=self.user, measured_at=timezone.now(),
                                           systolic=120, diastolic=80, pulse=70)
        self.client.post(reverse("accounts:delete"), {"password": "wrong"})
        self.assertTrue(User.objects.filter(username="amy").exists())
        r = self.client.post(reverse("accounts:delete"), {"password": "Bp-722-check"})
        self.assertRedirects(r, reverse("education:home"))
        self.assertFalse(User.objects.filter(username="amy").exists())
        self.assertEqual(BloodPressureRecord.objects.count(), 0)
