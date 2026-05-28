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
