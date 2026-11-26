"""
records app 的 View：血壓紀錄新增、查詢（依日期篩選）、趨勢圖、修改、刪除、匯出 CSV

所有 View 都加 @login_required，而且查詢一律 filter(user=request.user)，
確保每個人只看得到、改得到自己的紀錄。
"""
import csv
from datetime import time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.urls import reverse

from education.content import CHECKLIST_ITEMS, SOURCE_722, SOURCE_REFERENCE_VALUE
from education.views import checklist_recently_done

from .calendar import build_ics
from .charts import build_trend_chart
from .forms import ChallengeForm, DateFilterForm, RecordEditForm, RecordForm, guess_period
from .models import BloodPressureRecord, Challenge722
from .progress import compute_progress, rolling_progress

Period = BloodPressureRecord.Period

# 有幾筆「完成檢查」的紀錄之後，檢查清單改成一鍵確認（熟練模式）
QUICK_CHECKLIST_AFTER = 3
# 挑戰結束後幾天內，紀錄頁仍顯示「完成！看報告」
SHOW_FINISHED_DAYS = 30


def latest_challenge(user):
    return Challenge722.objects.filter(user=user).first()  # ordering = -created_at


def checklist_mode(request):
    """
    full  ：6 項逐一勾選（新手）
    quick ：一個「我已完成量測前準備」確認，清單收合可展開（熟練）
    none  ：一小時內剛在檢查清單頁完成過，不用再勾
    """
    if checklist_recently_done(request):
        return "none"
    done = BloodPressureRecord.objects.filter(user=request.user, checklist_done=True).count()
    return "quick" if done >= QUICK_CHECKLIST_AFTER else "full"


def _filtered_records(request):
    """依網址上的 ?start=&end= 篩選目前使用者的紀錄"""
    qs = BloodPressureRecord.objects.filter(user=request.user)
    form = DateFilterForm(request.GET or None)
    if form.is_bound and form.is_valid():
        if form.cleaned_data.get("start"):
            qs = qs.filter(measured_at__date__gte=form.cleaned_data["start"])
        if form.cleaned_data.get("end"):
            qs = qs.filter(measured_at__date__lte=form.cleaned_data["end"])
    return qs, form


# ------------------------------------------------------------------
# ⑥ 歷史紀錄：依日期篩選 + 趨勢圖 + 722 進度
# ------------------------------------------------------------------
@login_required
def record_list(request):
    qs, filter_form = _filtered_records(request)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))

    # 保留篩選條件，讓分頁、匯出 CSV 的連結也套用同樣的日期範圍
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "records/record_list.html", {
        "page": page,
        "filter_form": filter_form,
        "is_filtered": bool(request.GET.get("start") or request.GET.get("end")),
        "query": params.urlencode(),
        "total": page.paginator.count,
        "chart": build_trend_chart(qs),
        "ref_source": SOURCE_REFERENCE_VALUE,
        **_challenge_panel(request.user),
    })


def _challenge_panel(user):
    """紀錄頁上方的 722 面板：進行中的挑戰 / 剛完成的挑戰 / 最近 7 天＋開始按鈕"""
    today = timezone.localdate()
    ch = latest_challenge(user)
    if ch and not ch.is_finished(today):
        return {"panel": "active", "challenge": ch, "progress": compute_progress(user, ch.start_date)}
    if ch and (today - ch.end_date).days <= SHOW_FINISHED_DAYS:
        return {"panel": "finished", "challenge": ch, "progress": compute_progress(user, ch.start_date)}
    return {"panel": "rolling", "challenge": None, "progress": rolling_progress(user)}


# ------------------------------------------------------------------
# ⑤ 輸入血壓：先完成檢查清單，再填數值
# ------------------------------------------------------------------
@login_required
def record_create(request):
    mode = checklist_mode(request)
    if request.method == "POST":
        form = RecordForm(request.POST, checklist_mode=mode)
        if form.is_valid():
            record = BloodPressureRecord.objects.create(user=request.user, **form.to_record_values())
            msg = f"已儲存：{record.systolic}/{record.diastolic} mmHg，心跳 {record.pulse}"
            if record.readings_count == 2:
                msg += "（兩遍平均）"
            ch = latest_challenge(request.user)
            if ch and not ch.is_finished() and record.period != Period.OTHER:
                p = compute_progress(request.user, ch.start_date)
                msg += f"。722 週進度 {p['done']}/{p['total']}"
                if p["done"] == p["total"]:
                    msg += "，全部完成！可以列印就醫報告了"
            messages.success(request, msg)
            return redirect("records:list")
    else:
        now = timezone.localtime()
        form = RecordForm(
            checklist_mode=mode,
            initial={"measured_at": now.strftime("%Y-%m-%dT%H:%M"), "period": guess_period(now)},
        )
    return render(request, "records/record_form.html", {
        "form": form,
        "checklist_mode": mode,
        "checklist_items": CHECKLIST_ITEMS,
        "now": timezone.localtime(),
    })


@login_required
def record_edit(request, pk):
    record = get_object_or_404(BloodPressureRecord, pk=pk, user=request.user)
    form = RecordEditForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "紀錄已更新")
        return redirect("records:list")
    return render(request, "records/record_edit.html", {"form": form, "record": record})


@login_required
def record_delete(request, pk):
    record = get_object_or_404(BloodPressureRecord, pk=pk, user=request.user)
    if request.method == "POST":
        record.delete()
        messages.success(request, "紀錄已刪除")
        return redirect("records:list")
    return render(request, "records/record_confirm_delete.html", {"record": record})


# ------------------------------------------------------------------
# 匯出 CSV（套用目前的日期篩選），就醫時可以印出來給醫師看
# ------------------------------------------------------------------
@login_required
def export_csv(request):
    qs, _ = _filtered_records(request)
    filename = f"blood_pressure_{timezone.localdate():%Y%m%d}.csv"
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.write("\ufeff")  # BOM：讓 Excel 開啟時中文不會變亂碼
    w = csv.writer(resp)
    w.writerow(["量測日期", "時間", "時段", "收縮壓(mmHg)", "舒張壓(mmHg)",
                "心跳(次/分)", "量測遍數", "已完成量測前檢查", "備註"])
    for r in qs.order_by("measured_at"):
        t = timezone.localtime(r.measured_at)
        w.writerow([t.strftime("%Y-%m-%d"), t.strftime("%H:%M"), r.get_period_display(),
                    r.systolic, r.diastolic, r.pulse, r.readings_count,
                    "是" if r.checklist_done else "否", r.note])
    return resp


# ------------------------------------------------------------------
# 我的 722 週：開始挑戰 → 加入行事曆 → 每天量 → 列印就醫報告
# ------------------------------------------------------------------
@login_required
def challenge_start(request):
    current = latest_challenge(request.user)
    active = current if current and not current.is_finished() else None
    if request.method == "POST":
        form = ChallengeForm(request.POST)
        if form.is_valid():
            ch = form.save(commit=False)
            ch.user = request.user
            ch.start_date = timezone.localdate() + timedelta(days=int(form.cleaned_data["start_when"]))
            ch.save()
            messages.success(request, f"722 週開始了！{ch.start_date:%m/%d} 到 {ch.end_date:%m/%d}")
            return redirect("records:challenge", pk=ch.pk)
    else:
        now = timezone.localtime()
        # 晚上才開始的話，今天早上已經錯過，預設從明天開始
        form = ChallengeForm(initial={
            "start_when": "0" if now.hour < 12 else "1",
            "morning_time": time(7, 0),
            "evening_time": time(21, 30),
        })
    return render(request, "records/challenge_start.html", {
        "form": form, "active": active, "source": SOURCE_722,
    })


@login_required
def challenge_detail(request, pk):
    ch = get_object_or_404(Challenge722, pk=pk, user=request.user)
    return render(request, "records/challenge_detail.html", {
        "challenge": ch,
        "progress": compute_progress(request.user, ch.start_date),
        "finished": ch.is_finished(),
    })


@login_required
def challenge_ics(request, pk):
    ch = get_object_or_404(Challenge722, pk=pk, user=request.user)
    content, _ = build_ics(ch, request.build_absolute_uri(reverse("records:create")),
                           host=request.get_host().split(":")[0])
    resp = HttpResponse(content, content_type="text/calendar; charset=utf-8")
    # inline：iPhone Safari 會直接跳出「加入行事曆」
    resp["Content-Disposition"] = f'inline; filename="722_{ch.start_date:%Y%m%d}.ics"'
    return resp


@login_required
def challenge_report(request, pk):
    ch = get_object_or_404(Challenge722, pk=pk, user=request.user)
    progress = compute_progress(request.user, ch.start_date)
    notes = [r for d in progress["days"] for p in ("morning", "evening")
             for r in d[p]["records"] if r.note]
    return render(request, "records/challenge_report.html", {
        "challenge": ch,
        "progress": progress,
        "notes": notes,
        "finished": ch.is_finished(),
        "printed_at": timezone.localtime(),
        "source": SOURCE_722,
        "ref_source": SOURCE_REFERENCE_VALUE,
    })
