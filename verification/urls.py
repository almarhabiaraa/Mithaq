from django.urls import path

from . import views

app_name = "verification"

urlpatterns = [
    path('', views.verify_page, name='verify-page'),
    path("verify/", views.verify_page, name="verify_page"),
    path("api/verify-contract/", views.verify_contract_api, name="verify_contract_api"),
]

