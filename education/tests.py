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
