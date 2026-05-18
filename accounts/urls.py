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

]
