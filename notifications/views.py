from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Notification


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all notifications for the current user"""
        notifications = Notification.objects.filter(
            user=request.user
        ).select_related('contract')

        data = [
            {
                'id': n.id,
                'type': n.notification_type,
                'message': n.get_message(),
                'contract_id': str(n.contract.id) if n.contract else None,
                'contract_title': n.contract.title_ar if n.contract else None,
                'is_read': n.is_read,
                'created_at': n.created_at,
            }
            for n in notifications
        ]

        return Response(data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Mark a single notification as read"""
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.is_read = True
            notification.save()
            return Response({'status': 'marked as read'})
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found'}, status=404)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Mark all notifications as read"""
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)

        return Response({'status': 'all marked as read'})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get unread notifications count"""
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        return Response({'unread_count': count})


@login_required(login_url="accounts:sign_in")
def notification_list_page(request):
    """Render notifications HTML page"""
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related('contract')

    return render(request, 'notifications/list.html', {
        'notifications': notifications,
    })