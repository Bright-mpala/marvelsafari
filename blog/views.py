from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core import signing
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from newsletter.models import NewsletterSubscriber
from newsletter.views import UNSUBSCRIBE_SALT

from .forms import BlogPostForm
from .models import BlogPost, BlogCategory


def post_list(request):
    """Public blog index with optional search and category filter."""
    posts = BlogPost.objects.filter(is_published=True).select_related('author', 'category')

    query = request.GET.get('q') or ''
    if query:
        posts = posts.filter(
            Q(title__icontains=query)
            | Q(excerpt__icontains=query)
            | Q(content__icontains=query)
        )

    category_slug = request.GET.get('category') or ''
    active_category = None
    if category_slug:
        active_category = get_object_or_404(BlogCategory, slug=category_slug)
        posts = posts.filter(category=active_category)

    categories = BlogCategory.objects.all().order_by('name')

    context = {
        'posts': posts,
        'categories': categories,
        'active_category': active_category,
    }
    return render(request, 'blog/post_list.html', context)


def post_detail(request, slug):
    """Single blog post view with category in context."""
    post = get_object_or_404(BlogPost.objects.select_related('author', 'category'), slug=slug, is_published=True)
    related_posts = BlogPost.objects.filter(
        is_published=True,
        category=post.category
    ).exclude(id=post.id)[:3] if post.category else []

    context = {
        'post': post,
        'related_posts': related_posts,
    }
    return render(request, 'blog/post_detail.html', context)


def _send_post_to_newsletter_subscribers(request, post: BlogPost) -> None:
    """Send a newly published blog post to all active newsletter subscribers.

    Each recipient gets a personalised unsubscribe link, reusing the
    newsletter app's unsubscribe token logic.
    """

    recipients = list(
        NewsletterSubscriber.objects.filter(is_active=True).values_list('email', flat=True)
    )
    if not recipients:
        messages.info(
            request,
            'Blog post published, but there are no active newsletter subscribers yet.',
        )
        return

    connection = get_connection(fail_silently=False)
    email_messages = []

    post_url = request.build_absolute_uri(post.get_absolute_url())
    featured_image_url = None
    if post.featured_image:
        try:
            featured_image_url = request.build_absolute_uri(post.featured_image.url)
        except Exception:
            featured_image_url = None

    for recipient in recipients:
        token = signing.dumps(recipient, salt=UNSUBSCRIBE_SALT)
        unsubscribe_path = reverse('newsletter:unsubscribe')
        unsubscribe_url = request.build_absolute_uri(f'{unsubscribe_path}?token={token}')

        html_body = render_to_string(
            'newsletter/email_blog_post.html',
            {
                'post': post,
                'post_url': post_url,
                'featured_image_url': featured_image_url,
                'unsubscribe_url': unsubscribe_url,
            },
        )

        text_parts = [post.title]
        if post.excerpt:
            text_parts.append('')
            text_parts.append(post.excerpt)
        text_parts.append('')
        text_parts.append(f'Read the full article: {post_url}')
        text_parts.append('')
        text_parts.append(f'Unsubscribe: {unsubscribe_url}')
        text_body = '\n'.join(text_parts)

        message = EmailMultiAlternatives(
            subject=f'New from Marvel Safari: {post.title}',
            body=text_body,
            to=[recipient],
            connection=connection,
        )
        message.attach_alternative(html_body, 'text/html')
        email_messages.append(message)

    try:
        sent_count = connection.send_messages(email_messages)
    except Exception:
        messages.error(request, 'Blog post published, but sending newsletter emails failed.')
        return

    if sent_count:
        messages.success(request, f'Blog post emailed to {sent_count} newsletter subscribers.')


@login_required
@user_passes_test(lambda user: user.is_staff)
def post_create(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            just_published = post.is_published and post.published_at is None
            if just_published:
                post.published_at = timezone.now()
            post.save()

            if just_published:
                _send_post_to_newsletter_subscribers(request, post)

            messages.success(request, 'Blog post created successfully.')
            return redirect('blog:post_detail', slug=post.slug)
    else:
        form = BlogPostForm()

    return render(request, 'blog/post_form.html', {'form': form})


@login_required
@user_passes_test(lambda user: user.is_staff)
def post_edit(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    was_published = post.is_published
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            just_published = post.is_published and not was_published
            if post.is_published and post.published_at is None:
                post.published_at = timezone.now()
            post.save()

            if just_published:
                _send_post_to_newsletter_subscribers(request, post)

            messages.success(request, 'Blog post updated successfully.')
            return redirect('blog:post_detail', slug=post.slug)
    else:
        form = BlogPostForm(instance=post)

    return render(request, 'blog/post_form.html', {'form': form, 'post': post})
