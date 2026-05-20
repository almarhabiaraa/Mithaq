from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.sign_up, name="sign_up"),
    path("signin/", views.sign_in, name="sign_in"),
    path("logout/", views.log_out, name="log_out"),
    path("profile/", views.profile, name="profile"),
    path("settings/", views.settings, name="settings"),
    path("change-password/", views.change_password, name="change_password"),
    path("privacy/", views.privacy, name="privacy"),
    path("help/", views.help_support, name="help_support"),
    path('verify-identity/', views.verify_identity_page, name='verify_identity'), # (added by ghadi: page that runs face verification in the browser using face-api.js)
    path('verify-identity/confirm/', views.confirm_verification, name='confirm_verification'), # (added by ghadi: API endpoint that the browser calls after successful face verification to mark the user as verified)

]
