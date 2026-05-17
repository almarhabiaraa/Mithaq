from django.urls import path

from . import views

urlpatterns = [
    # HTML page — for humans visiting /verify/
    path('', views.VerifyPageView.as_view(), name='verify-page'),

    # JSON API — called by JavaScript in verify.html (and external integrations)
    # Mounted at both /verify/<hash>/ and /api/verify/<hash>/
    path('<str:hash_hex>/', views.PublicVerifyAPIView.as_view(), name='verify-api'),
]
