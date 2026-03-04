from django.contrib import admin

from travel_booking.admin import admin_site

from .models import BlogPost, BlogCategory


@admin.register(BlogCategory, site=admin_site)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(BlogPost, site=admin_site)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'is_published', 'published_at', 'created_at')
    list_filter = ('is_published', 'created_at', 'category')
    search_fields = ('title', 'slug', 'content', 'author__email')
    prepopulated_fields = {'slug': ('title',)}
