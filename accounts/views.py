from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import DeleteAccountForm, RememberMeLoginForm


class RememberMeLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = RememberMeLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember_me"):
            # 沒勾「記住我」：關掉瀏覽器就登出（適合用別人的手機或公用電腦）
            self.request.session.set_expiry(0)
        return response


def signup(request):
    """註冊後直接登入，並帶到「我的紀錄」"""
    if request.user.is_authenticated:
        return redirect("records:list")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"歡迎，{user.username}！現在可以開始記錄血壓了。")
        nxt = request.GET.get("next", "")
        # 只允許導回本站網址，避免 open redirect
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            return redirect(nxt)
        return redirect("records:list")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def settings_page(request):
    return render(request, "accounts/settings.html", {
        "record_count": request.user.bp_records.count(),
    })


@login_required
def password_change(request):
    """我們沒有收 Email，無法寄信重設密碼，所以至少要能自己改密碼"""
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # 改完密碼不要被登出
        messages.success(request, "密碼已更新")
        return redirect("accounts:settings")
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def delete_account(request):
    """刪除帳號：血壓紀錄、722 週挑戰會一起刪除（ForeignKey on_delete=CASCADE）"""
    form = DeleteAccountForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "帳號與所有血壓紀錄已刪除。")
        return redirect("education:home")
    return render(request, "accounts/delete_account.html", {
        "form": form, "record_count": request.user.bp_records.count(),
    })
