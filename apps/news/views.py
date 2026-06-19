from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import News, NewsImage, NewsDocument


@login_required
def news_list(request):
    # display news for both students and teachers
    news = News.objects.all()
    return render(request, 'news/news_list.html', {'news': news})


@login_required
def news_detail(request, pk):
    news = get_object_or_404(News, pk=pk)
    return render(request, 'news/news_detail.html', {'news': news})


@login_required
def manage_news(request):
    # admin only - list all news for management
    if not request.user.is_staff:
        return redirect('accounts:accounts_home')
    
    news = News.objects.all()
    return render(request, 'news/manage_news.html', {'news': news})


@login_required
def create_news(request):
    # admin only - create new news
    if not request.user.is_staff:
        return redirect('accounts:accounts_home')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        
        if not title or not content:
            messages.error(request, 'Title and content are required.')
            return render(request, 'news/create_news.html')
        
        news = News.objects.create(
            title=title,
            content=content,
            created_by=request.user
        )
        
        # handle image uploads (max 5)
        images = request.FILES.getlist('images')
        for i, image in enumerate(images[:5]):
            NewsImage.objects.create(news=news, image=image)
        
        # handle document uploads (max 5)
        documents = request.FILES.getlist('documents')
        for doc in documents[:5]:
            # determine document type from extension
            if doc.name.endswith('.pdf'):
                doc_type = 'pdf'
            elif doc.name.endswith('.docx') or doc.name.endswith('.doc'):
                doc_type = 'docx'
            else:
                continue  # skip unsupported formats
            
            NewsDocument.objects.create(news=news, document=doc, document_type=doc_type)
        
        messages.success(request, 'News created successfully')
        return redirect('manage_news')
    
    return render(request, 'news/create_news.html')


@login_required
def edit_news(request, pk):
    # admin only - edit existing news
    if not request.user.is_staff:
        return redirect('accounts:accounts_home')
    
    news = get_object_or_404(News, pk=pk)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        
        if not title or not content:
            messages.error(request, 'Title and content are required.')
            return render(request, 'news/edit_news.html', {'news': news})
        
        news.title = title
        news.content = content
        news.save()
        
        # handle new image uploads (max 5 total)
        if request.FILES.getlist('images'):
            images = request.FILES.getlist('images')
            current_count = news.images.count()
            for i, image in enumerate(images):
                if current_count + i >= 5:
                    break
                NewsImage.objects.create(news=news, image=image)
        
        # handle new document uploads (max 5 total)
        if request.FILES.getlist('documents'):
            documents = request.FILES.getlist('documents')
            current_count = news.documents.count()
            for i, doc in enumerate(documents):
                if current_count + i >= 5:
                    break
                if doc.name.endswith('.pdf'):
                    doc_type = 'pdf'
                elif doc.name.endswith('.docx') or doc.name.endswith('.doc'):
                    doc_type = 'docx'
                else:
                    continue
                NewsDocument.objects.create(news=news, document=doc, document_type=doc_type)
        
        messages.success(request, 'News updated successfully')
        return redirect('manage_news')
    
    return render(request, 'news/edit_news.html', {'news': news})


@login_required
def delete_news(request, pk):
    # admin only - delete news
    if not request.user.is_staff:
        return redirect('accounts:accounts_home')
    
    news = get_object_or_404(News, pk=pk)
    news.delete()
    messages.success(request, 'News deleted')
    return redirect('manage_news')


@login_required
def delete_image(request, news_pk, image_pk):
    # admin only - delete specific image from news
    if not request.user.is_staff:
        return redirect('accounts:accounts_home')
    
    image = get_object_or_404(NewsImage, pk=image_pk, news_id=news_pk)
    image.delete()
    messages.success(request, 'Image deleted')
    return redirect('edit_news', pk=news_pk)


@login_required
def delete_document(request, news_pk, doc_pk):
    # admin only - delete specific document from news
    if not request.user.is_staff:
        return redirect('accounts:accounts_home')
    
    document = get_object_or_404(NewsDocument, pk=doc_pk, news_id=news_pk)
    document.delete()
    messages.success(request, 'Document deleted')
    return redirect('edit_news', pk=news_pk)
