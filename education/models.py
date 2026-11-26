"""
Quiz 題庫的資料結構。

題目放在資料庫裡（而不是寫死在程式），
衛教人員可以直接從 /admin 後台新增或修改題目。
預設 5 題由 migrations/0002_seed_quiz.py 自動建立。
"""
from django.db import models


class Question(models.Model):
    order = models.PositiveSmallIntegerField("題號", unique=True)
    text = models.CharField("題目", max_length=200)
    explanation = models.TextField("解說（答錯時顯示）")
    tip = models.CharField("小提醒", max_length=200, blank=True)
    # 答錯時「返回重新複習」要跳到哪個衛教主題（對應 content.TOPICS 的 slug）
    topic_slug = models.CharField("相關衛教主題", max_length=30, blank=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "測驗題目"
        verbose_name_plural = "測驗題目"

    def __str__(self):
        return f"Q{self.order}. {self.text}"

    @property
    def correct_choice(self):
        return self.choices.filter(is_correct=True).first()


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    label = models.CharField("選項代號", max_length=1)  # A / B / C / D
    text = models.CharField("選項內容", max_length=100)
    is_correct = models.BooleanField("正確答案", default=False)

    class Meta:
        ordering = ["label"]
        verbose_name = "選項"
        verbose_name_plural = "選項"

    def __str__(self):
        return f"{self.label}. {self.text}"
