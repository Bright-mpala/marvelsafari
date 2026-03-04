from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import NewsletterCampaignForm, NewsletterSubscriberForm
from .models import NewsletterCampaign, NewsletterSubscriber


UNSUBSCRIBE_SALT = 'newsletter-unsubscribe'


def subscribe(request):
    if request.method == 'POST':
        form = NewsletterSubscriberForm(request.POST)
        if form.is_valid():
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=form.cleaned_data['email'],
                defaults={'is_active': True},
            )
            if not created and not subscriber.is_active:
                subscriber.is_active = True
                subscriber.save(update_fields=['is_active'])

            try:
                send_mail(
                    subject='Subscription confirmed',
                    message='Thanks for subscribing to Marvel Safari updates. You will receive travel news and offers in real time.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscriber.email],
                    fail_silently=True,
                )
            except Exception:
                pass

            messages.success(request, 'You have been subscribed to the newsletter.')
            return redirect('newsletter:subscribe')
    else:
        form = NewsletterSubscriberForm()

    return render(request, 'newsletter/subscribe.html', {'form': form})


@login_required
def campaign_list(request):
    campaigns = NewsletterCampaign.objects.filter(created_by=request.user)
    return render(request, 'newsletter/campaign_list.html', {'campaigns': campaigns})


@login_required
def campaign_create(request):
    if request.method == 'POST':
        form = NewsletterCampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            messages.success(request, 'Campaign saved as draft.')
            return redirect('newsletter:campaign_list')
    else:
        form = NewsletterCampaignForm()

    return render(request, 'newsletter/campaign_form.html', {'form': form})


@login_required
def send_campaign(request, pk):
    campaign = get_object_or_404(NewsletterCampaign, pk=pk, created_by=request.user)
    if campaign.status == NewsletterCampaign.STATUS_SENT:
        messages.info(request, 'Campaign has already been sent.')
        return redirect('newsletter:campaign_list')

    recipient_list = list(
        NewsletterSubscriber.objects.filter(is_active=True).values_list('email', flat=True)
    )
    if not recipient_list:
        messages.error(request, 'No active newsletter subscribers found.')
        return redirect('newsletter:campaign_list')

    connection = get_connection(fail_silently=False)
    email_messages = []

    for recipient in recipient_list:
        token = signing.dumps(recipient, salt=UNSUBSCRIBE_SALT)
        unsubscribe_path = reverse('newsletter:unsubscribe')
        unsubscribe_url = request.build_absolute_uri(f'{unsubscribe_path}?token={token}')

        html_body = render_to_string(
            'newsletter/email_campaign.html',
            {
                'campaign': campaign,
                'unsubscribe_url': unsubscribe_url,
            },
        )
        text_body = f"{campaign.body}\n\nUnsubscribe: {unsubscribe_url}"

        message = EmailMultiAlternatives(
            subject=campaign.subject,
            body=text_body,
            to=[recipient],
            connection=connection,
        )
        message.attach_alternative(html_body, 'text/html')
        email_messages.append(message)

    sent_count = connection.send_messages(email_messages)

    campaign.status = NewsletterCampaign.STATUS_SENT
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=['status', 'sent_at'])

    messages.success(request, f'Newsletter sent to {sent_count} subscribers.')
    return redirect('newsletter:campaign_list')


def unsubscribe(request):
    token = request.GET.get('token', '')
    if not token:
        messages.error(request, 'Invalid unsubscribe link.')
        return redirect('newsletter:subscribe')

    try:
        email = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * 365 * 5)
    except signing.BadSignature:
        messages.error(request, 'Invalid or expired unsubscribe link.')
        return redirect('newsletter:subscribe')

    updated = NewsletterSubscriber.objects.filter(email=email, is_active=True).update(is_active=False)
    if updated:
        messages.success(request, 'You have been unsubscribed from the newsletter.')
    else:
        messages.info(request, 'This email is already unsubscribed.')

    return redirect('newsletter:subscribe')
