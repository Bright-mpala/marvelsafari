import logging
from dataclasses import dataclass
from typing import Dict, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.utils.html import strip_tags

from .models import EmailTemplate

logger = logging.getLogger(__name__)


@dataclass
class RenderedEmail:
    subject: str
    html: str
    text: str


class EmailTemplateService:
    """Render and send stored email templates."""

    def __init__(self, language: str = 'en'):
        self.language = language

    def _render_string(self, raw: str, context: Dict[str, str]) -> str:
        if not raw:
            return ''
        return Template(raw).render(Context(context))

    def get_template(self, template_type: str) -> Optional[EmailTemplate]:
        queryset = EmailTemplate.objects.filter(
            template_type=template_type,
            language=self.language,
            is_active=True,
        ).order_by('-is_default', '-updated_at')
        return queryset.first()

    def render(self, template_type: str, context: Dict[str, str]) -> Optional[RenderedEmail]:
        template = self.get_template(template_type)
        if not template:
            return None

        rendered_subject = self._render_string(template.subject, context)
        rendered_html = self._render_string(template.html_content, context)
        rendered_text = self._render_string(template.plain_text_content, context) or strip_tags(rendered_html)

        return RenderedEmail(
            subject=rendered_subject,
            html=rendered_html,
            text=rendered_text,
        )

    def send(self, template_type: str, recipients: list[str], context: Dict[str, str], *, fallback_subject: str) -> bool:
        if not recipients:
            return False

        rendered = self.render(template_type, context)
        if not rendered:
            logger.warning("Email template %s not found; skipping send", template_type)
            return False

        subject = rendered.subject or fallback_subject
        text_body = rendered.text or fallback_subject

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        if rendered.html:
            message.attach_alternative(rendered.html, 'text/html')

        try:
            message.send(fail_silently=False)
            return True
        except Exception:
            logger.exception("Failed sending %s email", template_type)
            return False
