from django.conf import settings
from django.db import models
from django.urls import reverse


class BlogCategory(models.Model):
    """Category for grouping blog posts."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'blog category'
        verbose_name_plural = 'blog categories'

    def __str__(self) -> str:
        return self.name


class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        related_name='posts',
        null=True,
        blank=True,
    )
    featured_image = models.ImageField(
        upload_to='blog/featured/',
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_posts',
    )
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    class Meta:
        ordering = ['-published_at', '-created_at']
