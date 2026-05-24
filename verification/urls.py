from django.urls import path

from . import views
app_name = 'verification'

urlpatterns = [
    # HTML page — user types the hash from their signed PDF
    path('', views.verify_page, name='verify_page'),

    # JSON API — called by JavaScript in verify.html
    # Accepts: GET ?hash=<64-char-hex>
    # Returns: verification_status + blockchain proof (no PII)
    path('api/verify-contract/', views.VerifyContractAPIView.as_view(), name='verify_contract_api'),
]
