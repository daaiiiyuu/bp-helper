"""
records app 的 View：血壓紀錄新增、查詢（依日期篩選）、趨勢圖、修改、刪除、匯出 CSV

所有 View 都加 @login_required，而且查詢一律 filter(user=request.user)，
確保每個人只看得到、改得到自己的紀錄。
"""
import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from education.content import SOURCE_REFERENCE_VALUE
from education.views import checklist_recently_done

from .charts import REF_DIA, REF_SYS, build_trend_chart
from .forms import DateFilterForm, RecordEditForm, RecordForm, guess_period
from .models import BloodPressureRecord

Period = BloodPressureRecord.Period


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


def _progress_722(user):
    """
    最近 7 天（含今天）的 722 進度：
    每天早上、晚上各一格，共 14 格；並計算這 7 天的平均血壓。
    """
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    recent = BloodPressureRecord.objects.filter(
        user=user, measured_at__date__gte=days[0], measured_at__date__lte=today)

    done = set()
    for r in recent:
        d = timezone.localtime(r.measured_at).date()
        done.add((d, r.period))

    weekday = "一二三四五六日"
    rows = [{
        "date": d,
        "label": f"{d.month}/{d.day}",
        "weekday": weekday[d.weekday()],
        "is_today": d == today,
        "morning": (d, Period.MORNING) in done,
        "evening": (d, Period.EVENING) in done,
    } for d in days]
    sessions = sum(r["morning"] + r["evening"] for r in rows)

    avg = recent.filter(period__in=[Period.MORNING, Period.EVENING]).aggregate(
        sys=Avg("systolic"), dia=Avg("diastolic"), pulse=Avg("pulse"))
    has_avg = avg["sys"] is not None
    return {
        "days": rows,
        "sessions": sessions,
        "total_sessions": 14,
        "percent": round(sessions / 14 * 100),
        "has_avg": has_avg,
        "avg_sys": round(avg["sys"]) if has_avg else None,
        "avg_dia": round(avg["dia"]) if has_avg else None,
        "avg_pulse": round(avg["pulse"]) if has_avg else None,
        "above_ref": has_avg and (avg["sys"] > REF_SYS or avg["dia"] > REF_DIA),
        "ref_sys": REF_SYS, "ref_dia": REF_DIA,
    }


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
        "progress": _progress_722(request.user),
        "ref_source": SOURCE_REFERENCE_VALUE,
    })


# ------------------------------------------------------------------
# ⑤ 輸入血壓：先完成檢查清單，再填數值
# ------------------------------------------------------------------
@login_required
def record_create(request):
    checklist_done = checklist_recently_done(request)
    if request.method == "POST":
        form = RecordForm(request.POST, require_checklist=not checklist_done)
        if form.is_valid():
            record = BloodPressureRecord.objects.create(user=request.user, **form.to_record_values())
            msg = f"已儲存：{record.systolic}/{record.diastolic} mmHg，心跳 {record.pulse}"
            if record.readings_count == 2:
                msg += "（兩遍平均）"
            messages.success(request, msg)
            return redirect("records:list")
    else:
        now = timezone.localtime()
        form = RecordForm(
            require_checklist=not checklist_done,
            initial={"measured_at": now.strftime("%Y-%m-%dT%H:%M"), "period": guess_period(now)},
        )
    return render(request, "records/record_form.html", {
        "form": form,
        "checklist_done": checklist_done,
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
    resp.write("﻿")  # BOM：讓 Excel 開啟時中文不會變亂碼
    w = csv.writer(resp)
    w.writerow(["量測日期", "時間", "時段", "收縮壓(mmHg)", "舒張壓(mmHg)",
                "心跳(次/分)", "量測遍數", "已完成量測前檢查", "備註"])
    for r in qs.order_by("measured_at"):
        t = timezone.localtime(r.measured_at)
        w.writerow([t.strftime("%Y-%m-%d"), t.strftime("%H:%M"), r.get_period_display(),
                    r.systolic, r.diastolic, r.pulse, r.readings_count,
                    "是" if r.checklist_done else "否", r.note])
    return resp
