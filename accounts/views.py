from django.shortcuts import render, redirect
from django.http import HttpRequest
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError

# (added by ghadi: imports two subscription functions used in sign_up and profile)
from subscriptions.services.subscription_service import assign_free_plan, get_user_subscription
from .models import User


def sign_up(request: HttpRequest):
    form_data = {}
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        national_id = request.POST.get("national_id", "").strip()
        mobile = request.POST.get("mobile", "").strip()
        date_of_birth = request.POST.get("date_of_birth", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        form_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "national_id": national_id,
            "mobile": mobile,
            "date_of_birth": date_of_birth,
        }

        # Guard: all required fields must be present
        if not all([email, first_name, last_name, national_id, mobile, password, confirm_password]):
            messages.error(request, "يرجى تعبئة جميع الحقول المطلوبة", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Validate national_id — 10 digits
        if not national_id.isdigit() or len(national_id) != 10:
            messages.error(request, "رقم الهوية يجب أن يكون 10 أرقام", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Validate mobile — starts with 05
        if not mobile.isdigit() or len(mobile) != 10 or not mobile.startswith("05"):
            messages.error(request, "رقم الجوال غير صحيح — يجب أن يبدأ بـ 05 ويكون 10 أرقام", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Validate password length
        if len(password) < 8:
            messages.error(request, "كلمة المرور يجب أن تكون 8 أحرف على الأقل", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Validate password match
        if password != confirm_password:
            messages.error(request, "كلمة المرور غير متطابقة", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "البريد الإلكتروني مستخدم مسبقاً", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Check if national_id already exists
        if User.objects.filter(national_id=national_id).exists():
            messages.error(request, "رقم الهوية مستخدم مسبقاً", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        # Create new user — try/except catches race-condition IntegrityErrors
        # that slip past the pre-checks above when two requests arrive simultaneously.
        try:
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
                assign_free_plan(user)  # (added by ghadi)
        except IntegrityError as e:
            err = str(e)
            if "national_id" in err:
                messages.error(request, "رقم الهوية مستخدم مسبقاً", "alert-danger")
            elif "email" in err:
                messages.error(request, "البريد الإلكتروني مستخدم مسبقاً", "alert-danger")
            else:
                messages.error(request, "حدث خطأ أثناء إنشاء الحساب، يرجى المحاولة مرة أخرى", "alert-danger")
            return render(request, "accounts/signup.html", {"form_data": form_data})

        login(request, user)
        messages.success(request, "تم إنشاء الحساب بنجاح", "alert-success")
        return redirect("accounts:profile")

    return render(request, "accounts/signup.html", {"form_data": form_data})


def sign_in(request: HttpRequest):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Check if user exists first
        if not User.objects.filter(email=email).exists():
            messages.error(request, "لا يوجد حساب مرتبط بهذا البريد الإلكتروني", "alert-danger")
            return render(request, "accounts/signin.html")

        # Authenticate
        user = authenticate(request, email=email, password=password)

        if user:
            login(request, user)
            messages.success(request, "مرحباً بك!", "alert-success")
            next_url = request.GET.get("next")
            return redirect(next_url if next_url else "accounts:profile")
        else:
            messages.error(request, "كلمة المرور غير صحيحة", "alert-danger")

    return render(request, "accounts/signin.html")


def log_out(request: HttpRequest):
    logout(request)
    messages.success(request, "تم تسجيل الخروج بنجاح", "alert-warning")
    return redirect("accounts:sign_in")


@login_required(login_url="accounts:sign_in")
def profile(request: HttpRequest):
    user = request.user

    if request.method == "POST":
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.bio = request.POST.get("bio", user.bio)
        user.date_of_birth = request.POST.get("date_of_birth") or user.date_of_birth
        user.mobile = request.POST.get("mobile", user.mobile)

        if request.FILES.get("avatar"):
            user.avatar = request.FILES["avatar"]

        user.save()
        messages.success(request, "تم تحديث المعلومات بنجاح", "alert-success")
        return redirect("accounts:profile")

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

        if not request.user.check_password(current_password):
            messages.error(request, "كلمة المرور الحالية غير صحيحة", "alert-danger")
            return render(request, "accounts/change_password.html")

        if new_password != confirm_password:
            messages.error(request, "كلمة المرور الجديدة غير متطابقة", "alert-danger")
            return render(request, "accounts/change_password.html")

        if current_password == new_password:
            messages.error(request, "كلمة المرور الجديدة يجب أن تختلف عن الحالية", "alert-danger")
            return render(request, "accounts/change_password.html")

        request.user.set_password(new_password)
        request.user.save()
        login(request, request.user)
        messages.success(request, "تم تغيير كلمة المرور بنجاح", "alert-success")
        return redirect("accounts:settings")

    return render(request, "accounts/change_password.html")


@login_required(login_url="accounts:sign_in")
def privacy(request: HttpRequest):
    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "تم حذف حسابك بنجاح", "alert-success")
        return redirect("accounts:sign_in")

    return render(request, "accounts/privacy.html")


@login_required(login_url="accounts:sign_in")
def help_support(request):
    return render(request, "accounts/help_support.html")


# ── Face Verification Views ───────────────────────────────────────────────────

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.services.face_verification_service import mark_user_verified

@login_required(login_url='accounts:sign_in')
def verify_identity_page(request):
    """
    GET /accounts/verify-identity/
    Renders the face verification page.
    Shows success state if already verified.
    """
    return render(request, 'accounts/verify_identity.html', {
        'is_verified': request.user.is_verified,
        'verified_at': request.user.verified_at,
    })


@require_POST
@login_required(login_url='accounts:sign_in')
def confirm_verification(request):
    """
    POST /accounts/verify-identity/confirm/
    Called by JavaScript after face-api.js confirms a match.
    Marks the user as verified in the database.
    """
    result = mark_user_verified(request.user)

    if result:
        return JsonResponse({
            'success': True,
            'message': 'تم التحقق من هويتك بنجاح',
            'verified_at': request.user.verified_at.isoformat(),
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'تم التحقق من هويتك مسبقاً',
        })