"""
預設 5 題衛教 Quiz（內容依國健署「居家量血壓 722」衛教資訊）
migrate 時自動寫入資料庫；之後可在 /admin 修改。
"""
from django.db import migrations

QUIZ = [
    {
        "order": 1,
        "text": "測量血壓前，應先安靜休息多久？",
        "choices": [("A", "不需要休息，直接測量", False), ("B", "至少 5 分鐘", True),
                    ("C", "30 秒即可", False), ("D", "一定要休息 30 分鐘", False)],
        "explanation": "量血壓前應先靜坐休息五分鐘，避免剛活動完就測量，影響血壓數值的準確性。",
        "tip": "測量時應坐穩、背部有支撐、雙腳平放地面，並保持安靜。",
        "topic": "prepare",
    },
    {
        "order": 2,
        "text": "量測前半小時，下列哪一件事應該避免？",
        "choices": [("A", "安靜坐著看書", False), ("B", "喝咖啡或茶", True),
                    ("C", "先去上廁所", False), ("D", "準備好紀錄本", False)],
        "explanation": "量測前半小時應避免抽菸、進食、洗澡、運動、喝酒，以及喝咖啡或茶。"
                       "上廁所反而是建議的，因為不要憋尿。",
        "tip": "量測前先上廁所，不要憋尿。",
        "topic": "prepare",
    },
    {
        "order": 3,
        "text": "量血壓時，壓脈帶的中心應該在什麼位置？",
        "choices": [("A", "大約與手腕同高", False), ("B", "大約與心臟同高", True),
                    ("C", "越高越好，靠近肩膀", False), ("D", "位置不重要", False)],
        "explanation": "壓脈帶的中心大約要與心臟同高，鬆緊以大約可以放入兩根手指為準。",
        "tip": "坐在有靠背的椅子上，雙腳平放，量測時不說話、不移動。",
        "topic": "posture",
    },
    {
        "order": 4,
        "text": "「722」原則中，「每天量 2 次」是指什麼時候？",
        "choices": [("A", "午餐前和午餐後", False), ("B", "早上起床後、晚上睡覺前", True),
                    ("C", "運動前和運動後", False), ("D", "想到的時候量兩次就好", False)],
        "explanation": "722 原則是連續量 7 天，每天早上起床後、晚上睡覺前各量一次。",
        "tip": "7 天 × 2 次 × 2 遍，一共是 28 個數值。",
        "topic": "722",
    },
    {
        "order": 5,
        "text": "每一次量測，應該怎麼記錄數值？",
        "choices": [("A", "量 1 遍就好", False), ("B", "量 2 遍，取平均值", True),
                    ("C", "量 3 遍，取最高的", False), ("D", "量 2 遍，取最低的", False)],
        "explanation": "722 原則的最後一個 2：每次量兩遍，取兩遍的平均值記錄下來。",
        "tip": "在本網站輸入兩遍的數值，系統會自動幫你算平均。",
        "topic": "722",
    },
]


def seed(apps, schema_editor):
    Question = apps.get_model("education", "Question")
    Choice = apps.get_model("education", "Choice")
    for q in QUIZ:
        question = Question.objects.create(
            order=q["order"], text=q["text"], explanation=q["explanation"],
            tip=q["tip"], topic_slug=q["topic"],
        )
        for label, text, correct in q["choices"]:
            Choice.objects.create(question=question, label=label, text=text, is_correct=correct)


def unseed(apps, schema_editor):
    apps.get_model("education", "Question").objects.filter(
        order__in=[q["order"] for q in QUIZ]).delete()


class Migration(migrations.Migration):
    dependencies = [("education", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
