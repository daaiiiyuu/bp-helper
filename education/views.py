"""
education app 的 View：首頁、衛教主題、Quiz、量測前檢查清單、QR Code

學習進度、Quiz 作答都存在 session（瀏覽器的登入狀態），
所以「不用註冊也能學、能測驗」；只有血壓紀錄需要帳號。
"""
import io
import time

import qrcode
import qrcode.image.svg
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .content import SOURCE_722, TOPIC_BY_SLUG, TOPICS
from .forms import ChecklistForm
from .models import Question

# 完成檢查清單後，多久之內進到「輸入血壓」會自動帶入已勾選（秒）
CHECKLIST_VALID_SECONDS = 60 * 60


# ------------------------------------------------------------------
# ① 首頁
# ------------------------------------------------------------------
def home(request):
    return render(request, "education/home.html", {"topics": TOPICS})


# ------------------------------------------------------------------
# ② 選擇主題（看過的主題會打勾）
# ------------------------------------------------------------------
def topic_list(request):
    done = set(request.session.get("topics_done", []))
    topics = [{**t, "done": t["slug"] in done} for t in TOPICS]
    return render(request, "education/topic_list.html", {
        "topics": topics,
        "done_count": len(done & set(TOPIC_BY_SLUG)),
        "total": len(TOPICS),
    })


# ------------------------------------------------------------------
# ③ 圖文學習：一頁一步驟，圖片 + 短句
# ------------------------------------------------------------------
def topic_step(request, slug, step=1):
    topic = TOPIC_BY_SLUG.get(slug)
    if topic is None:
        raise Http404("找不到這個衛教主題")
    steps = topic["steps"]
    if not 1 <= step <= len(steps):
        raise Http404("沒有這一頁")

    is_last = step == len(steps)
    if is_last:
        # 讀到最後一頁就算看過，在主題列表打勾
        done = set(request.session.get("topics_done", []))
        done.add(slug)
        request.session["topics_done"] = sorted(done)

    idx = [t["slug"] for t in TOPICS].index(slug)
    next_topic = TOPICS[idx + 1] if idx + 1 < len(TOPICS) else None

    return render(request, "education/topic_step.html", {
        "topic": topic,
        "item": steps[step - 1],
        "step": step,
        "total": len(steps),
        "progress": round(step / len(steps) * 100),
        "prev_step": step - 1 if step > 1 else None,
        "next_step": step + 1 if not is_last else None,
        "is_last": is_last,
        "next_topic": next_topic,
        "source": SOURCE_722,
    })


# ------------------------------------------------------------------
# ④ Quiz：每題作答後立即回饋，答錯給解說與「返回重新複習」
# session["quiz"] = {"answers": {"1": "B", ...}}
# ------------------------------------------------------------------
def quiz_start(request):
    request.session["quiz"] = {"answers": {}}
    first = Question.objects.order_by("order").first()
    if first is None:
        return render(request, "education/quiz_empty.html")
    return redirect("education:quiz_question", order=first.order)


def quiz_question(request, order):
    question = get_object_or_404(Question.objects.prefetch_related("choices"), order=order)
    questions = list(Question.objects.order_by("order").values_list("order", flat=True))
    position = questions.index(order) + 1
    next_order = questions[position] if position < len(questions) else None

    quiz = request.session.get("quiz", {"answers": {}})
    selected = None
    is_correct = None

    if request.method == "POST":
        label = request.POST.get("choice", "")
        choice = question.choices.filter(label=label).first()
        if choice is not None:
            selected = choice.label
            is_correct = choice.is_correct
            quiz["answers"][str(order)] = {"label": selected, "correct": is_correct}
            request.session["quiz"] = quiz
    elif str(order) in quiz["answers"]:
        # 重新整理頁面時，保留剛剛的作答結果
        prev = quiz["answers"][str(order)]
        selected, is_correct = prev["label"], prev["correct"]

    topic = TOPIC_BY_SLUG.get(question.topic_slug)
    return render(request, "education/quiz_question.html", {
        "question": question,
        "choices": question.choices.all(),
        "position": position,
        "total": len(questions),
        "progress": round(position / len(questions) * 100),
        "selected": selected,
        "answered": selected is not None,
        "is_correct": is_correct,
        "correct_choice": question.correct_choice,
        "next_order": next_order,
        "review_url": reverse("education:topic", args=[topic["slug"]]) if topic else None,
        "review_title": topic["title"] if topic else None,
    })


def quiz_result(request):
    answers = request.session.get("quiz", {}).get("answers", {})
    questions = Question.objects.order_by("order").prefetch_related("choices")
    rows = []
    for q in questions:
        a = answers.get(str(q.order))
        topic = TOPIC_BY_SLUG.get(q.topic_slug)
        rows.append({
            "question": q,
            "answered": a is not None,
            "label": a["label"] if a else None,
            "correct": a["correct"] if a else False,
            "correct_choice": q.correct_choice,
            "topic": topic,
        })
    score = sum(1 for r in rows if r["correct"])
    return render(request, "education/quiz_result.html", {
        "rows": rows,
        "score": score,
        "total": len(rows),
        "all_correct": score == len(rows) and len(rows) > 0,
    })


# ------------------------------------------------------------------
# 量測前檢查清單：全部勾完才算完成，接著可以直接去輸入血壓
# ------------------------------------------------------------------
def checklist(request):
    if request.method == "POST":
        form = ChecklistForm(request.POST)
        if form.is_valid():
            request.session["checklist_ok_at"] = time.time()
            return render(request, "education/checklist_done.html")
    else:
        form = ChecklistForm()
    return render(request, "education/checklist.html", {"form": form, "source": SOURCE_722})


def checklist_recently_done(request):
    """給 records app 用：一小時內是否完成過檢查清單"""
    ts = request.session.get("checklist_ok_at")
    return ts is not None and time.time() - ts < CHECKLIST_VALID_SECONDS


# ------------------------------------------------------------------
# 手機掃碼即可開啟：門診時衛教人員給民眾掃這個 QR Code
# ------------------------------------------------------------------
def qr_code(request):
    site_url = request.build_absolute_uri(reverse("education:home"))
    img = qrcode.make(site_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    # 去掉 XML 宣告，才能直接嵌進 HTML
    svg = svg[svg.find("<svg"):]
    return render(request, "education/qr.html", {"svg": svg, "site_url": site_url})
