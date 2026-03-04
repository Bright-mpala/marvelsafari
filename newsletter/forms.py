from django import forms

from .models import NewsletterCampaign, NewsletterSubscriber


class NewsletterSubscriberForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ['email']


class NewsletterCampaignForm(forms.ModelForm):
    class Meta:
        model = NewsletterCampaign
        fields = ['title', 'subject', 'body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 10}),
        }
