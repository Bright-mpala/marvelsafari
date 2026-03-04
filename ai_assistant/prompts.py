"""
Centralized prompt management system for MarvelSafari AI.

Provides versioned, templated prompts with variable substitution,
making prompts auditable, testable, and maintainable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class PromptCategory(str, Enum):
    """Categories for organizing prompts."""
    
    SUPPORT = "support"
    ITINERARY = "itinerary"
    RECOMMENDATIONS = "recommendations"
    SEO = "seo"
    VERIFICATION = "verification"
    ANALYTICS = "analytics"
    TRIAGE = "triage"
    DEALS = "deals"


@dataclass
class PromptTemplate:
    """A versioned, configurable prompt template."""
    
    name: str
    category: PromptCategory
    version: str
    system_prompt: str
    user_prompt_template: str
    required_fields: List[str] = field(default_factory=list)
    max_tokens: int = 900
    temperature: float = 0.2
    expect_json: bool = True
    description: str = ""
    
    @property
    def prompt_hash(self) -> str:
        """Generate a hash for cache invalidation."""
        content = f"{self.system_prompt}:{self.user_prompt_template}:{self.version}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def render_user_prompt(self, context: Dict[str, Any]) -> str:
        """Render user prompt with context variables."""
        payload = {
            **context,
            "required_fields": self.required_fields,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "prompt_hash": self.prompt_hash,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "expect_json": self.expect_json,
        }


class PromptRegistry:
    """
    Central registry for all AI prompts.
    
    Enables:
    - Versioned prompts for A/B testing
    - Runtime prompt overrides
    - Audit trail for prompt changes
    - Caching for performance
    """
    
    _instance: Optional['PromptRegistry'] = None
    _prompts: Dict[str, PromptTemplate] = {}
    
    def __new__(cls) -> 'PromptRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_default_prompts()
        return cls._instance
    
    def _load_default_prompts(self) -> None:
        """Load built-in prompt templates."""
        self._prompts = {}
        
        # Support Chat Prompt
        self.register(PromptTemplate(
            name="support_chat",
            category=PromptCategory.SUPPORT,
            version="2.0.0",
            system_prompt=(
                "You are MarvelSafari's AI concierge. Provide policy-aware responses to "
                "booking, cancellation, visa, and travel logistics questions. "
                "Be empathetic, accurate, and concise. "
                "If unsure or the query requires human judgment, recommend contacting a human agent. "
                "Always structure your response as valid JSON."
            ),
            user_prompt_template="customer_question,context",
            required_fields=[
                "answer",
                "confidence",
                "needs_handoff",
                "related_policies",
                "next_steps",
            ],
            max_tokens=900,
            temperature=0.2,
            description="Customer support chat responses",
        ))
        
        # Itinerary Generator Prompt
        self.register(PromptTemplate(
            name="itinerary_generator",
            category=PromptCategory.ITINERARY,
            version="2.0.0",
            system_prompt=(
                "You design MarvelSafari itineraries that balance pace, budget, and memorable touchpoints. "
                "Consider local customs, seasonality, and sustainable tourism practices. "
                "Return JSON with a per-day plan, suggested experiences, packing tips, and cost distribution."
            ),
            user_prompt_template="destination,budget,days,travel_style,interests",
            required_fields=[
                "daily_plan",
                "packing_tips",
                "cost_breakdown",
                "local_insights",
                "disclaimer",
            ],
            max_tokens=1200,
            temperature=0.3,
            description="Generate travel itineraries",
        ))
        
        # Destination Recommendations Prompt
        self.register(PromptTemplate(
            name="destination_recommendations",
            category=PromptCategory.RECOMMENDATIONS,
            version="2.0.0",
            system_prompt=(
                "You recommend destinations for MarvelSafari customers by blending their past searches "
                "with current preferences. Consider seasonality, budget constraints, and travel restrictions. "
                "Output JSON with recommendations (ranked), supporting data points, and a summary."
            ),
            user_prompt_template="preferences,history",
            required_fields=[
                "recommendations",
                "summary",
                "data_points_used",
            ],
            max_tokens=900,
            temperature=0.4,
            description="Personalized destination recommendations",
        ))
        
        # SEO Content Generator Prompt
        self.register(PromptTemplate(
            name="seo_content",
            category=PromptCategory.SEO,
            version="2.0.0",
            system_prompt=(
                "You are MarvelSafari's SEO strategist. Produce JSON for destination landing pages "
                "with hero_title, intro, highlight_sections, faq, target_keywords, and meta_description. "
                "Keep claims factual and cite why MarvelSafari helps. Optimize for search intent."
            ),
            user_prompt_template="destination,keywords,tone",
            required_fields=[
                "hero_title",
                "intro",
                "highlight_sections",
                "faq",
                "target_keywords",
                "meta_description",
            ],
            max_tokens=1500,
            temperature=0.5,
            description="SEO-optimized landing page content",
        ))
        
        # Car Listing Verification Prompt
        self.register(PromptTemplate(
            name="car_verification",
            category=PromptCategory.VERIFICATION,
            version="2.0.0",
            system_prompt=(
                "You are an authenticity checker for MarvelSafari's marketplace where both private "
                "individuals and fleet managers can list vehicles. Never assume every listing belongs "
                "to a company—focus on internal consistency (make/model/year/price), policy compliance, "
                "and red flags like impossible specs. "
                "Return JSON with: is_real (bool), confidence (0-1), reasons (array of short strings), "
                "and action ('approve' or 'manual_review'). Approve only if confidence >= 0.7."
            ),
            user_prompt_template="car",
            required_fields=["is_real", "confidence", "reasons", "action"],
            max_tokens=600,
            temperature=0.1,
            description="Verify car listing authenticity",
        ))
        
        # Support Thread Triage Prompt
        self.register(PromptTemplate(
            name="support_triage",
            category=PromptCategory.TRIAGE,
            version="2.0.0",
            system_prompt=(
                "You are MarvelSafari's concierge AI. Summarize travel support conversations, "
                "detect intent, urgency, and craft a respectful reply. "
                "Identify if the customer needs immediate assistance or can be helped asynchronously. "
                "Always respond with valid JSON."
            ),
            user_prompt_template="thread,recent_messages",
            required_fields=[
                "summary",
                "intent",
                "priority",
                "sentiment_score",
                "recommended_actions",
                "suggested_reply",
                "status",
                "tags",
                "deal_recommendations",
                "booking_context",
            ],
            max_tokens=1000,
            temperature=0.2,
            description="Triage support threads",
        ))
        
        # Booking Analysis Prompt
        self.register(PromptTemplate(
            name="booking_analysis",
            category=PromptCategory.ANALYTICS,
            version="2.0.0",
            system_prompt=(
                "You review MarvelSafari booking records. Extract structured insights, unmet needs, "
                "risk flags, and upsell opportunities. Consider guest preferences and property amenities. "
                "Respond using JSON."
            ),
            user_prompt_template="booking",
            required_fields=[
                "summary",
                "priority",
                "tags",
                "recommended_actions",
                "structured",
            ],
            max_tokens=800,
            temperature=0.2,
            description="Analyze booking for insights",
        ))
        
        # Deal Recommendations Prompt
        self.register(PromptTemplate(
            name="deal_recommendations",
            category=PromptCategory.DEALS,
            version="2.0.0",
            system_prompt=(
                "You are the MarvelSafari deals engine. Match customers with available properties or tours "
                "and explain why each option fits. Consider customer history, preferences, and current promotions. "
                "Output JSON with `deals` (array) and `summary`."
            ),
            user_prompt_template="customer,inventory",
            required_fields=["deals", "summary"],
            max_tokens=900,
            temperature=0.3,
            description="Generate personalized deals",
        ))
    
    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        key = f"{template.category.value}:{template.name}"
        self._prompts[key] = template
        logger.debug("Registered prompt: %s (v%s)", key, template.version)
    
    def get(self, category: PromptCategory, name: str) -> Optional[PromptTemplate]:
        """Retrieve a prompt template by category and name."""
        key = f"{category.value}:{name}"
        return self._prompts.get(key)
    
    def get_by_name(self, name: str) -> Optional[PromptTemplate]:
        """Retrieve a prompt template by name (searches all categories)."""
        for key, template in self._prompts.items():
            if template.name == name:
                return template
        return None
    
    def list_prompts(self, category: Optional[PromptCategory] = None) -> List[PromptTemplate]:
        """List all prompts, optionally filtered by category."""
        prompts = list(self._prompts.values())
        if category:
            prompts = [p for p in prompts if p.category == category]
        return prompts
    
    def override_from_settings(self) -> None:
        """
        Load prompt overrides from Django settings.
        
        Allows runtime customization via:
        AI_PROMPT_OVERRIDES = {
            'support_chat': {'system_prompt': '...', 'version': '2.1.0'},
        }
        """
        overrides = getattr(settings, 'AI_PROMPT_OVERRIDES', {})
        for name, changes in overrides.items():
            template = self.get_by_name(name)
            if template:
                for field, value in changes.items():
                    if hasattr(template, field):
                        setattr(template, field, value)
                logger.info("Applied prompt override for: %s", name)


def get_prompt(name: str) -> PromptTemplate:
    """
    Convenience function to get a prompt by name.
    
    Raises KeyError if prompt not found.
    """
    registry = PromptRegistry()
    template = registry.get_by_name(name)
    if not template:
        raise KeyError(f"Prompt '{name}' not found in registry")
    return template


def render_prompt(name: str, context: Dict[str, Any]) -> tuple[str, str, PromptTemplate]:
    """
    Render a prompt with context and return (system_prompt, user_prompt, template).
    
    Usage:
        system, user, template = render_prompt('support_chat', {
            'customer_question': 'How do I cancel?',
            'context': {'booking_id': '123'},
        })
    """
    template = get_prompt(name)
    user_prompt = template.render_user_prompt(context)
    return template.system_prompt, user_prompt, template
