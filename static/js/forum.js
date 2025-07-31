// CleanForum - JavaScript для работы с API

class ForumAPI {
    constructor() {
        this.baseURL = '/api';
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    // Posts API
    async getPosts(limit = 20, offset = 0) {
        return this.request(`/posts?limit=${limit}&offset=${offset}`);
    }

    async getPost(postId) {
        return this.request(`/posts/${postId}`);
    }

    async createPost(postData) {
        return this.request('/posts', {
            method: 'POST',
            body: JSON.stringify(postData)
        });
    }

    // Categories API
    async getCategories() {
        return this.request('/categories');
    }

    // Moderator API
    async getPendingPosts() {
        return this.request('/moderator/pending-posts');
    }

    async getSpamStatistics() {
        return this.request('/moderator/spam-statistics');
    }

    async moderatePost(postId, action) {
        return this.request('/moderator/moderate', {
            method: 'POST',
            body: JSON.stringify({
                post_id: postId,
                action: action,
                moderator_id: 'moderator_demo'
            })
        });
    }

    async getSpamAnalysis(postId) {
        return this.request(`/moderator/posts/${postId}/analysis`);
    }

    async getSystemStats() {
        return this.request('/moderator/system-stats');
    }

    async retrainModel() {
        return this.request('/moderator/retrain', { method: 'POST' });
    }
}

const api = new ForumAPI();

// Utility functions
function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);

    if (diffInSeconds < 60) return 'только что';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} мин назад`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} ч назад`;
    return `${Math.floor(diffInSeconds / 86400)} дн назад`;
}

function getSpamBadge(isSpam, spamScore) {
    if (isSpam) {
        return '<span class="badge bg-danger">СПАМ</span>';
    } else if (spamScore > 0.5) {
        return '<span class="badge bg-warning">Подозрительно</span>';
    } else if (spamScore > 0.3) {
        return '<span class="badge bg-info">Проверено</span>';
    }
    return '<span class="badge bg-success">Чисто</span>';
}

// Main page functions
async function loadPosts() {
    try {
        const posts = await api.getPosts();
        const container = document.getElementById('posts-container');

        if (posts.length === 0) {
            container.innerHTML = '<p class="text-muted">Пока нет постов</p>';
            return;
        }

        container.innerHTML = posts.map(post => `
            <div class="card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between">
                        <h5 class="card-title">
                            <a href="/posts/${post.id}" class="text-decoration-none">${post.title}</a>
                        </h5>
                        ${getSpamBadge(post.is_spam, post.spam_score)}
                    </div>
                    <p class="card-text">${post.content.substring(0, 200)}${post.content.length > 200 ? '...' : ''}</p>
                    <div class="row">
                        <div class="col">
                            <small class="text-muted">
                                <i class="fas fa-user"></i> ${post.author_username} • 
                                <i class="fas fa-eye"></i> ${post.view_count} • 
                                <i class="fas fa-comments"></i> ${post.comment_count} •
                                <i class="fas fa-clock"></i> ${timeAgo(post.created_at)}
                            </small>
                        </div>
                        <div class="col-auto">
                            <span class="badge bg-primary">${post.category_name}</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading posts:', error);
        document.getElementById('posts-container').innerHTML = 
            '<div class="alert alert-danger">Ошибка загрузки постов</div>';
    }
}

async function loadCategories() {
    try {
        const categories = await api.getCategories();
        const container = document.getElementById('categories-list');

        if (categories.length === 0) {
            container.innerHTML = '<p class="text-muted">Нет категорий</p>';
            return;
        }

        container.innerHTML = categories.map(cat => `
            <a href="/category/${cat.id}" class="btn btn-outline-primary btn-sm me-2 mb-2">
                <span class="badge" style="background-color: ${cat.color}">&nbsp;</span>
                ${cat.name} (${cat.post_count})
            </a>
        `).join('');

    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// Post Detail page functions
async function loadPostDetail(postId) {
    try {
        const post = await api.getPost(postId);
        const container = document.getElementById('post-detail-container');
        const metaContainer = document.getElementById('post-meta-container');

        document.title = `${post.title} - CleanForum`;

        container.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h1>${post.title}</h1>
                    <hr>
                    <div class="text-muted mb-3">
                        <span><i class="fas fa-user"></i> ${post.author_username}</span> |
                        <span><i class="fas fa-clock"></i> ${timeAgo(post.created_at)}</span> |
                        <span><i class="fas fa-eye"></i> ${post.view_count}</span>
                    </div>
                    <div class="post-content">${post.content.replace(/\n/g, '<br>')}</div>
                </div>
            </div>
        `;

        metaContainer.innerHTML = `
            <p><strong>Категория:</strong> <a href="/category/${post.category_id}">${post.category_name}</a></p>
            <p><strong>Теги:</strong> ${post.tags.map(tag => `<span class="badge bg-secondary">${tag}</span>`).join(' ')}</p>
            <p><strong>Оценка спама:</strong> ${getSpamBadge(post.is_spam, post.spam_score)}</p>
        `;

        await loadComments(postId);

    } catch (error) {
        console.error('Error loading post detail:', error);
        document.getElementById('post-detail-container').innerHTML = '<div class="alert alert-danger">Ошибка загрузки поста.</div>';
    }
}

async function loadComments(postId) {
    try {
        const comments = await api.getPostComments(postId);
        const container = document.getElementById('comments-container');

        if (comments.length === 0) {
            container.innerHTML = '<p class="text-muted">Комментариев пока нет.</p>';
            return;
        }

        container.innerHTML = comments.map(comment => `
            <div class="border-bottom pb-3 mb-3">
                <p>${comment.content}</p>
                <small class="text-muted"><strong>${comment.author_username}</strong> • ${timeAgo(comment.created_at)}</small>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

async function handleCommentForm(postId) {
    const form = document.getElementById('add-comment-form');
    if (!form) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const content = document.getElementById('comment-content').value;

        try {
            await api.createComment({ post_id: postId, content: content });
            showAlert('Комментарий успешно добавлен!', 'success');
            document.getElementById('comment-content').value = '';
            await loadComments(postId); // Перезагружаем комментарии
        } catch (error) {
            console.error('Error creating comment:', error);
            showAlert('Ошибка при добавлении комментария.', 'danger');
        }
    });
}

async function loadSystemStats() {
    try {
        const stats = await api.getSystemStats();
        const container = document.getElementById('system-stats');

        container.innerHTML = `
            <ul class="list-group list-group-flush">
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия Redis
                    <span class="badge bg-primary rounded-pill">${stats.redis_version}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Всего постов
                    <span class="badge bg-info rounded-pill">${stats.total_posts}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Постов в спаме
                    <span class="badge bg-danger rounded-pill">${stats.spam_posts}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Векторов в базе
                    <span class="badge bg-success rounded-pill">${stats.vector_count}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия Python
                    <span class="badge bg-secondary rounded-pill">${stats.python_version}</span>
                </li>
                 <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия FastAPI
                    <span class="badge bg-secondary rounded-pill">${stats.fastapi_version}</span>
                </li>
            </ul>
        `;

    } catch (error) {
        console.error('Error loading system stats:', error);
        document.getElementById('system-stats').innerHTML = '<div class="alert alert-danger">Ошибка загрузки статистики.</div>';
    }
}

// Moderator functions
async function loadModeratorPosts() {
    try {
        const posts = await api.getPendingPosts();
        const container = document.getElementById('pending-posts');

        if (posts.length === 0) {
            container.innerHTML = '<p class="text-success">Нет постов для модерации</p>';
            return;
        }

        container.innerHTML = posts.map(post => `
            <div class="border p-3 mb-3 rounded">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6>${post.title}</h6>
                        <p class="small text-muted">${post.content.substring(0, 100)}...</p>
                        <div>
                            ${getSpamBadge(post.is_spam, post.spam_score)}
                            <span class="small text-muted">Оценка: ${(post.spam_score * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="btn-group-vertical btn-group-sm">
                        <button class="btn btn-success" onclick="moderatePost('${post.id}', 'approve')">
                            <i class="fas fa-check"></i>
                        </button>
                        <button class="btn btn-danger" onclick="moderatePost('${post.id}', 'mark_spam')">
                            <i class="fas fa-ban"></i>
                        </button>
                        <button class="btn btn-info" onclick="showSpamAnalysis('${post.id}')">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading pending posts:', error);
    }
}

async function loadSpamStatistics() {
    try {
        const stats = await api.getSpamStatistics();
        const container = document.getElementById('spam-statistics');

        container.innerHTML = `
            <div class="row text-center">
                <div class="col-6">
                    <h4>${stats.total_posts_analyzed}</h4>
                    <small class="text-muted">Проанализировано</small>
                </div>
                <div class="col-6">
                    <h4>${stats.spam_detected}</h4>
                    <small class="text-muted">Спам заблокирован</small>
                </div>
            </div>
            <hr>
            <div class="mt-3">
                <strong>Статус модели:</strong><br>
                <span class="badge ${stats.classifier_stats.model_loaded ? 'bg-success' : 'bg-danger'}">
                    ${stats.classifier_stats.model_loaded ? 'Загружена' : 'Не загружена'}
                </span>
            </div>
        `;

    } catch (error) {
        console.error('Error loading spam statistics:', error);
    }
}

async function moderatePost(postId, action) {
    try {
        const result = await api.moderatePost(postId, action);

        // Показываем уведомление
        const alertType = action === 'approve' ? 'success' : 'warning';
        showAlert(result.message, alertType);

        // Перезагружаем список
        await loadPendingPosts();

    } catch (error) {
        console.error('Error moderating post:', error);
        showAlert('Ошибка модерации', 'danger');
    }
}

async function showSpamAnalysis(postId) {
    try {
        const analysis = await api.getSpamAnalysis(postId);
        const content = document.getElementById('spam-analysis-content');

        content.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Общая оценка</h6>
                    <p>Оценка спама: <strong>${(analysis.spam_score * 100).toFixed(1)}%</strong></p>
                    <p>Статус: ${getSpamBadge(analysis.is_spam, analysis.spam_score)}</p>
                </div>
                <div class="col-md-6">
                    <h6>Детали анализа</h6>
                    <p>Эвристика: ${(analysis.heuristic_score * 100).toFixed(1)}%</p>
                    <p>Векторный: ${(analysis.vector_score * 100).toFixed(1)}%</p>
                    <p>Похожих постов: ${analysis.similar_posts_count}</p>
                </div>
            </div>
            <div class="mt-3">
                <h6>Причины подозрения:</h6>
                <ul>
                    ${analysis.reasons.map(reason => `<li>${reason}</li>`).join('')}
                </ul>
            </div>
        `;

        const modal = new bootstrap.Modal(document.getElementById('spamAnalysisModal'));
        modal.show();

    } catch (error) {
        console.error('Error loading spam analysis:', error);
    }
}

async function retrainModel() {
    try {
        const result = await api.retrainModel();
        showAlert(result.message, 'info');
    } catch (error) {
        console.error('Error retraining model:', error);
        showAlert('Ошибка запуска переобучения', 'danger');
    }
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.querySelector('main').insertBefore(alertDiv, document.querySelector('main').firstChild);

    // Автоматически скрываем через 5 секунд
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Create Post page functions
async function loadCategoriesIntoSelect() {
    try {
        const categories = await api.getCategories();
        const select = document.getElementById('post-category');
        select.innerHTML = categories.map(cat => `<option value="${cat.id}">${cat.name}</option>`).join('');
    } catch (error) {
        console.error('Error loading categories for select:', error);
    }
}

async function handleCreatePostForm() {
    const form = document.getElementById('create-post-form');
    if (!form) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const postData = {
            title: document.getElementById('post-title').value,
            content: document.getElementById('post-content').value,
            category_id: document.getElementById('post-category').value,
            tags: document.getElementById('post-tags').value.split(',').map(tag => tag.trim()).filter(tag => tag)
        };

        try {
            const newPost = await api.createPost(postData);
            showAlert('Пост успешно создан!', 'success');
            // Перенаправляем на страницу поста через 2 секунды
            setTimeout(() => {
                window.location.href = `/posts/${newPost.id}`;
            }, 2000);
        } catch (error) {
            console.error('Error creating post:', error);
            showAlert('Ошибка при создании поста. Проверьте консоль.', 'danger');
        }
    });
}

// Initialize page content
document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;

    if (path === '/') {
        loadPosts();
        loadCategories();
    } else if (path.startsWith('/create')) {
        loadCategoriesIntoSelect();
        handleCreatePostForm();
    } else if (path.startsWith('/posts/')) {
        const postId = path.split('/').pop();
        loadPostDetail(postId);
        handleCommentForm(postId);
    } else if (path === '/moderator') {
        loadModeratorPosts();
        loadSpamStatistics();
        loadSystemStats();
    }
});