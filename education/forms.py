from django import forms

from .content import CHECKLIST_ITEMS


class ChecklistForm(forms.Form):
    """
    量測前檢查清單。欄位依 content.CHECKLIST_ITEMS 動態產生，
    每一項都必須勾選（required=True）才算完成。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label in CHECKLIST_ITEMS:
            self.fields[key] = forms.BooleanField(
                label=label, required=True,
                error_messages={"required": "這一項還沒確認喔"},
            )
