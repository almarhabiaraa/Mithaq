from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    
    path('', views.notification_list_page, name='list'),
    path('api/', views.NotificationListView.as_view(), name='api_list'),
    path('<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='mark_read'),
    path('read-all/', views.NotificationMarkAllReadView.as_view(), name='mark_all_read'),
    path('unread-count/', views.UnreadCountView.as_view(), name='unread_count'),
]