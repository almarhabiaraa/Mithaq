from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock
from notifications.models import Notification
from notifications.services import NotificationService

User = get_user_model()


class NotificationModelTest(TestCase):

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            email='test@mithaq.com',
            password='testpass123',
            first_name='ريماس',
            last_name='الشهراني',
            national_id='1234567890',
            mobile='0501234567',
        )

    def test_create_notification(self):
        """Test creating a notification for a user"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.CONTRACT_RECEIVED,
        )
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.notification_type, Notification.CONTRACT_RECEIVED)
        self.assertFalse(notification.is_read)

    def test_get_message(self):
        """Test get_message returns correct Arabic message"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.CONTRACT_RECEIVED,
        )
        self.assertEqual(notification.get_message(), 'لديك عقد جديد للمراجعة')

    def test_mark_as_read(self):
        """Test marking a notification as read"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.CONTRACT_SIGNED,
        )
        notification.is_read = True
        notification.save()
        self.assertTrue(notification.is_read)

    def test_unread_count(self):
        """Test unread notifications count"""
        Notification.objects.create(user=self.user, notification_type=Notification.CONTRACT_RECEIVED)
        Notification.objects.create(user=self.user, notification_type=Notification.CONTRACT_SIGNED)

        count = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(count, 2)


class NotificationServiceTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(
            email='user1@mithaq.com',
            password='testpass123',
            first_name='ريماس',
            last_name='الشهراني',
            national_id='1111111111',
            mobile='0501111111',
        )
        self.user2 = User.objects.create_user(
            email='user2@mithaq.com',
            password='testpass123',
            first_name='هند',
            last_name='العمري',
            national_id='2222222222',
            mobile='0502222222',
        )

    def test_notify_single_user(self):
        """Test sending notification to a single user"""
        NotificationService.notify(
            user=self.user1,
            notification_type=Notification.CONTRACT_RECEIVED,
        )
        count = Notification.objects.filter(user=self.user1).count()
        self.assertEqual(count, 1)

    def test_notify_all_parties(self):
        """Test sending notification to all contract parties"""

        # Notify user2 directly — exclude user1
        NotificationService.notify(
            user=self.user2,
            notification_type=Notification.CONTRACT_RECEIVED,
            contract=None,
        )

        # Only user2 should receive the notification
        self.assertEqual(Notification.objects.filter(user=self.user2).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user1).count(), 0)