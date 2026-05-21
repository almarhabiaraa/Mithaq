from django.urls import path
from audit.views import AuditTimelineView

app_name = "audit"
urlpatterns = [
    path('<uuid:pk>/audit/', AuditTimelineView.as_view()),
]