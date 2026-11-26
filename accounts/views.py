from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme


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
