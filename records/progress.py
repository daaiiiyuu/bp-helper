"""
722 進度計算（「最近 7 天」與「我的 722 週」共用）

一天兩格：早上、晚上；7 天共 14 格。
只有時段選「早上」「晚上」的紀錄會算進格子和平均值，
「其他時間」的紀錄仍會出現在列表與趨勢圖，但不算 722。
"""
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from .charts import REF_DIA, REF_SYS
from .models import BloodPressureRecord

Period = BloodPressureRecord.Period
WEEKDAY = "一二三四五六日"
SLOTS_PER_DAY = 2


def _avg(qs):
    a = qs.aggregate(sys=Avg("systolic"), dia=Avg("diastolic"), pulse=Avg("pulse"))
    if a["sys"] is None:
        return None
    return {"sys": round(a["sys"]), "dia": round(a["dia"]), "pulse": round(a["pulse"]),
            "n": qs.count()}


def compute_progress(user, start_date, days=7):
    """
    回傳 start_date 起連續 days 天的格子狀態、統計數字與平均值。
    每一格：done（有紀錄）/ missed（日期已過但沒量）/ pending（今天或之後）
    """
    today = timezone.localdate()
    dates = [start_date + timedelta(days=i) for i in range(days)]
    end_date = dates[-1]

    records = BloodPressureRecord.objects.filter(
        user=user, period__in=[Period.MORNING, Period.EVENING],
        measured_at__date__gte=start_date, measured_at__date__lte=end_date,
    ).order_by("measured_at")

    by_slot = {}
    for r in records:
        key = (timezone.localtime(r.measured_at).date(), r.period)
        by_slot.setdefault(key, []).append(r)

    def slot(d, period):
        recs = by_slot.get((d, period), [])
        state = "done" if recs else ("missed" if d < today else "pending")
        return {"state": state, "records": recs}

    rows = []
    for i, d in enumerate(dates):
        morning, evening = slot(d, Period.MORNING), slot(d, Period.EVENING)
        rows.append({
            "date": d,
            "day_no": i + 1,
            "label": f"{d.month}/{d.day}",
            "weekday": WEEKDAY[d.weekday()],
            "is_today": d == today,
            "morning": morning,
            "evening": evening,
            "slots": [morning, evening],  # 給報告表格依序輸出
        })

    states = [r[p]["state"] for r in rows for p in ("morning", "evening")]
    done = states.count("done")
    total = days * SLOTS_PER_DAY

    overall = _avg(records)
    return {
        "days": rows,
        "start": start_date,
        "end": end_date,
        "done": done,
        "missed": states.count("missed"),
        "remaining": states.count("pending"),
        "total": total,
        "percent": round(done / total * 100),
        "today_no": (today - start_date).days + 1 if start_date <= today <= end_date else None,
        "avg": overall,
        "avg_morning": _avg(records.filter(period=Period.MORNING)),
        "avg_evening": _avg(records.filter(period=Period.EVENING)),
        "above_ref": bool(overall) and (overall["sys"] > REF_SYS or overall["dia"] > REF_DIA),
        "ref_sys": REF_SYS,
        "ref_dia": REF_DIA,
    }


def rolling_progress(user):
    """沒有進行中的挑戰時，顯示「最近 7 天（含今天）」"""
    return compute_progress(user, timezone.localdate() - timedelta(days=6))
