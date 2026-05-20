from django.urls import path
from contracts.views import (
    ContractListCreateView, ContractDetailView,
    ApproveView, SignView, CancelView,
    VersionListView, VersionDetailView,
    contract_create_view, contract_detail_view,
    version_history_view, audit_timeline_view,
)
from audit.views import AuditTimelineView

urlpatterns = [
    # ── Template URLs ──────────────────────────
    path('create/', contract_create_view),
    path('<uuid:pk>/detail/', contract_detail_view), 
    path('<uuid:pk>/versions/history/', version_history_view),
    path('<uuid:pk>/audit/timeline/', audit_timeline_view),

    # ── API URLs ───────────────────────────────
    path('',ContractListCreateView.as_view(),name='contract-list_create'),
    path('<uuid:pk>/',ContractDetailView.as_view(),name='contract-api_detail'),
    path('<uuid:pk>/versions/',VersionListView.as_view(),name='version_list'),
    path('<uuid:pk>/versions/<int:version_number>/',VersionDetailView.as_view(),name='version_detail'),
    path('<uuid:pk>/approve/',ApproveView.as_view(),name='contract_approve'),
    path('<uuid:pk>/sign/',SignView.as_view(),name='contract_sign'),
    path('<uuid:pk>/cancel/',CancelView.as_view(),name='contract_cancel'),
    path('<uuid:pk>/audit/',AuditTimelineView.as_view(),name='contract_audit'),
]


