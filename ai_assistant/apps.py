from django.apps import AppConfig


class AIAssistantConfig(AppConfig):
    """Configuration for the AI Assistant domain services."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant'
    verbose_name = 'AI Assistant'

    def ready(self):
        # Import signals so booking events are processed automatically.
        from . import signals  # noqa: F401
