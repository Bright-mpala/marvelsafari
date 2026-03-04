from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import (
    PropertyType, AmenityCategory, Amenity, Property, RoomType, Room,
    PropertyImage, PricePlan, Availability, PropertyDocument, PropertyStatus,
    PropertyActivity, RoomTypeImage
)
from travel_booking.admin import admin_site


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0
    show_change_link = True
    readonly_fields = ('width', 'height', 'file_size', 'is_processed')
    fields = ('image', 'caption', 'is_primary', 'display_order', 'width', 'height')


class RoomTypeInline(admin.TabularInline):
    model = RoomType
    extra = 0
    show_change_link = True
    fields = ('name', 'base_price', 'quantity_available', 'max_adults', 'max_children', 'bed_type', 'display_order')


class PricePlanInline(admin.TabularInline):
    model = PricePlan
    extra = 0


class RoomTypeImageInline(admin.TabularInline):
    model = RoomTypeImage
    extra = 1
    fields = ('image', 'caption', 'is_primary', 'display_order')
    readonly_fields = ('width', 'height', 'file_size')


class PropertyDocumentInline(admin.TabularInline):
    model = PropertyDocument
    extra = 1


class PropertyActivityInline(admin.TabularInline):
    model = PropertyActivity
    extra = 0
    show_change_link = True
    fields = ('name', 'activity_type', 'price_per_person', 'duration', 'availability', 'is_active')


@admin.register(PropertyType, site=admin_site)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')


@admin.register(AmenityCategory, site=admin_site)
class AmenityCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')


@admin.register(Amenity, site=admin_site)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'category', 'is_chargeable', 'charge_amount', 'is_active')
    list_filter = ('category', 'is_chargeable', 'is_active')
    search_fields = ('name', 'description')


@admin.register(Property, site=admin_site)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'property_type', 'city', 'country', 'status_badge', 'owner_email', 'is_verified', 'created_at')
    list_filter = ('status', 'is_verified', 'is_featured', 'property_type', 'country', 'created_at')
    search_fields = ('name', 'city', 'country', 'address', 'owner__email')
    readonly_fields = (
        'view_count', 'booking_count', 'average_rating', 'review_count',
        'approved_by', 'approved_at', 'verification_date', 'published_at',
        'created_at', 'updated_at'
    )
    prepopulated_fields = {'slug': ('name',)}
    list_select_related = ('property_type', 'owner')
    raw_id_fields = ('owner',)
    autocomplete_fields = ('amenities',)
    list_per_page = 25
    date_hierarchy = 'created_at'
    # Add approval actions
    actions = ['approve_properties', 'reject_properties', 'mark_as_featured']
    # Inlines for managing property details
    inlines = [PropertyImageInline, RoomTypeInline, PropertyActivityInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Keep changelist light by deferring large text fields while still selecting relations
        return qs.select_related('property_type', 'owner').defer(
            'description',
            'cancellation_policy',
            'house_rules',
            'special_instructions',
            'meta_description',
            'meta_keywords',
            'address',
        )
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            PropertyStatus.DRAFT: '#6c757d',      # gray
            PropertyStatus.PENDING: '#ffc107',    # yellow
            PropertyStatus.APPROVED: '#28a745',   # green
            PropertyStatus.ACTIVE: '#28a745',     # green
            PropertyStatus.REJECTED: '#dc3545',   # red
            PropertyStatus.INACTIVE: '#17a2b8',   # blue
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    status_badge.admin_order_field = 'status'
    
    def owner_email(self, obj):
        """Display owner email."""
        if obj.owner:
            return obj.owner.email
        return '-'
    owner_email.short_description = _('Owner')
    owner_email.admin_order_field = 'owner__email'
    
    @admin.action(description=_('Approve selected properties'))
    def approve_properties(self, request, queryset):
        """Admin action to approve multiple properties."""
        from .services import get_property_service
        
        service = get_property_service(request)
        approved_count = 0
        error_count = 0
        
        for prop in queryset.filter(status=PropertyStatus.PENDING):
            try:
                service.approve_property(prop, request.user)
                approved_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f'Error approving {prop.name}: {e}',
                    level=messages.ERROR
                )
        
        if approved_count:
            self.message_user(
                request,
                f'{approved_count} propert{"ies" if approved_count > 1 else "y"} approved successfully.',
                level=messages.SUCCESS
            )
        
        if error_count == 0 and approved_count == 0:
            self.message_user(
                request,
                'No pending properties were selected.',
                level=messages.WARNING
            )
    
    @admin.action(description=_('Reject selected properties (requires reason)'))
    def reject_properties(self, request, queryset):
        """Admin action to reject properties - redirects to intermediate page."""
        # For bulk rejection, we need an intermediate page
        # For simplicity, reject with generic reason
        from .services import get_property_service
        
        service = get_property_service(request)
        rejected_count = 0
        
        for prop in queryset.filter(status=PropertyStatus.PENDING):
            try:
                service.reject_property(
                    prop,
                    request.user,
                    reason='Property does not meet our listing requirements. Please review and resubmit.'
                )
                rejected_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'Error rejecting {prop.name}: {e}',
                    level=messages.ERROR
                )
        
        if rejected_count:
            self.message_user(
                request,
                f'{rejected_count} propert{"ies" if rejected_count > 1 else "y"} rejected. Owners have been notified.',
                level=messages.SUCCESS
            )
    
    @admin.action(description=_('Mark as featured'))
    def mark_as_featured(self, request, queryset):
        """Mark properties as featured."""
        updated = queryset.filter(
            status__in=[PropertyStatus.APPROVED, PropertyStatus.ACTIVE]
        ).update(is_featured=True)
        
        self.message_user(
            request,
            f'{updated} propert{"ies" if updated > 1 else "y"} marked as featured.',
            level=messages.SUCCESS
        )

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'property_type', 'star_rating', 'description')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country', 'latitude', 'longitude')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'website', 'owner', 'manager_name', 'manager_phone', 'manager_email')
        }),
        ('Property Details', {
            'fields': ('check_in_time', 'check_out_time', 'earliest_check_in', 'latest_check_out',
                      'total_rooms', 'year_built', 'year_renovated')
        }),
        ('Policies', {
            'fields': ('cancellation_policy', 'house_rules', 'special_instructions')
        }),
        ('Amenities', {
            'fields': ('amenities',)
        }),
        ('Status & Approval', {
            'fields': ('status', 'rejection_reason', 'is_featured', 'is_verified', 
                      'verification_date', 'approved_by', 'approved_at', 'published_at'),
            'description': 'Approval workflow: DRAFT → PENDING → APPROVED/REJECTED'
        }),
        ('Pricing & Commission', {
            'fields': ('commission_rate', 'minimum_price', 'maximum_price')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count', 'booking_count', 'average_rating', 'review_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PropertyImage, site=admin_site)
class PropertyImageAdmin(admin.ModelAdmin):
    """Admin for managing property images."""
    list_display = ('id', 'property', 'caption', 'is_primary', 'display_order', 'is_processed', 'created_at')
    list_filter = ('is_primary', 'is_processed', 'created_at')
    search_fields = ('property__name', 'caption')
    readonly_fields = ('width', 'height', 'file_size', 'thumbnail_url', 'is_processed', 'processing_error')
    list_select_related = ('property',)


@admin.register(RoomType, site=admin_site)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'base_price', 'quantity_available', 'max_occupancy', 'bed_type', 'room_size', 'image_count', 'display_order')
    list_filter = ('property', 'bed_type')
    search_fields = ('name', 'property__name')
    list_editable = ('base_price', 'quantity_available')
    inlines = [RoomTypeImageInline, PricePlanInline]
    autocomplete_fields = ('property',)
    
    def image_count(self, obj):
        count = obj.images.count()
        return format_html('<span style="color: {}">{} images</span>', 'green' if count > 0 else 'gray', count)
    image_count.short_description = _('Images')


@admin.register(Room, site=admin_site)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'floor', 'is_available')
    list_filter = ('room_type__property', 'is_available')
    search_fields = ('room_number', 'room_type__name')


@admin.register(PricePlan, site=admin_site)
class PricePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'base_price', 'currency', 'is_active')
    list_filter = ('is_active', 'currency', 'room_type__property')
    search_fields = ('name', 'room_type__name')


@admin.register(Availability, site=admin_site)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ('room', 'date', 'is_available', 'price', 'available_rooms')
    list_filter = ('is_available', 'date')
    search_fields = ('room__room_type__property__name', 'room__room_number')
    date_hierarchy = 'date'


@admin.register(PropertyDocument, site=admin_site)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ('property', 'document_type', 'document_number', 'is_verified', 'expiry_date')
    list_filter = ('document_type', 'is_verified')
    search_fields = ('property__name', 'document_number')


@admin.register(PropertyActivity, site=admin_site)
class PropertyActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'activity_type', 'price_per_person', 'duration', 'availability', 'is_active')
    list_filter = ('activity_type', 'availability', 'difficulty', 'is_active')
    search_fields = ('name', 'property__name', 'description')
    list_editable = ('is_active',)
    autocomplete_fields = ('property',)
    fieldsets = (
        (None, {
            'fields': ('property', 'name', 'description', 'activity_type')
        }),
        (_('Pricing & Duration'), {
            'fields': ('price_per_person', 'duration')
        }),
        (_('Participants'), {
            'fields': ('min_participants', 'max_participants')
        }),
        (_('Availability & Details'), {
            'fields': ('availability', 'difficulty', 'included')
        }),
        (_('Settings'), {
            'fields': ('display_order', 'is_active')
        }),
    )


@admin.register(RoomTypeImage, site=admin_site)
class RoomTypeImageAdmin(admin.ModelAdmin):
    list_display = ('room_type', 'caption', 'is_primary', 'display_order', 'image_preview', 'dimensions')
    list_filter = ('room_type__property', 'is_primary')
    search_fields = ('room_type__name', 'room_type__property__name', 'caption')
    list_editable = ('is_primary', 'display_order')
    raw_id_fields = ('room_type',)
    readonly_fields = ('width', 'height', 'file_size', 'image_preview_large')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 80px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return '-'
    image_preview.short_description = _('Preview')
    
    def image_preview_large(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 400px; max-height: 300px; object-fit: contain; border-radius: 8px;" />', obj.image.url)
        return '-'
    image_preview_large.short_description = _('Image Preview')
    
    def dimensions(self, obj):
        if obj.width and obj.height:
            return f'{obj.width}×{obj.height}'
        return '-'
    dimensions.short_description = _('Size')