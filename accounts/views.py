from django.shortcuts import render, redirect
from django.http import HttpRequest
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

# (added by ghadi: imports two subscription functions used in sign_up and profile)
#   assign_free_plan    → gives every new user the Free plan (1 contract limit)
#   get_user_subscription → fetches the active subscription to show on the profile page
from subscriptions.services.subscription_service import assign_free_plan, get_user_subscription
from .models import User


def sign_up(request: HttpRequest):
    if request.method == "POST":
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        national_id = request.POST.get("national_id")
        mobile = request.POST.get("mobile")
        date_of_birth = request.POST.get("date_of_birth")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Validate password match
        if password != confirm_password:
            messages.error(request, "كلمة المرور غير متطابقة", "alert-danger")
            return render(request, "accounts/signup.html")

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "البريد الإلكتروني مستخدم مسبقاً", "alert-danger")
            return render(request, "accounts/signup.html")

        # Check if national_id already exists
        if User.objects.filter(national_id=national_id).exists():
            messages.error(request, "رقم الهوية مستخدم مسبقاً", "alert-danger")
            return render(request, "accounts/signup.html")

        # Create new user
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                national_id=national_id,
                mobile=mobile,
                date_of_birth=date_of_birth or None,
            )

        assign_free_plan(user)  # (added by ghadi: auto-assigns the Free plan to every new user on registration)
        login(request, user)
        messages.success(request, "تم إنشاء الحساب بنجاح", "alert-success")
        return redirect("accounts:profile")

    return render(request, "accounts/signup.html")


def sign_in(request: HttpRequest):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Authenticate user
        user = authenticate(request, email=email, password=password)

        if user:
            login(request, user)
            messages.success(request, "مرحباً بك!", "alert-success")
            next_url = request.GET.get("next")
            return redirect(next_url if next_url else "accounts:profile")
        else:
            messages.error(request, "البريد الإلكتروني أو كلمة المرور غير صحيحة", "alert-danger")

    return render(request, "accounts/signin.html")


def log_out(request: HttpRequest):
    logout(request)
    messages.success(request, "تم تسجيل الخروج بنجاح", "alert-warning")
    return redirect("accounts:sign_in")


@login_required(login_url="accounts:sign_in")
def profile(request: HttpRequest):
    user = request.user

    if request.method == "POST":
        # Update personal info
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.bio = request.POST.get("bio", user.bio)
        user.date_of_birth = request.POST.get("date_of_birth") or user.date_of_birth
        user.mobile = request.POST.get("mobile", user.mobile)

        # Update avatar if uploaded
        if request.FILES.get("avatar"):
            user.avatar = request.FILES["avatar"]

        user.save()
        messages.success(request, "تم تحديث المعلومات بنجاح", "alert-success")
        return redirect("accounts:profile")

    # (added by ghadi: fetch the user's active subscription so the profile page
    #  can display plan name, status, contracts used, and expiry date)
    sub = get_user_subscription(user)
    return render(request, "accounts/profile.html", {"user": user, "subscription": sub})

@login_required(login_url="accounts:sign_in")
def settings(request):
    return render(request, "accounts/settings.html", {"user": request.user})

@login_required(login_url="accounts:sign_in")
def change_password(request: HttpRequest):
    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, "كلمة المرور الحالية غير صحيحة", "alert-danger")
            return render(request, "accounts/change_password.html")

        # Validate new password match
        if new_password != confirm_password:
            messages.error(request, "كلمة المرور الجديدة غير متطابقة", "alert-danger")
            return render(request, "accounts/change_password.html")

        # Validate new password is different
        if current_password == new_password:
            messages.error(request, "كلمة المرور الجديدة يجب أن تختلف عن الحالية", "alert-danger")
            return render(request, "accounts/change_password.html")

        # Update password
        request.user.set_password(new_password)
        request.user.save()

        # Keep user logged in after password change
        login(request, request.user)

        messages.success(request, "تم تغيير كلمة المرور بنجاح", "alert-success")
        return redirect("accounts:settings")

    return render(request, "accounts/change_password.html")

@login_required(login_url="accounts:sign_in")
def privacy(request: HttpRequest):
    if request.method == "POST":
        # Delete account permanently
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "تم حذف حسابك بنجاح", "alert-success")
        return redirect("accounts:sign_in")

    return render(request, "accounts/privacy.html")

@login_required(login_url="accounts:sign_in")
def help_support(request):
    return render(request, "accounts/help_support.html")