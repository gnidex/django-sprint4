from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DeleteView, UpdateView

from .forms import CommentForm, CreationForm, EditProfileForm, PostForm
from .models import Category, Comment, Post

User = get_user_model()

POSTS_PER_PAGE = 10


def filter_published(posts):
    """Возвращает опубликованные публикации, доступные всем."""
    return posts.filter(
        is_published=True,
        pub_date__lte=timezone.now(),
        category__is_published=True,
    ).annotate(
        comment_count=Count('comments')
    ).order_by('-pub_date')


def paginate(request, posts):
    """Разбивает список публикаций на страницы."""
    return Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get('page'))


def index(request):
    """Главная страница: лента опубликованных публикаций."""
    page_obj = paginate(request, filter_published(Post.objects.all()))
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def post_detail(request, id):
    """Страница отдельной публикации со списком комментариев."""
    post = get_object_or_404(Post, pk=id)
    if request.user != post.author:
        if (
            not post.is_published
            or post.pub_date > timezone.now()
            or post.category is None
            or not post.category.is_published
        ):
            raise Http404
    context = {
        'post': post,
        'comments': post.comments.select_related('author'),
        'form': CommentForm(),
    }
    return render(request, 'blog/detail.html', context)


def category_posts(request, category_slug):
    """Страница публикаций в категории."""
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    page_obj = paginate(
        request, filter_published(category.posts.all())
    )
    return render(
        request, 'blog/category.html',
        {'category': category, 'page_obj': page_obj}
    )


def profile(request, username):
    """Страница пользователя со списком его публикаций."""
    profile = get_object_or_404(User, username=username)
    posts = Post.objects.filter(author=profile).annotate(
        comment_count=Count('comments')
    ).order_by('-pub_date')
    if request.user != profile:
        posts = posts.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
        )
    page_obj = paginate(request, posts)
    return render(
        request, 'blog/profile.html',
        {'profile': profile, 'page_obj': page_obj}
    )


@login_required
def edit_profile(request):
    """Редактирование профиля текущего пользователя."""
    form = EditProfileForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'registration/registration_form.html',
                  {'form': form})


def registration(request):
    """Регистрация нового пользователя."""
    form = CreationForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('login')
    return render(request, 'registration/registration_form.html',
                  {'form': form})


@login_required
def create_post(request):
    """Создание новой публикации."""
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
    )
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
def edit_post(request, post_id):
    """Редактирование публикации (только автором)."""
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', id=post_id)
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
        instance=post,
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', id=post_id)
    return render(request, 'blog/create.html', {'form': form})


@login_required
def delete_post(request, post_id):
    """Удаление публикации (только автором или админом)."""
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user and not request.user.is_staff:
        return redirect('blog:post_detail', id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:index')
    form = PostForm(instance=post)
    return render(request, 'blog/create.html', {'form': form})


@login_required
def add_comment(request, post_id):
    """Добавление комментария к публикации."""
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', id=post_id)


class CommentEditView(LoginRequiredMixin, UpdateView):
    """Редактирование комментария (только автором)."""

    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if comment.author != request.user:
            return redirect('blog:post_detail', id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'id': self.object.post_id})


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление комментария (только автором)."""

    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if comment.author != request.user:
            return redirect('blog:post_detail', id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'id': self.object.post_id})
