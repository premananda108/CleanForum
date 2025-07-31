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
    async getPosts(limit = 20, offset = 0, categoryId = null) {
        let endpoint = `/posts?limit=${limit}&offset=${offset}`;
        if (categoryId) {
            endpoint += `&category_id=${categoryId}`;
        }
        return this.request(endpoint);
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

    // Search API
    async searchPosts(query) {
        return this.request(`/search?q=${encodeURIComponent(query)}`);
    }

    // Comments API
    async createComment(commentData) {
        return this.request('/comments', {
            method: 'POST',
            body: JSON.stringify(commentData)
        });
    }

    async getPostComments(postId) {
        return this.request(`/posts/${postId}/comments`);
    }

    // Moderator API
    async getPendingPosts() {
        return this.request('/moderator/pending-posts');
    }

    async moderatePost(postId, action) {
        return this.request('/moderator/moderate-post', {
            method: 'POST',
            body: JSON.stringify({
                entity_id: postId,
                action: action
            })
        });
    }

    async getPostSpamAnalysis(postId) {
        return this.request(`/moderator/posts/${postId}/analysis`);
    }

    async getPendingComments() {
        return this.request('/moderator/pending-comments');
    }

    async moderateComment(commentId, action) {
        return this.request('/moderator/moderate-comment', {
            method: 'POST',
            body: JSON.stringify({
                entity_id: commentId,
                action: action
            })
        });
    }

    async getCommentSpamAnalysis(commentId) {
        return this.request(`/moderator/comments/${commentId}/analysis`);
    }

    async getSystemStats() {
        return this.request('/moderator/system-stats');
    }

    async analyzeAllPosts() {
        return this.request('/moderator/analyze-all-posts', { method: 'POST' });
    }

    async retrainModel() {
        return this.request('/moderator/retrain', { method: 'POST' });
    }

    async getLogs() {
        const response = await fetch(`${this.baseURL}/logs`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.text();
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
async function loadPosts(categoryId = null) {
    try {
        const posts = await api.getPosts(20, 0, categoryId);
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

        // Загружаем и отображаем похожие посты
        if (post.similar_posts) {
            renderSimilarPosts(post.similar_posts);
        }

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

function renderSimilarPosts(posts) {
    const container = document.getElementById('similar-posts-container');
    if (!container) return;

    if (!posts || posts.length === 0) {
        container.innerHTML = '<p class="text-muted small">Похожих постов не найдено.</p>';
        return;
    }

    container.innerHTML = `
        <ul class="list-unstyled">
            ${posts.map(post => `
                <li class="mb-2">
                    <a href="/posts/${post.id}" class="text-decoration-none small">${post.title}</a>
                    <div class="text-muted small">
                        <i class="fas fa-user"></i> ${post.author_username}
                    </div>
                </li>
            `).join('')}
        </ul>
    `;
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

// Search page functions
async function handleSearchForm() {
    const form = document.getElementById('search-form');
    const resultsContainer = document.getElementById('search-results-container');
    const queryInput = document.getElementById('search-query');

    if (!form) return;

    // Check for query in URL and trigger search on page load
    const urlParams = new URLSearchParams(window.location.search);
    const q = urlParams.get('q');
    if (q) {
        queryInput.value = q;
        await performSearch(q);
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const query = queryInput.value.trim();

        // Update URL without reloading
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('q', query);
        window.history.pushState({path: newUrl.href}, '', newUrl.href);

        await performSearch(query);
    });

    async function performSearch(query) {
        if (query.length < 2) {
            resultsContainer.innerHTML = '<p class="text-warning">Поисковый запрос должен содержать минимум 2 символа.</p>';
            return;
        }

        resultsContainer.innerHTML = '<p class="text-muted">Идет поиск...</p>';

        try {
            const posts = await api.searchPosts(query);
            renderSearchResults(posts, resultsContainer);
        } catch (error) {
            console.error('Ошибка поиска:', error);
            resultsContainer.innerHTML = '<div class="alert alert-danger">Произошла ошибка во время поиска.</div>';
        }
    }
}

function renderSearchResults(posts, container) {
    if (posts.length === 0) {
        container.innerHTML = '<p class="text-muted">Ничего не найдено.</p>';
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
    } else if (path.startsWith('/search')) {
        handleSearchForm();
    }
});