# views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from bookings.models import Booking
from properties.models import Property

from .forms import ReviewSubmissionForm
from .models import Review, ReviewHelpful, ReviewImage, ReviewReport


def review_list(request):
    """List reviews with advanced filtering and sorting."""
    reviews = Review.objects.filter(
        is_published=True
    ).select_related(
        'user', 'property'
    ).prefetch_related(
        'images'
    ).annotate(
        helpful_votes=Count('helpful_votes', filter=Q(helpful_votes__is_helpful=True)),
        not_helpful_votes=Count('helpful_votes', filter=Q(helpful_votes__is_helpful=False))
    )

    # Filter by property
    property_id = request.GET.get('property')
    if property_id:
        reviews = reviews.filter(property_id=property_id)

    # Filter by rating
    rating_filter = request.GET.get('rating')
    if rating_filter:
        if rating_filter == '5':
            reviews = reviews.filter(overall_rating=5)
        elif rating_filter == '4':
            reviews = reviews.filter(overall_rating__gte=4)
        elif rating_filter == '3':
            reviews = reviews.filter(overall_rating__gte=3)
        elif rating_filter == '2':
            reviews = reviews.filter(overall_rating__gte=2)

    # Filter by date
    date_filter = request.GET.get('date')
    if date_filter == 'month':
        reviews = reviews.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30))
    elif date_filter == '3months':
        reviews = reviews.filter(created_at__gte=timezone.now() - timezone.timedelta(days=90))
    elif date_filter == 'year':
        reviews = reviews.filter(created_at__gte=timezone.now() - timezone.timedelta(days=365))

    # Search in comments
    search_query = request.GET.get('q')
    if search_query:
        reviews = reviews.filter(
            Q(title__icontains=search_query) |
            Q(comment__icontains=search_query) |
            Q(property__name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    allowed_sorts = ['-created_at', 'created_at', '-overall_rating', 'overall_rating', '-helpful_votes']
    if sort_by in allowed_sorts:
        reviews = reviews.order_by(sort_by)

    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calculate averages for all properties
    averages = Review.objects.filter(is_published=True).aggregate(
        avg_overall=Avg('overall_rating'),
        avg_cleanliness=Avg('cleanliness'),
        avg_comfort=Avg('comfort'),
        avg_location=Avg('location'),
        avg_facilities=Avg('facilities'),
        avg_staff=Avg('staff'),
        avg_value=Avg('value_for_money'),
        total_reviews=Count('id')
    )

    # Get rating distribution
    rating_distribution = Review.objects.filter(is_published=True).values('overall_rating').annotate(
        count=Count('id')
    ).order_by('-overall_rating')

    # Get popular properties
    popular_properties = Property.objects.filter(
        reviews__is_published=True
    ).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__overall_rating')
    ).filter(
        review_count__gt=0
    ).order_by('-review_count')[:5]

    context = {
        'page_obj': page_obj,
        'averages': averages,
        'rating_distribution': rating_distribution,
        'popular_properties': popular_properties,
        'current_filters': {
            'property': property_id,
            'rating': rating_filter,
            'date': date_filter,
            'sort': sort_by,
            'q': search_query,
        }
    }
    return render(request, 'reviews/review_list.html', context)


@login_required
def review_create(request, booking_id):
    """Create a review for a completed booking."""
    booking = get_object_or_404(
        Booking.objects.select_related('property', 'user'),
        pk=booking_id,
        user=request.user,
    )

    # Check if booking is completed
    if booking.status != 'completed':
        messages.error(request, 'You can only review completed bookings.')
        return redirect('bookings:detail', pk=booking.pk)

    # Check if already reviewed
    if Review.objects.filter(user=request.user, property=booking.property).exists():
        messages.info(request, 'You have already reviewed this property.')
        return redirect('bookings:detail', pk=booking.pk)

    if request.method == 'POST':
        form = ReviewSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.user = request.user
            review.property = booking.property
            review.is_verified = True
            review.ip_address = request.META.get('REMOTE_ADDR')
            review.user_agent = request.META.get('HTTP_USER_AGENT', '')
            review.save()

            # Handle image uploads
            images = request.FILES.getlist('images')
            for idx, image in enumerate(images):
                ReviewImage.objects.create(
                    review=review,
                    image=image,
                    is_primary=(idx == 0)  # First image is primary
                )

            messages.success(request, 'Your review was submitted successfully. Thank you for your feedback!')
            return redirect('reviews:review_detail', pk=review.pk)
    else:
        form = ReviewSubmissionForm()

    return render(request, 'reviews/review_create.html', {
        'form': form, 
        'booking': booking,
        'property': booking.property
    })


def review_detail(request, pk):
    """Display individual review with details."""
    review = get_object_or_404(
        Review.objects.select_related(
            'user', 'property', 'booking'
        ).prefetch_related(
            'images', 'helpful_votes__user'
        ),
        pk=pk,
        is_published=True
    )

    # Check if current user found this helpful
    user_helpful = None
    if request.user.is_authenticated:
        try:
            helpful_vote = ReviewHelpful.objects.get(
                review=review,
                user=request.user
            )
            user_helpful = helpful_vote.is_helpful
        except ReviewHelpful.DoesNotExist:
            pass

    # Get similar reviews from same property
    similar_reviews = Review.objects.filter(
        property=review.property,
        is_published=True
    ).exclude(
        pk=review.pk
    ).select_related('user')[:3]

    context = {
        'review': review,
        'user_helpful': user_helpful,
        'similar_reviews': similar_reviews,
        'category_ratings': {
            'Cleanliness': review.cleanliness,
            'Comfort': review.comfort,
            'Location': review.location,
            'Facilities': review.facilities,
            'Staff': review.staff,
            'Value for Money': review.value_for_money,
        }
    }
    return render(request, 'reviews/review_detail.html', context)


@login_required
@require_POST
def review_helpful(request, pk):
    """Mark a review as helpful or not helpful."""
    review = get_object_or_404(Review, pk=pk)
    
    is_helpful = request.POST.get('is_helpful') == 'true'
    
    # Update or create vote
    helpful_vote, created = ReviewHelpful.objects.update_or_create(
        review=review,
        user=request.user,
        defaults={'is_helpful': is_helpful}
    )

    # Update counts
    helpful_count = ReviewHelpful.objects.filter(review=review, is_helpful=True).count()
    not_helpful_count = ReviewHelpful.objects.filter(review=review, is_helpful=False).count()
    
    review.helpful_count = helpful_count
    review.not_helpful_count = not_helpful_count
    review.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'helpful_count': helpful_count,
            'not_helpful_count': not_helpful_count,
            'user_vote': is_helpful
        })
    
    messages.success(request, 'Thank you for your feedback!')
    return redirect('reviews:review_detail', pk=review.pk)


@login_required
def review_report(request, pk):
    """Report an inappropriate review."""
    review = get_object_or_404(Review, pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        description = request.POST.get('description', '')
        
        # Check if already reported by this user
        existing_report = ReviewReport.objects.filter(
            review=review,
            reported_by=request.user
        ).first()
        
        if existing_report:
            messages.warning(request, 'You have already reported this review.')
        else:
            ReviewReport.objects.create(
                review=review,
                reported_by=request.user,
                reason=reason,
                description=description
            )
            messages.success(request, 'Thank you for reporting. Our team will review this content.')
        
        return redirect('reviews:review_detail', pk=review.pk)
    
    return render(request, 'reviews/review_report.html', {'review': review})


@login_required
def my_reviews(request):
    """List current user's reviews."""
    reviews = Review.objects.filter(
        user=request.user
    ).select_related(
        'property'
    ).prefetch_related(
        'images'
    ).order_by('-created_at')

    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'reviews/my_reviews.html', {'page_obj': page_obj})


def property_reviews(request, property_id):
    """List reviews for a specific property."""
    property_obj = get_object_or_404(Property, pk=property_id)
    
    reviews = Review.objects.filter(
        property=property_obj,
        is_published=True
    ).select_related(
        'user'
    ).prefetch_related(
        'images'
    ).annotate(
        helpful_count=Count('helpful_votes', filter=Q(helpful_votes__is_helpful=True))
    )

    # Calculate property statistics
    stats = reviews.aggregate(
        avg_rating=Avg('overall_rating'),
        total_reviews=Count('id'),
        avg_cleanliness=Avg('cleanliness'),
        avg_comfort=Avg('comfort'),
        avg_location=Avg('location'),
        avg_staff=Avg('staff'),
        avg_value=Avg('value_for_money')
    )

    # Rating distribution
    distribution = reviews.values('overall_rating').annotate(
        count=Count('id')
    ).order_by('-overall_rating')

    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'property': property_obj,
        'page_obj': page_obj,
        'stats': stats,
        'distribution': distribution,
    }
    return render(request, 'reviews/property_reviews.html', context)