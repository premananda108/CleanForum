// CleanForum - JavaScript for the moderator panel

document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;
    if (path === '/moderator') {
        loadModeratorData();
    }
});

function getSpamBadge(entity) {
    if (entity && entity.status === 'moderated') {
        return '<span class="px-2 py-1 text-xs font-semibold text-white bg-blue-500 rounded-full">Verified</span>';
    }
    if (entity && entity.is_spam) {
        return '<span class="px-2 py-1 text-xs font-semibold text-white bg-red-500 rounded-full">SPAM</span>';
    }
    if (entity && entity.spam_score > 0.5) {
        return '<span class="px-2 py-1 text-xs font-semibold text-black bg-yellow-400 rounded-full">Suspicious</span>';
    }
    return '<span class="px-2 py-1 text-xs font-semibold text-white bg-green-500 rounded-full">Clean</span>';
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

        const statItem = (label, value, color) => `
            <div class="flex justify-between items-center py-2">
                <span class="text-sm text-gray-600">${label}</span>
                <span class="px-3 py-1 text-xs font-bold text-white ${color} rounded-full">${value}</span>
            </div>
        `;

        contentContainer.innerHTML = `
            ${statItem('Total Posts', stats.total_posts, 'bg-blue-500')}
            ${statItem('Published', stats.published_posts, 'bg-green-500')}
            ${statItem('In Spam', stats.spam_posts, 'bg-red-500')}
            ${statItem('Spam Percentage', `${stats.spam_percentage}%`, 'bg-yellow-500')}
        `;

        systemContainer.innerHTML = `
            ${statItem('Redis Version', stats.redis_version, 'bg-gray-600')}
            ${statItem('Used Memory', stats.used_memory, 'bg-blue-400')}
            ${statItem('Vector Count', stats.vector_count, 'bg-green-400')}
            ${statItem('Python Version', stats.python_version, 'bg-gray-800')}
            ${statItem('FastAPI Version', stats.fastapi_version, 'bg-gray-800')}
            ${statItem('App Version', stats.app_version, 'bg-gray-800')}
        `;

    } catch (error) {
        console.error('Error loading stats:', error);
        const errorHtml = '<div class="p-4 text-sm text-red-700 bg-red-100 rounded-lg" role="alert">Error loading statistics.</div>';
        document.getElementById('content-stats').innerHTML = errorHtml;
        document.getElementById('system-stats').innerHTML = errorHtml;
    }
}

async function loadModeratorPosts() {
    try {
        const posts = await api.getPendingPosts();
        const container = document.getElementById('pending-posts');

        if (posts.length === 0) {
            container.innerHTML = '<p class="text-green-600 font-medium">No posts for moderation</p>';
            return;
        }

        container.innerHTML = posts.map(post => `
            <div class="bg-gray-50 border border-gray-200 p-4 rounded-xl">
                <div class="flex justify-between items-start">
                    <div class="flex-grow">
                        <h6 class="font-bold text-gray-800">
                            <a href="/posts/${post.id}" target="_blank" class="hover:text-primary-600 transition">${post.title}</a>
                        </h6>
                        <p class="text-sm text-gray-600 mt-1">${post.content.substring(0, 100)}...</p>
                        <div class="mt-3 flex items-center space-x-2">
                            ${getSpamBadge(post)}
                            <span class="text-xs text-gray-500">Score: <strong>${(post.spam_score * 100).toFixed(1)}%</strong></span>
                        </div>
                    </div>
                    <div class="flex flex-col space-y-2 ml-4">
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-green-100 text-green-600 hover:bg-green-200 transition" onclick="moderatePost('${post.id}', 'approve')">
                            <i class="fas fa-check"></i>
                        </button>
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition" onclick="moderatePost('${post.id}', 'mark_spam')">
                            <i class="fas fa-ban"></i>
                        </button>
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition" onclick="deletePost('${post.id}')">
                            <i class="fas fa-trash"></i>
                        </button>
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-blue-100 text-blue-600 hover:bg-blue-200 transition" onclick="showPostSpamAnalysis('${post.id}')">
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
        showAlert('Error moderating post', 'danger');
    }
}

async function deletePost(postId) {
    if (!confirm('Are you sure you want to delete this post?')) {
        return;
    }
    try {
        await api.deletePost(postId);
        showAlert('Post deleted successfully', 'success');
        await loadModeratorPosts();
    } catch (error) {
        console.error('Error deleting post:', error);
        showAlert('Error deleting post', 'danger');
    }
}

async function showPostSpamAnalysis(postId) {
    try {
        const analysis = await api.getPostSpamAnalysis(postId);
        displaySpamAnalysis(analysis);
    } catch (error) {
        console.error('Error loading post spam analysis:', error);
        showAlert('Error loading post analysis', 'danger');
    }
}

async function loadModeratorComments() {
    try {
        const comments = await api.getPendingComments();
        const container = document.getElementById('pending-comments');
        if (comments.length === 0) {
            container.innerHTML = '<p class="text-green-600 font-medium">No comments for moderation</p>';
            return;
        }
        container.innerHTML = comments.map(comment => `
            <div class="bg-gray-50 border border-gray-200 p-4 rounded-xl">
                <div class="flex justify-between items-start">
                    <div class="flex-grow">
                        <p class="text-sm text-gray-700">
                            <a href="/posts/${comment.post_id}" target="_blank" class="hover:text-primary-600 transition text-gray-600">
                                ${comment.content.substring(0, 150)}...
                            </a>
                        </p>
                        <div class="mt-3 flex items-center space-x-2">
                            ${getSpamBadge(comment)}
                            <span class="text-xs text-gray-500">Score: <strong>${(comment.spam_score * 100).toFixed(1)}%</strong></span>
                        </div>
                    </div>
                    <div class="flex flex-col space-y-2 ml-4">
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-green-100 text-green-600 hover:bg-green-200 transition" onclick="moderateComment('${comment.id}', 'approve')"><i class="fas fa-check"></i></button>
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition" onclick="moderateComment('${comment.id}', 'mark_spam')"><i class="fas fa-ban"></i></button>
                        <button class="w-10 h-10 flex items-center justify-center rounded-lg bg-blue-100 text-blue-600 hover:bg-blue-200 transition" onclick="showCommentSpamAnalysis('${comment.id}')"><i class="fas fa-search"></i></button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading pending comments:', error);
        document.getElementById('pending-comments').innerHTML = '<p class="text-red-600">Error loading comments.</p>';
    }
}

async function moderateComment(commentId, action) {
    try {
        const result = await api.moderateComment(commentId, action);
        showAlert(result.message, action === 'approve' ? 'success' : 'warning');
        await loadModeratorComments();
    } catch (error) {
        console.error('Error moderating comment:', error);
        showAlert('Error moderating comment', 'danger');
    }
}

async function showCommentSpamAnalysis(commentId) {
    try {
        const analysis = await api.getCommentSpamAnalysis(commentId);
        displaySpamAnalysis(analysis);
    } catch (error) {
        console.error('Error loading comment spam analysis:', error);
        showAlert('Error loading comment analysis', 'danger');
    }
}

function displaySpamAnalysis(analysis) {
    const content = document.getElementById('spam-analysis-content');

    let neighborsHtml = '';
    if (analysis.neighbors && analysis.neighbors.length > 0) {
        neighborsHtml = `
            <div class="mt-6 border-t pt-4">
                <h6 class="font-bold text-gray-700 mb-2">Similar items (influencing the score):</h6>
                <div class="space-y-2">
                    ${analysis.neighbors.map(neighbor => `
                        <div class="p-2 bg-gray-100 rounded-lg text-sm">
                            <a href="/posts/${neighbor.id}" target="_blank" class="text-blue-600 hover:underline">${neighbor.title || 'Comment without a title'}</a>
                            <div class="flex items-center justify-between mt-1">
                                <!-- Use getSpamBadge for consistency -->
                                ${getSpamBadge(neighbor)}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    content.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-gray-50 p-4 rounded-lg">
                <h6 class="font-bold text-gray-700 mb-2">Overall Score</h6>
                <p class="text-gray-600">Spam score: <strong class="text-lg text-gray-900">${(analysis.spam_score * 100).toFixed(1)}%</strong></p>
                <div class="mt-2">Status: ${getSpamBadge(analysis)}</div>
            </div>
            <div class="bg-gray-50 p-4 rounded-lg">
                <h6 class="font-bold text-gray-700 mb-2">Analysis Details</h6>
                <p class="text-sm text-gray-600">Heuristic: <span class="font-semibold">${(analysis.heuristic_score * 100).toFixed(1)}%</span></p>
                <p class="text-sm text-gray-600">Vector: <span class="font-semibold">${(analysis.vector_score * 100).toFixed(1)}%</span> (Prediction: ${analysis.vector_prediction})</p>
                <p class="text-sm text-gray-600">Vector confidence: <span class="font-semibold">${(analysis.vector_confidence * 100).toFixed(1)}%</span></p>
            </div>
        </div>
        <div class="mt-6">
            <h6 class="font-bold text-gray-700 mb-2">Reasons for suspicion:</h6>
            <ul class="list-disc list-inside space-y-1 text-gray-600">
                ${analysis.reasons.map(reason => `<li>${reason}</li>`).join('') || '<li>No reasons found</li>'}
            </ul>
        </div>
        ${neighborsHtml}
    `;
    showModal('spamAnalysisModal');
}

async function analyzeAllPosts() {
    try {
        const result = await api.analyzeAllPosts();
        showAlert(result.message, 'info');
    } catch (error) {
        console.error('Error analyzing all posts:', error);
        showAlert('Error starting analysis', 'danger');
    }
}

async function retrainModel() {
    try {
        const result = await api.retrainModel();
        showAlert(result.message, 'info');
    } catch (error) {
        console.error('Error retraining model:', error);
        showAlert('Error starting retraining', 'danger');
    }
}

async function showLogs() {
    try {
        const logs = await api.getLogs();
        const content = document.getElementById('logs-content');
        content.textContent = logs;
        showModal('logsModal');
    } catch (error) {
        console.error('Error loading logs:', error);
        showAlert('Error loading logs', 'danger');
    }
}
