import mimetypes
import os

from django.db import models


class Assignment(models.Model):
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=128)
    target_class = models.CharField(max_length=64)
    due_date = models.DateTimeField()
    file_attachment = models.FileField(upload_to='assignments/')
    original_filename = models.CharField(max_length=255, blank=True)
    file_content_type = models.CharField(max_length=127, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        'teachers.TeacherProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assignments'
    )

    def __str__(self):
        return self.title

    @property
    def attachment_filename(self):
        if self.original_filename:
            return self.original_filename
        return os.path.basename(self.file_attachment.name) if self.file_attachment else ''

    @property
    def attachment_extension(self):
        return os.path.splitext(self.attachment_filename)[1].lower()

    @property
    def attachment_content_type(self):
        if self.file_content_type:
            return self.file_content_type
        guessed, _ = mimetypes.guess_type(self.attachment_filename)
        return guessed or 'application/octet-stream'

    @property
    def attachment_size_bytes(self):
        if self.file_size is not None:
            return self.file_size
        if not self.file_attachment:
            return None
        try:
            return self.file_attachment.size
        except (OSError, ValueError):
            return None

    @property
    def attachment_icon(self):
        extension = self.attachment_extension
        if extension == '.pdf':
            return '📄'
        if extension in {'.doc', '.docx'}:
            return '📘'
        if extension in {'.xls', '.xlsx'}:
            return '📊'
        if extension in {'.ppt', '.pptx'}:
            return '🖥️'
        if extension in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
            return '🖼️'
        if extension == '.zip':
            return '🗜️'
        return '📎'
