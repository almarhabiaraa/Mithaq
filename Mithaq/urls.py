from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    

    path('api/contracts/', include('contracts.urls')),
    path('api/audit/', include('audit.urls')),
    path("blockchain/", include("blockchain.urls")),
    path("signatures/", include("signatures.urls")),
    
    path("invitations/", include("invitations.urls")),
    path("milestones/", include("milestones.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("notifications/", include("notifications.urls")),
    path("api/payments/", include("payments.urls")),           # (added by ghadi: Moyasar checkout, callback, success/failed pages)
    path("api/subscriptions/", include("subscriptions.urls")), # (added by ghadi: subscription plans, status, upgrade options, and checkout page)
    path("wallet/", include("wallet.urls")),

    # (added by ghadi: public contract verification — no login needed)
    path("verify/",     include("verification.urls")),   # HTML page for humans: /verify/
    path("api/verify/", include("verification.urls")),   # JSON API for JS: /api/verify/<hash>/
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
