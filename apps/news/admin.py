from django.contrib import admin
from django import forms
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import (
    GalleryImage,
    HomePageContactSection,
    HomepageFeatureCard,
    HomepageInquiry,
    HomepageSettings,
    News,
    NewsDocument,
    NewsImage,
)


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


@admin.register(HomePageContactSection)
class HomePageContactSectionAdmin(admin.ModelAdmin):
    list_display = ['section_title', 'phone_number', 'email_address']
    search_fields = ['section_title', 'introductory_text', 'email_address', 'phone_number']


class HomepageSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = HomepageSettings
        fields = ['hero_heading', 'hero_description', 'hero_image', 'footer_text', 'contact_section']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hero_image'].help_text = 'Recommended: 1600 x 1100 px or larger, landscape orientation, JPG/PNG/WebP, ideally under 2 MB.'


class HomepageFeatureCardInlineForm(forms.ModelForm):
    class Meta:
        model = HomepageFeatureCard
        fields = ['order', 'slug', 'title', 'description', 'image', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].help_text = 'Recommended: 1200 x 900 px or larger, consistent aspect ratio across cards, JPG/PNG/WebP, ideally under 2 MB.'


class HomepageFeatureCardInline(admin.TabularInline):
    model = HomepageFeatureCard
    form = HomepageFeatureCardInlineForm
    extra = 0
    fields = ['order', 'slug', 'title', 'description', 'image', 'is_active']
    ordering = ['order', 'id']


@admin.register(HomepageSettings)
class HomepageSettingsAdmin(admin.ModelAdmin):
    form = HomepageSettingsAdminForm
    list_display = ['id', 'hero_heading', 'contact_section', 'updated_at']
    fields = ['hero_heading', 'hero_description', 'hero_image', 'footer_text', 'contact_section']
    inlines = [HomepageFeatureCardInline]

    def has_add_permission(self, request):
        has_permission = super().has_add_permission(request)
        if not has_permission:
            return False
        return not HomepageSettings.objects.exists()

    def changelist_view(self, request, extra_context=None):
        singleton = HomepageSettings.objects.first()
        if singleton:
            url = reverse('admin:news_homepagesettings_change', args=[singleton.pk])
            return HttpResponseRedirect(url)
        return super().changelist_view(request, extra_context=extra_context)


@admin.action(description='Mark selected inquiries as Read')
def mark_inquiries_read(modeladmin, request, queryset):
    queryset.update(status=HomepageInquiry.STATUS_READ)


@admin.action(description='Mark selected inquiries as Unread')
def mark_inquiries_unread(modeladmin, request, queryset):
    queryset.update(status=HomepageInquiry.STATUS_UNREAD)


@admin.action(description='Archive selected inquiries')
def archive_inquiries(modeladmin, request, queryset):
    queryset.update(status=HomepageInquiry.STATUS_ARCHIVED)


@admin.register(HomepageInquiry)
class HomepageInquiryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'subject', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['full_name', 'email', 'subject', 'message']
    actions = [mark_inquiries_read, mark_inquiries_unread, archive_inquiries]
