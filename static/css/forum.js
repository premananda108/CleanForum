// Advanced Forum - JavaScript для работы с API

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

// Moderator functions
async function loadPendingPosts() {
    try {
        const posts = await api.getPendingPosts();
        const container = document.getElementById('pending-posts');

        if (posts.length === 0) {
            container.innerHTML = '<p class="text-success">Нет подозрительных постов</p>';
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

// Initialize page content
document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;

    if (path === '/') {
        loadPosts();
        loadCategories();
    } else if (path === '/moderator') {
        loadPendingPosts();
        loadSpamStatistics();
    }
});