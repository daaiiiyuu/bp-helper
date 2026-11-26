"""
產生 722 週的行事曆檔（.ics，iCalendar RFC 5545）

手機點一下就能把 14 次量測提醒加進內建行事曆，時間到手機自己會響，
不需要伺服器排程或推播服務。

格式重點：
- 時間一律換成 UTC（結尾加 Z），任何手機時區都能正確顯示
- 每行用 CRLF 換行，超過 75 bytes 要折行（中文一個字 3 bytes，要用 bytes 計算）
- 文字中的 , ; \\ 與換行要跳脫
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from education.content import SOURCE_722

LOCAL_TZ = ZoneInfo(settings.TIME_ZONE)
EVENT_MINUTES = 15

PREP_TEXT = ("量測前半小時避免抽菸、進食、洗澡、運動、喝酒、喝咖啡或茶；"
             "先上廁所；靜坐休息 5 分鐘；量 2 遍取平均。")


def _escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line):
    """RFC 5545 §3.1：每行最多 75 bytes，續行以一個空白開頭；不能把一個中文字切開"""
    out, current = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74  # 續行開頭的空白占 1 byte
        if len(current) + len(b) > limit:
            out.append(current)
            current = b""
        current += b
    out.append(current)
    return b"\r\n ".join(out).decode("utf-8")


def _utc(dt):
    return dt.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _event(uid, start_local, summary, description, url, stamp):
    end_local = start_local + timedelta(minutes=EVENT_MINUTES)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_utc(start_local)}",
        f"DTEND:{_utc(end_local)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"URL:{url}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape(summary)}",
        "TRIGGER:PT0M",  # 時間到就提醒
        "END:VALARM",
        "END:VEVENT",
    ]
    return lines


def build_ics(challenge, record_url, host="bp-helper"):
    """
    challenge：Challenge722
    record_url：「輸入血壓」頁的完整網址（放進提醒內容，點了直接開網站）
    回傳 .ics 文字內容；已經過去的時段不會放進去
    """
    now = timezone.now()
    stamp = _utc(now)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//bp-helper//722//ZH-TW",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:722 量血壓",
    ]

    slots = (("morning", "早上・起床後", challenge.morning_time),
             ("evening", "晚上・睡前", challenge.evening_time))
    count = 0
    for i in range(challenge.DAYS):
        d = challenge.start_date + timedelta(days=i)
        for key, label, t in slots:
            start = datetime.combine(d, t, tzinfo=LOCAL_TZ)
            if start + timedelta(minutes=EVENT_MINUTES) < now:
                continue  # 已經過去的時段不加
            summary = f"🩺 量血壓（{label}）第 {i + 1} 天"
            desc = f"722 原則第 {i + 1}/7 天。{PREP_TEXT}\n量完記錄：{record_url}"
            lines += _event(f"722-{challenge.pk}-{d:%Y%m%d}-{key}@{host}",
                            start, summary, desc, record_url, stamp)
            count += 1

    # 國健署建議每年至少做一次 722：一年後提醒
    next_year = datetime.combine(challenge.start_date + timedelta(days=365),
                                 challenge.morning_time, tzinfo=LOCAL_TZ)
    lines += _event(
        f"722-{challenge.pk}-next-year@{host}", next_year,
        "🩺 今年的 722 居家量血壓",
        f"國健署建議 18 歲以上民眾每年至少用 722 原則在家量一次血壓。"
        f"打開網站開始新的 722 週：{record_url}\n資料來源：{SOURCE_722['url']}",
        record_url, stamp)

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n", count
