// CleanForum - JavaScript для панели модератора

document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;
    if (path === '/moderator') {
        loadModeratorData();
    }
});

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

async function loadModeratorData() {
    await loadStats();
    await loadModeratorPosts();
    await loadModeratorComments();
}

async function loadStats() {
    try {
        const stats = await api.getSystemStats();
        const contentContainer = document.getElementById('content-stats');
        const systemContainer = document.getElementById('system-stats');

        // Заполняем статистику по контенту
        contentContainer.innerHTML = `
            <ul class="list-group list-group-flush">
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Всего постов
                    <span class="badge bg-primary rounded-pill">${stats.total_posts}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Опубликованных
                    <span class="badge bg-success rounded-pill">${stats.published_posts}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    В спаме
                    <span class="badge bg-danger rounded-pill">${stats.spam_posts}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Процент спама
                    <span class="badge bg-warning rounded-pill">${stats.spam_percentage}%</span>
                </li>
            </ul>
        `;

        // Заполняем системную статистику
        systemContainer.innerHTML = `
            <ul class="list-group list-group-flush">
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия Redis
                    <span class="badge bg-secondary rounded-pill">${stats.redis_version}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Используемая память
                    <span class="badge bg-info rounded-pill">${stats.used_memory}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Количество векторов
                    <span class="badge bg-success rounded-pill">${stats.vector_count}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия Python
                    <span class="badge bg-dark rounded-pill">${stats.python_version}</span>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия FastAPI
                    <span class="badge bg-dark rounded-pill">${stats.fastapi_version}</span>
                </li>
                 <li class="list-group-item d-flex justify-content-between align-items-center">
                    Версия приложения
                    <span class="badge bg-dark rounded-pill">${stats.app_version}</span>
                </li>
            </ul>
        `;

    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('content-stats').innerHTML = '<div class="alert alert-danger">Ошибка загрузки статистики.</div>';
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
                        <h6>
                            <a href="/posts/${post.id}" target="_blank" class="text-decoration-none">${post.title}</a>
                        </h6>
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
                        <button class="btn btn-info" onclick="showPostSpamAnalysis('${post.id}')">
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



async function moderatePost(postId, action) {
    try {
        const result = await api.moderatePost(postId, action);
        showAlert(result.message, action === 'approve' ? 'success' : 'warning');
        await loadModeratorPosts();
    } catch (error) {
        console.error('Error moderating post:', error);
        showAlert('Ошибка модерации поста', 'danger');
    }
}

async function showPostSpamAnalysis(postId) {
    try {
        const analysis = await api.getPostSpamAnalysis(postId);
        displaySpamAnalysis(analysis);
    } catch (error) {
        console.error('Error loading post spam analysis:', error);
        showAlert('Ошибка загрузки анализа поста', 'danger');
    }
}

async function loadModeratorComments() {
    try {
        const comments = await api.getPendingComments();
        const container = document.getElementById('pending-comments');
        if (comments.length === 0) {
            container.innerHTML = '<p class="text-success">Нет комментариев для модерации</p>';
            return;
        }
        container.innerHTML = comments.map(comment => `
            <div class="border p-3 mb-3 rounded">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <p class="small">
                            <a href="/posts/${comment.post_id}" target="_blank" class="text-decoration-none text-muted">
                                ${comment.content.substring(0, 150)}...
                            </a>
                        </p>
                        <div>
                            ${getSpamBadge(comment.is_spam, comment.spam_score)}
                            <span class="small text-muted">Оценка: ${(comment.spam_score * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="btn-group-vertical btn-group-sm">
                        <button class="btn btn-success" onclick="moderateComment('${comment.id}', 'approve')"><i class="fas fa-check"></i></button>
                        <button class="btn btn-danger" onclick="moderateComment('${comment.id}', 'mark_spam')"><i class="fas fa-ban"></i></button>
                        <button class="btn btn-info" onclick="showCommentSpamAnalysis('${comment.id}')"><i class="fas fa-search"></i></button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading pending comments:', error);
        document.getElementById('pending-comments').innerHTML = '<p class="text-danger">Ошибка загрузки комментариев.</p>';
    }
}

async function moderateComment(commentId, action) {
    try {
        const result = await api.moderateComment(commentId, action);
        showAlert(result.message, action === 'approve' ? 'success' : 'warning');
        await loadModeratorComments();
    } catch (error) {
        console.error('Error moderating comment:', error);
        showAlert('Ошибка модерации комментария', 'danger');
    }
}

async function showCommentSpamAnalysis(commentId) {
    try {
        const analysis = await api.getCommentSpamAnalysis(commentId);
        displaySpamAnalysis(analysis);
    } catch (error) {
        console.error('Error loading comment spam analysis:', error);
        showAlert('Ошибка загрузки анализа комментария', 'danger');
    }
}

function displaySpamAnalysis(analysis) {
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
                <p>Похожих элементов: ${analysis.similar_posts_count}</p>
            </div>
        </div>
        <div class="mt-3">
            <h6>Причины подозрения:</h6>
            <ul>
                ${analysis.reasons.map(reason => `<li>${reason}</li>`).join('') || '<li>Причин не найдено</li>'}
            </ul>
        </div>
    `;
    const modal = new bootstrap.Modal(document.getElementById('spamAnalysisModal'));
    modal.show();
}

async function analyzeAllPosts() {
    try {
        const result = await api.analyzeAllPosts();
        showAlert(result.message, 'info');
    } catch (error) {
        console.error('Error analyzing all posts:', error);
        showAlert('Ошибка запуска анализа', 'danger');
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

async function showLogs() {
    try {
        const logs = await api.getLogs();
        const content = document.getElementById('logs-content');
        content.textContent = logs;

        const modal = new bootstrap.Modal(document.getElementById('logsModal'));
        modal.show();

    } catch (error) {
        console.error('Error loading logs:', error);
        showAlert('Ошибка загрузки логов', 'danger');
    }
}
