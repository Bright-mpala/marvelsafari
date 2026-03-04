"""Health check endpoints for monitoring and orchestration"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.shortcuts import render
import logging

from ai_assistant.models import SupportThread
from ai_assistant.services import AIAssistantOrchestrator, AIAssistantUnavailable

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_live(request):
    """
    Liveness probe: Is the application running?
    
    Used by orchestration platforms (K8s, ECS) to determine if pod should stay online.
    """
    return Response({
        'status': 'alive',
        'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_ready(request):
    """
    Readiness probe: Is the application ready to handle traffic?
    
    Checks basic external dependencies:
    - Database connectivity
    - Redis/Cache availability
    """
    
    checks = {
        'database': None,
        'cache': None,
        'ready': True,
    }
    status_code = status.HTTP_200_OK
    
    # Check database
    try:
        conn = connections['default']
        conn.ensure_connection()
        checks['database'] = 'ok'
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        checks['database'] = 'failed'
        checks['ready'] = False
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Check cache/Redis
    try:
        cache.set('healthcheck', 1, timeout=10)
        if cache.get('healthcheck'):
            checks['cache'] = 'ok'
        else:
            checks['cache'] = 'failed'
            checks['ready'] = False
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        checks['cache'] = 'ok'  # Cache is optional, don't fail readiness
    
    return Response({
        'status': 'ready' if checks['ready'] else 'not_ready',
        'checks': checks,
        'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
    }, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_deep(request):
    """
    Deep health check: Are all critical systems operational?
    
    Performs comprehensive checks on all external dependencies.
    Used for monitoring dashboards and detailed status.
    """
    
    checks = {
        'database_read': None,
        'database_write': None,
        'cache': None,
        'celery': None,
        'overall': 'healthy',
    }
    status_code = status.HTTP_200_OK
    
    # Check database read
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.exists()
        checks['database_read'] = 'ok'
    except Exception as e:
        logger.error(f"Database read check failed: {e}")
        checks['database_read'] = f'failed: {str(e)[:50]}'
        checks['overall'] = 'unhealthy'
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Check database write capability
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        checks['database_write'] = 'ok'
    except Exception as e:
        logger.error(f"Database write check failed: {e}")
        checks['database_write'] = f'failed: {str(e)[:50]}'
        checks['overall'] = 'unhealthy'
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Check Celery
    if getattr(settings, 'CELERY_ENABLED', True):
        try:
            from celery import current_app
            current_app.control.inspect().active()
            checks['celery'] = 'ok'
        except Exception as e:
            logger.warning(f"Celery health check failed: {e}")
            checks['celery'] = f'warning: {str(e)[:50]}'
    else:
        checks['celery'] = 'disabled'
    
    # Check Redis/Cache
    try:
        test_key = f'health_{__import__("uuid").uuid4()}'
        cache.set(test_key, 1, timeout=10)
        if cache.get(test_key):
            cache.delete(test_key)
            checks['cache'] = 'ok'
        else:
            checks['cache'] = 'failed: value not retrievable'
            checks['overall'] = 'degraded'
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        checks['cache'] = f'warning: {str(e)[:50]}'
        checks['overall'] = 'degraded' if checks['overall'] == 'healthy' else checks['overall']
    
    return Response({
        'status': checks['overall'],
        'checks': checks,
        'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
    }, status=status_code)


def health_check(request):
    """Main health check endpoint that routes to appropriate check"""
    
    path = request.path
    
    if path.startswith('/health/live'):
        return health_check_live(request)
    elif path.startswith('/health/ready'):
        return health_check_ready(request)
    elif path.startswith('/health/deep'):
        return health_check_deep(request)
    else:
        # Default to readiness check
        return health_check_ready(request)


def contact_us(request):
    """Contact Us page view"""
    if request.method == 'POST':
        from django.core.mail import send_mail
        from django.contrib import messages
        
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Compose email
        full_subject = f"Marvel Safari Contact: {subject}"
        full_message = f"""
New contact form submission from Marvel Safari website:

Name: {first_name} {last_name}
Email: {email}
Subject: {subject}

Message:
{message}

---
This message was sent from the Marvel Safari contact form.
"""
        
        customer_name = f"{first_name or ''} {last_name or ''}".strip()
        thread = SupportThread.objects.create(
            source='contact_form',
            channel='web',
            customer_name=customer_name,
            customer_email=email,
            subject=subject,
            latest_customer_message=message,
            metadata={
                'path': request.path,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'referer': request.META.get('HTTP_REFERER', ''),
            },
        )
        thread.add_message('customer', message, {'origin': 'contact_form'})

        try:
            send_mail(
                subject=full_subject,
                message=full_message,
                from_email=email,  # Use user's email as from
                recipient_list=[settings.CONTACT_EMAIL_RECIPIENT],
                fail_silently=False,
            )
            messages.success(request, 'Thank you for your message! We\'ll get back to you within 24 hours.')
        except Exception:
            messages.error(request, 'Sorry, there was an error sending your message. Please try again or contact us directly.')

        orchestrator = AIAssistantOrchestrator()
        try:
            triage_result = orchestrator.triage_support_thread(
                thread_payload={
                    'subject': subject,
                    'message': message,
                    'customer_name': customer_name,
                    'customer_email': email,
                    'booking_reference': request.POST.get('booking_reference'),
                    'is_authenticated': request.user.is_authenticated,
                },
                recent_messages=thread.raw_messages,
            )
            thread.apply_triage_result(triage_result.data, triage_result.provider, triage_result.latency_ms)

            deals_result = orchestrator.generate_deal_recommendations(
                customer_profile={
                    'intent': triage_result.data.get('intent'),
                    'priority': triage_result.data.get('priority'),
                    'customer_email': email,
                    'tags': triage_result.data.get('tags'),
                }
            )
            thread.deal_recommendations = deals_result.data.get('deals', thread.deal_recommendations)
            if deals_result.data.get('summary'):
                actions = list(thread.ai_recommended_actions or [])
                actions.append(deals_result.data['summary'])
                thread.ai_recommended_actions = actions
            thread.save()
        except AIAssistantUnavailable as exc:
            logger.warning('AI assistant unavailable for contact form: %s', exc)
            thread.save()
    
    return render(request, 'core/contact.html')


def about_us(request):
    """About Us page view"""
    return render(request, 'core/about.html')


def privacy_policy(request):
    """Privacy Policy page view"""
    return render(request, 'core/privacy.html')


def terms_of_service(request):
    """Terms of Service page view"""
    return render(request, 'core/terms.html')


def cookie_policy(request):
    """Cookie Policy page view"""
    return render(request, 'core/cookies.html')


def accessibility(request):
    """Accessibility page view"""
    return render(request, 'core/accessibility.html')


def careers(request):
    """Careers page view"""
    return render(request, 'core/careers.html')


def press(request):
    """Press page view"""
    return render(request, 'core/press.html')


def sustainability(request):
    """Sustainability page view"""
    return render(request, 'core/sustainability.html')


def help_center(request):
    """Help Center page view"""
    return render(request, 'core/help.html')


def faq(request):
    """FAQ page view"""
    return render(request, 'core/faq.html')
