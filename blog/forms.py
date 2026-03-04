from django import forms

from .models import BlogPost, BlogCategory


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['title', 'slug', 'category', 'featured_image', 'excerpt', 'content', 'is_published']
        widgets = {
            'excerpt': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 14}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].queryset = BlogCategory.objects.all().order_by('name')
