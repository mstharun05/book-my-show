from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User, Permission
from django.core import mail
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from bookings.models import Theater, Screen, Seat, Show
from bookings.services import reserve_seats
from movies.models import Movie
from payments.models import Payment
from payments.services import apply_payment
from .models import TicketDelivery
from .tasks import deliver_ticket, dispatch_pending
from .pdf import verification_token


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TicketTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('viewer', email='viewer@example.com')
        movie = Movie.objects.create(title='Interstellar', duration=169, release_date=timezone.localdate())
        theater = Theater.objects.create(name='Grand Cinema', city='Hyderabad')
        screen = Screen.objects.create(theater=theater, name='Screen 1')
        seat = Seat.objects.create(screen=screen, seat_number='A1')
        show = Show.objects.create(movie=movie, screen=screen, ticket_price=200, show_time=timezone.now()+timedelta(days=1))
        self.booking = reserve_seats(self.user, show.pk, [seat.pk])
        Payment.objects.create(booking=self.booking, amount=200, razorpay_order_id='order_ticket')
        self.entity = dict(id='pay_ticket', order_id='order_ticket', status='captured', amount=20000, currency='INR')
        self.client.force_login(self.user)

    def confirm(self):
        apply_payment(self.entity)
        return TicketDelivery.objects.get(booking=self.booking)

    def test_confirmation_only_writes_one_outbox_without_network(self):
        with patch('tickets.tasks.deliver_ticket.delay') as queued, patch('tickets.tasks.EmailMessage.send') as send:
            self.confirm()
            apply_payment(self.entity)
        self.assertEqual(TicketDelivery.objects.count(), 1)
        queued.assert_not_called()
        send.assert_not_called()

    def test_rollback_leaves_no_ticket(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.confirm()
                raise RuntimeError()
        self.assertFalse(TicketDelivery.objects.exists())

    def test_delivery_attachment_and_idempotency(self):
        delivery = self.confirm()
        deliver_ticket(delivery.pk)
        deliver_ticket(delivery.pk)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].attachments[0].content.startswith(b'%PDF'))
        self.assertEqual(mail.outbox[0].to, ['viewer@example.com'])

    def test_failure_retries_then_succeeds(self):
        delivery = self.confirm()
        with patch('tickets.tasks.EmailMessage.send', side_effect=OSError('SMTP unavailable')):
            deliver_ticket(delivery.pk)
        delivery.refresh_from_db()
        self.assertIsNone(delivery.sent_at)
        self.assertEqual(delivery.attempts, 1)
        self.assertGreater(delivery.next_attempt_at, timezone.now())
        TicketDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        with patch('tickets.tasks.deliver_ticket.delay') as delay:
            dispatch_pending()
            delay.assert_called_once_with(delivery.pk)
        deliver_ticket(delivery.pk)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(delivery.attempts, 2)

    def test_download_ownership_payment_and_qr(self):
        url = f'/tickets/download/{self.booking.pk}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.confirm()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        other = User.objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        token = verification_token(self.booking)
        self.assertEqual(self.client.get(f'/tickets/verify/{token}/').status_code, 403)
        other.user_permissions.add(Permission.objects.get(codename='view_booking'))
        self.assertEqual(self.client.get(f'/tickets/verify/{token}/').json()['valid'], True)
        self.assertEqual(self.client.get(f'/tickets/verify/{token}tampered/').status_code, 400)
        Payment.objects.update(status='REFUNDED')
        self.assertEqual(self.client.get(f'/tickets/verify/{token}/').status_code, 404)

    def test_missing_email_preserves_pdf_and_recovers(self):
        self.user.email = ''
        self.user.save()
        delivery = self.confirm()
        deliver_ticket(delivery.pk)
        delivery.refresh_from_db()
        self.assertTrue(delivery.pdf)
        self.assertIsNone(delivery.sent_at)
        self.assertRedirects(self.client.post('/accounts/email/', {'email':'new@example.com'}), '/payments/history/')
        TicketDelivery.objects.update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        deliver_ticket(delivery.pk)
        self.assertEqual(mail.outbox[0].to, ['new@example.com'])
