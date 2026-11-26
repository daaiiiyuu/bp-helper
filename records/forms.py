"""
血壓紀錄表單

722 原則「每次量 2 遍取平均」：
  使用者輸入第 1 遍（必填）與第 2 遍（建議填），
  表單自動把兩遍取平均後存成一筆紀錄。

量測前檢查清單：每一項都要勾選才能儲存（網站操作流程 ⑤）。
"""
from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.utils import timezone

from education.content import CHECKLIST_ITEMS

from .models import BloodPressureRecord

# 與 Model 的 validators 一致，僅用來擋打錯字
RANGES = {"systolic": (50, 260), "diastolic": (30, 160), "pulse": (30, 220)}
LABELS = {"systolic": "收縮壓", "diastolic": "舒張壓", "pulse": "心跳"}


def _num_field(kind, required):
    lo, hi = RANGES[kind]
    return forms.IntegerField(
        label=LABELS[kind], required=required, min_value=lo, max_value=hi,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": "—"}),
        error_messages={
            "min_value": f"{LABELS[kind]}不太可能低於 {lo}，請再確認一下",
            "max_value": f"{LABELS[kind]}不太可能高於 {hi}，請再確認一下",
            "required": f"請輸入{LABELS[kind]}",
        },
    )


def _avg(a, b):
    """兩遍取平均，四捨五入到整數"""
    return int((Decimal(a + b) / 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def guess_period(dt):
    """依時間猜早上／晚上，只是預設值，使用者可以自己改"""
    h = timezone.localtime(dt).hour
    if 4 <= h < 12:
        return BloodPressureRecord.Period.MORNING
    if h >= 18 or h < 4:
        return BloodPressureRecord.Period.EVENING
    return BloodPressureRecord.Period.OTHER


class RecordForm(forms.Form):
    # 預設不勾 → 量測時間自動用「按下儲存的那一刻」；勾了才需要自己填時間（補登用）
    backfill = forms.BooleanField(label="補登其他時間的紀錄", required=False)
    measured_at = forms.DateTimeField(
        label="量測日期與時間", required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )
    period = forms.ChoiceField(label="量測時段", choices=BloodPressureRecord.Period.choices,
                               widget=forms.RadioSelect)

    systolic_1 = _num_field("systolic", True)
    diastolic_1 = _num_field("diastolic", True)
    pulse_1 = _num_field("pulse", True)
    systolic_2 = _num_field("systolic", False)
    diastolic_2 = _num_field("diastolic", False)
    pulse_2 = _num_field("pulse", False)

    note = forms.CharField(label="備註（選填）", max_length=200, required=False,
                           widget=forms.TextInput(attrs={"placeholder": "例如：昨晚睡不好"}))

    def __init__(self, *args, require_checklist=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.checklist_keys = []
        if require_checklist:
            for key, label in CHECKLIST_ITEMS:
                name = f"check_{key}"
                self.fields[name] = forms.BooleanField(
                    label=label, required=True,
                    error_messages={"required": "請先完成這一項檢查"},
                )
                self.checklist_keys.append(name)

    # 給 template 分區塊顯示
    def checklist_fields(self):
        return [self[k] for k in self.checklist_keys]

    def reading_rows(self):
        return [
            ("第 1 遍", self["systolic_1"], self["diastolic_1"], self["pulse_1"]),
            ("第 2 遍", self["systolic_2"], self["diastolic_2"], self["pulse_2"]),
        ]

    def clean(self):
        data = super().clean()

        # ---- 量測時間：沒勾補登就自動帶入現在時間 ----
        if not data.get("backfill"):
            data["measured_at"] = timezone.now().replace(second=0, microsecond=0)
        elif data.get("measured_at") is None:
            if "measured_at" not in self.errors:
                self.add_error("measured_at", "補登紀錄請填寫量測日期與時間")
        elif data["measured_at"] > timezone.now() + timezone.timedelta(minutes=5):
            self.add_error("measured_at", "量測時間不能是未來的時間")

        for n in (1, 2):
            s, d = data.get(f"systolic_{n}"), data.get(f"diastolic_{n}")
            if s is not None and d is not None and s <= d:
                self.add_error(f"systolic_{n}", "收縮壓（上面的數字）應該比舒張壓（下面的數字）大")

        second = [data.get(f"{k}_2") for k in ("systolic", "diastolic", "pulse")]
        filled = [v is not None for v in second]
        if any(filled) and not all(filled):
            raise forms.ValidationError("第 2 遍請三個數值都填，或是三個都留空")
        self.has_second = all(filled)
        return data

    def to_record_values(self):
        """把表單資料轉成要存進 Model 的欄位（兩遍取平均）"""
        d = self.cleaned_data
        values = {}
        for k in ("systolic", "diastolic", "pulse"):
            values[k] = _avg(d[f"{k}_1"], d[f"{k}_2"]) if self.has_second else d[f"{k}_1"]
        values.update(
            measured_at=d["measured_at"],
            period=d["period"],
            readings_count=2 if self.has_second else 1,
            # 能走到這裡代表：表單內清單全勾，或一小時內已在檢查清單頁完成
            checklist_done=True,
            note=d.get("note", ""),
        )
        return values


class RecordEditForm(forms.ModelForm):
    """修改既有紀錄：直接改平均後的數值，不再要求檢查清單"""

    class Meta:
        model = BloodPressureRecord
        fields = ["measured_at", "period", "systolic", "diastolic", "pulse", "note"]
        widgets = {
            "measured_at": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                               format="%Y-%m-%dT%H:%M"),
            "period": forms.RadioSelect,
        }

    def clean(self):
        data = super().clean()
        s, d = data.get("systolic"), data.get("diastolic")
        if s is not None and d is not None and s <= d:
            self.add_error("systolic", "收縮壓應該比舒張壓大")
        return data


class DateFilterForm(forms.Form):
    """依日期篩選紀錄"""
    start = forms.DateField(label="開始日期", required=False,
                            widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="結束日期", required=False,
                          widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("開始日期不能晚於結束日期")
        return data
