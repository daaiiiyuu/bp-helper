"""
血壓折線趨勢圖：在 Python 端算好座標，直接輸出 SVG。

不用 Chart.js 等外部套件 → 沒有網路也能顯示、手機載入快，
也方便期末展示時解釋「資料怎麼變成圖」。
"""
from django.utils import timezone

WIDTH, HEIGHT = 640, 300
PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 16, 44

# 國健署：健康成人 7 天平均參考值 120/80 mmHg（見 education.content.SOURCE_REFERENCE_VALUE）
REF_SYS, REF_DIA = 120, 80


def build_trend_chart(records, max_points=30):
    """
    records：依時間「新到舊」的 BloodPressureRecord 清單
    回傳 template 需要的所有座標；少於 2 筆時回傳 None
    """
    pts = list(records[:max_points])[::-1]  # 取最近 N 筆，轉成舊到新
    if len(pts) < 2:
        return None

    values = [r.systolic for r in pts] + [r.diastolic for r in pts] + [REF_SYS, REF_DIA]
    y_min = (min(values) - 10) // 10 * 10
    y_max = (max(values) + 19) // 10 * 10

    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B

    def x(i):
        return PAD_L + plot_w * i / (len(pts) - 1)

    def y(v):
        return PAD_T + plot_h * (y_max - v) / (y_max - y_min)

    def series(attr):
        return [
            {"x": round(x(i), 1), "y": round(y(getattr(r, attr)), 1),
             "v": getattr(r, attr), "label": timezone.localtime(r.measured_at).strftime("%m/%d %H:%M")}
            for i, r in enumerate(pts)
        ]

    sys_pts, dia_pts = series("systolic"), series("diastolic")

    # Y 軸格線：每 20 mmHg 一條
    step = 20
    first = (y_min + step - 1) // step * step
    grid = [{"v": v, "y": round(y(v), 1)} for v in range(first, y_max + 1, step)]

    # X 軸日期標籤：最多標約 5 個，避免手機上擠在一起
    every = max(1, -(-len(pts) // 5))  # 最多約 5 個標籤
    x_labels = []
    for i, r in enumerate(pts):
        if i % every == 0 or i == len(pts) - 1:
            lx = round(x(i), 1)
            if x_labels and lx - x_labels[-1]["x"] < 70:  # 太擠就把前一個換成最後一個
                x_labels.pop()
            x_labels.append({"x": lx, "text": timezone.localtime(r.measured_at).strftime("%m/%d")})

    # 第一個標籤靠左對齊、最後一個靠右對齊，避免被裁掉
    for j, lbl in enumerate(x_labels):
        lbl["anchor"] = "start" if j == 0 else ("end" if j == len(x_labels) - 1 else "middle")
    if len(x_labels) == 1:
        x_labels[0]["anchor"] = "middle"

    return {
        "width": WIDTH, "height": HEIGHT,
        "left": PAD_L, "right": WIDTH - PAD_R, "bottom": HEIGHT - PAD_B,
        "sys_points": sys_pts, "dia_points": dia_pts,
        "sys_path": " ".join(f"{p['x']},{p['y']}" for p in sys_pts),
        "dia_path": " ".join(f"{p['x']},{p['y']}" for p in dia_pts),
        "grid": grid, "x_labels": x_labels,
        "ref_sys_y": round(y(REF_SYS), 1), "ref_dia_y": round(y(REF_DIA), 1),
        "ref_sys": REF_SYS, "ref_dia": REF_DIA,
        "count": len(pts),
    }
