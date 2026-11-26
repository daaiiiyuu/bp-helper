from django import forms
from django.contrib.auth.forms import AuthenticationForm


class RememberMeLoginForm(AuthenticationForm):
    """登入表單加上「記住我」：預設勾選，長輩不用常常重新登入"""
    remember_me = forms.BooleanField(label="記住我（90 天內不用重新登入）",
                                     required=False, initial=True)


class DeleteAccountForm(forms.Form):
    """刪除帳號前再輸入一次密碼，避免誤刪"""
    password = forms.CharField(label="請輸入密碼確認", widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        pw = self.cleaned_data["password"]
        if not self.user.check_password(pw):
            raise forms.ValidationError("密碼不正確")
        return pw
