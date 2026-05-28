from django.contrib import admin
from .models import GalleryImage, News, NewsImage, NewsDocument


class NewsImageInline(admin.TabularInline):
    model = NewsImage
    extra = 1


class NewsDocumentInline(admin.TabularInline):
    model = NewsDocument
    extra = 1


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    inlines = [NewsImageInline, NewsDocumentInline]
    list_display = ['title', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'content']


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'active', 'order', 'created_at']
    list_filter = ['active']
    search_fields = ['title', 'caption']
    ordering = ['order', '-created_at']
