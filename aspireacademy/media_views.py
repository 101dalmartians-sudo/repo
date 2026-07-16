import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils._os import safe_join


def serve_media(request, path):
    if not path:
        raise Http404('File not found.')

    normalized_path = Path(path)
    if normalized_path.is_absolute() or '..' in normalized_path.parts:
        raise Http404('File not found.')

    full_path = safe_join(str(settings.MEDIA_ROOT), path)
    file_path = Path(full_path)
    if not file_path.exists() or not file_path.is_file():
        raise Http404('File not found.')

    content_type, encoding = mimetypes.guess_type(str(file_path))
    response = FileResponse(file_path.open('rb'), content_type=content_type or 'application/octet-stream')
    if encoding:
        response['Content-Encoding'] = encoding
    response['Cache-Control'] = 'public, max-age=3600'
    return response