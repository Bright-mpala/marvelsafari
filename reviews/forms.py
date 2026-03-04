# forms.py
from django import forms
from .models import Review, ReviewImage


class MultiImageInput(forms.ClearableFileInput):
    """File input widget that supports selecting multiple images."""

    allow_multiple_selected = True


class ReviewSubmissionForm(forms.ModelForm):
    images = forms.ImageField(
        required=False,
        widget=MultiImageInput(attrs={
            'multiple': True,
            'accept': 'image/*',
            'class': 'form-input'
        })
    )
    
    class Meta:
        model = Review
        fields = [
            'overall_rating', 'title', 'comment', 
            'positive_comment', 'negative_comment',
            'cleanliness', 'comfort', 'location', 
            'facilities', 'staff', 'value_for_money'
        ]
        widgets = {
            'overall_rating': forms.NumberInput(attrs={
                'min': 1, 'max': 5, 'step': 0.5,
                'class': 'form-input'
            }),
            'title': forms.TextInput(attrs={
                'maxlength': 200,
                'placeholder': 'Summary of your experience',
                'class': 'form-input'
            }),
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Tell us about your experience...',
                'class': 'form-textarea'
            }),
            'positive_comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'What did you like most?',
                'class': 'form-textarea'
            }),
            'negative_comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'What could be improved?',
                'class': 'form-textarea'
            }),
            'cleanliness': forms.NumberInput(attrs={
                'min': 1, 'max': 5,
                'class': 'form-input'
            }),
            'comfort': forms.NumberInput(attrs={
                'min': 1, 'max': 5,
                'class': 'form-input'
            }),
            'location': forms.NumberInput(attrs={
                'min': 1, 'max': 5,
                'class': 'form-input'
            }),
            'facilities': forms.NumberInput(attrs={
                'min': 1, 'max': 5,
                'class': 'form-input'
            }),
            'staff': forms.NumberInput(attrs={
                'min': 1, 'max': 5,
                'class': 'form-input'
            }),
            'value_for_money': forms.NumberInput(attrs={
                'min': 1, 'max': 5,
                'class': 'form-input'
            }),
        }
    
    def clean_overall_rating(self):
        rating = self.cleaned_data.get('overall_rating')
        if rating and (rating < 1 or rating > 5):
            raise forms.ValidationError('Rating must be between 1 and 5')
        return rating