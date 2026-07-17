from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class News(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        # Validate max 5 images
        if self.pk and self.images.count() > 5:
            raise ValidationError("Maximum 5 images allowed")
        # Validate max 5 documents
        if self.pk and self.documents.count() > 5:
            raise ValidationError("Maximum 5 documents allowed")


class NewsImage(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='news/images/')

    def __str__(self):
        return f"{self.news.title} - Image"


class NewsDocument(models.Model):
    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
    ]
    
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to='news/documents/')
    document_type = models.CharField(max_length=10, choices=DOCUMENT_TYPES)

    def __str__(self):
        return f"{self.news.title} - Document"


class GalleryImage(models.Model):
    title = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    image = models.ImageField(upload_to='home_gallery/')
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title or f"Gallery image {self.pk}"


class HomePageContactSection(models.Model):
    section_title = models.CharField(max_length=150, default='Contact our team')
    introductory_text = models.TextField(
        default='Questions, feedback, or partnership requests? We typically respond within 24 business hours.'
    )
    phone_number = models.CharField(max_length=50, default='+1 (234) 567-890')
    email_address = models.EmailField(default='info@aspireacademy.com')
    physical_address = models.TextField(default='145 Aspire Lane, Cityview, State 54321')
    availability_hours = models.CharField(max_length=150, default='Mon - Fri: 8:00 AM - 5:00 PM')
    form_heading = models.CharField(max_length=150, default='Start your inquiry')
    form_description = models.TextField(default='Share your details and our team will get back to you soon.')

    class Meta:
        verbose_name = 'Home Page Contact Section'
        verbose_name_plural = 'Home Page Contact Section'

    def __str__(self):
        return self.section_title


class HomepageSettings(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    hero_heading = models.CharField(max_length=200, default='Aspire Academy')
    hero_description = models.TextField(
        default='We provide a nurturing environment where learners grow academically, socially and personally.'
    )
    hero_image_1 = models.ImageField('Hero Image 1', upload_to='homepage/settings/', blank=True, null=True)
    hero_image_2 = models.ImageField('Hero Image 2', upload_to='homepage/settings/', blank=True, null=True)
    hero_image_3 = models.ImageField('Hero Image 3', upload_to='homepage/settings/', blank=True, null=True)
    hero_image_4 = models.ImageField('Hero Image 4', upload_to='homepage/settings/', blank=True, null=True)
    footer_text = models.TextField(
        default='Premium learning, modern care, and a connected school community.'
    )
    contact_section = models.OneToOneField(
        HomePageContactSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homepage_settings',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Homepage Settings'
        verbose_name_plural = 'Homepage Settings'

    def __str__(self):
        return 'Homepage Settings'

    def clean(self):
        super().clean()
        self.singleton_key = 1
        queryset = type(self).objects.exclude(pk=self.pk)
        if queryset.exists():
            raise ValidationError('Only one Homepage Settings record can exist.')

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        settings = cls.objects.first()
        if settings:
            return settings
        contact = HomePageContactSection.objects.first()
        return cls.objects.create(singleton_key=1, contact_section=contact)


class HomepageFeatureCard(models.Model):
    settings = models.ForeignKey(
        HomepageSettings,
        on_delete=models.CASCADE,
        related_name='feature_cards',
    )
    slug = models.SlugField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='homepage/features/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('settings', 'slug')
        verbose_name = 'Homepage Feature Card'
        verbose_name_plural = 'Homepage Feature Cards'

    def __str__(self):
        return self.title


class HomepageInquiry(models.Model):
    STATUS_UNREAD = 'unread'
    STATUS_READ = 'read'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_UNREAD, 'Unread'),
        (STATUS_READ, 'Read'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=120)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNREAD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Homepage Inquiry'
        verbose_name_plural = 'Homepage Inquiries'

    def __str__(self):
        return f'{self.full_name} - {self.subject}'
