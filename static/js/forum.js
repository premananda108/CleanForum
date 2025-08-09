// CleanForum - JavaScript for API interaction (Tailwind Version)

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
            // Try to get a detailed error message from the response body
            try {
                const errorData = await response.json();
                // FastAPI often uses the 'detail' field for errors
                const message = errorData.detail || `HTTP error! status: ${response.status}`;
                const error = new Error(message);
                error.response = response; // Attach the response for additional context
                throw error;
            } catch (e) {
                // If the response body is not JSON or is empty, throw a generic error
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }

        if (response.status === 204) {
            return null;
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

    async deletePost(postId) {
        return this.request(`/posts/${postId}`, {
            method: 'DELETE'
        });
    }

    async updatePost(postId, postData) {
        return this.request(`/posts/${postId}`, {
            method: 'PUT',
            body: JSON.stringify(postData)
        });
    }

    // User API
    async getMe() {
        return this.request('/users/me');
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
    async getPendingPosts(limit = 50, status = 'published', moderation = 'not_moderated', offset = 0) {
        return this.request(`/moderator/pending-posts?limit=${limit}&status=${status}&moderation=${moderation}&offset=${offset}`);
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

    async getPendingComments(limit = 50, status = 'published', offset = 0) {
        return this.request(`/moderator/pending-comments?limit=${limit}&status=${status}&offset=${offset}`);
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

    if (diffInSeconds < 60) return 'just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} min ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} h ago`;
    return `${Math.floor(diffInSeconds / 86400)} d ago`;
}

function getSpamBadge(isSpam, spamScore) {
    if (isSpam) {
        return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><i class="fas fa-ban mr-1"></i>SPAM</span>';
    } else if (spamScore > 0.5) {
        return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"><i class="fas fa-exclamation-triangle mr-1"></i>Suspicious</span>';
    } else if (spamScore > 0.3) {
        return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"><i class="fas fa-check-circle mr-1"></i>Verified</span>';
    }
    return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><i class="fas fa-shield-alt mr-1"></i>Clean</span>';
}

// State variables for pagination
let currentPage = 1;
const POSTS_PER_PAGE = 20;

// Main page functions
async function loadPosts({ page = 1, categoryId = null } = {}) {
    currentPage = page;
    const offset = (currentPage - 1) * POSTS_PER_PAGE;

    try {
        const response = await api.getPosts(POSTS_PER_PAGE, offset, categoryId);
        const posts = response.posts;
        const totalPosts = response.total;

        const container = document.getElementById('posts-container');

        if (!container) return; // Exit if container not found

        if (posts.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-comments text-gray-400 text-2xl"></i>
                    </div>
                    <p class="text-gray-500 text-lg">No posts yet</p>
                    <p class="text-gray-400 text-sm">Be the first to create a post!</p>
                </div>
            `;
            // Still render pagination to clear it if it exists
            renderPagination(0, categoryId);
            return;
        }

        container.innerHTML = posts.map(post => {
            const renderedHtml = marked.parse(post.content);
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = renderedHtml;
            const plainContent = tempDiv.textContent || tempDiv.innerText || '';

            return `
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 overflow-hidden group">
                <div class="p-6">
                    <div class="flex items-start justify-between mb-4">
                        <h3 class="text-xl font-bold text-gray-800 group-hover:text-blue-600 transition-colors flex-1 mr-4">
                            <a href="/posts/${post.id}" class="hover:underline">${post.title}</a>
                        </h3>
                        ${getSpamBadge(post.is_spam, post.spam_score)}
                    </div>

                    <p class="text-gray-600 mb-4 leading-relaxed break-words">${plainContent.substring(0, 200)}${plainContent.length > 200 ? '...' : ''}</p>

                    <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                        <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-gray-500">
                            <span class="flex items-center shrink-0">
                                <i class="fas fa-user mr-1.5 text-blue-500"></i>
                                ${post.author_username}
                            </span>
                            <span class="flex items-center shrink-0">
                                <i class="fas fa-eye mr-1.5 text-green-500"></i>
                                ${post.view_count}
                            </span>
                            <span class="flex items-center shrink-0">
                                <i class="fas fa-comments mr-1.5 text-purple-500"></i>
                                ${post.comment_count}
                            </span>
                            <span class="flex items-center shrink-0">
                                <i class="fas fa-clock mr-1.5 text-orange-500"></i>
                                ${timeAgo(post.created_at)}
                            </span>
                        </div>
                        <a href="/category/${post.category_id}" class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors shrink-0">
                            ${post.category_name}
                        </a>
                    </div>
                </div>
            </div>
            `;
        }).join('');

        renderPagination(totalPosts, categoryId);

    } catch (error) {
        console.error('Error loading posts:', error);
        document.getElementById('posts-container').innerHTML =
            `<div class="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
                <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                <p class="text-red-700 font-medium">Error loading posts</p>
                <p class="text-red-600 text-sm">Try refreshing the page</p>
            </div>`;
    }
}

function renderPagination(totalPosts, categoryId) {
    const paginationContainer = document.getElementById('pagination-container');
    if (!paginationContainer) return;

    const totalPages = Math.ceil(totalPosts / POSTS_PER_PAGE);

    if (totalPages <= 1) {
        paginationContainer.innerHTML = ''; // No pagination needed for a single page
        return;
    }

    const categoryIdJSON = JSON.stringify(categoryId);

    let paginationHTML = '<div class="flex justify-between items-center mt-6 pt-4 border-t border-gray-100">';

    // Previous button
    paginationHTML += `
        <button
            onclick="loadPosts({page: ${currentPage - 1}, categoryId: ${categoryIdJSON}})"
            class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
            ${currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-arrow-left mr-2"></i>Previous
        </button>
    `;

    // Page info
    paginationHTML += `<span class="text-gray-600 font-medium">Page ${currentPage} of ${totalPages}</span>`;

    // Next button
    paginationHTML += `
        <button
            onclick="loadPosts({page: ${currentPage + 1}, categoryId: ${categoryIdJSON}})"
            class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
            ${currentPage >= totalPages ? 'disabled' : ''}>
            Next<i class="fas fa-arrow-right ml-2"></i>
        </button>
    `;

    paginationHTML += '</div>';
    paginationContainer.innerHTML = paginationHTML;
}

async function loadCategories() {
    try {
        const categories = await api.getCategories();
        const container = document.getElementById('categories-list');

        if (categories.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-center py-4">No categories</p>';
            return;
        }

        container.innerHTML = categories.map(cat => `
            <a href="/category/${cat.id}"
               class="flex items-center justify-between p-3 rounded-xl hover:bg-gray-50 transition-colors group">
                <div class="flex items-center space-x-3">
                    <div class="w-3 h-3 rounded-full" style="background-color: ${cat.color}"></div>
                    <span class="font-medium text-gray-700 group-hover:text-blue-600">${cat.name}</span>
                </div>
                <span class="bg-gray-100 text-gray-600 px-2 py-1 rounded-lg text-xs font-medium">${cat.post_count}</span>
            </a>
        `).join('');

    } catch (error) {
        console.error('Error loading categories:', error);
        const container = document.getElementById('categories-list');
        if (container) {
            container.innerHTML = `
                <div class="p-4 text-sm text-red-700 bg-red-100 rounded-xl" role="alert">
                    <p class="font-bold flex items-center">
                        <i class="fas fa-exclamation-triangle mr-2"></i>
                        Error
                    </p>
                    <p>Could not load categories. Please try again later.</p>
                </div>
            `;
        }
    }
}

// Post Detail page functions
async function loadPostDetail(postId) {
    try {
        // Load post data and current user in parallel
        const [post, currentUser] = await Promise.all([
            api.getPost(postId),
            api.getMe()
        ]);

        const container = document.getElementById('post-detail-container');
        const metaContainer = document.getElementById('post-meta-container');

        document.title = `${post.title} - CleanForum`;

        // Use marked.js to render Markdown
        const contentToRender = marked.parse(post.content);

        container.innerHTML = `
            <div class="bg-white rounded-2xl shadow-lg overflow-hidden">
                <div class="p-8">
                    <h1 class="text-4xl font-bold text-gray-800 mb-6">${post.title}</h1>

                    <div class="flex items-center space-x-6 text-sm text-gray-500 mb-8 pb-6 border-b border-gray-100">
                        <div class="flex items-center">
                            <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-2">
                                <i class="fas fa-user text-blue-600 text-xs"></i>
                            </div>
                            <span class="font-medium">${post.author_username}</span>
                        </div>
                        <div class="flex items-center">
                            <i class="fas fa-clock mr-2 text-orange-500"></i>
                            <span>${timeAgo(post.created_at)}</span>
                        </div>
                        <div class="flex items-center">
                            <i class="fas fa-eye mr-2 text-green-500"></i>
                            <span>${post.view_count} views</span>
                        </div>
                        ${getSpamBadge(post.is_spam, post.spam_score)}
                    </div>

                    <div class="prose max-w-none text-gray-700 leading-relaxed">
                        ${contentToRender}
                    </div>
                </div>
            </div>
        `;

        if (metaContainer) {
            metaContainer.innerHTML = `
                <div class="space-y-4">
                    <div class="p-4 bg-blue-50 rounded-xl">
                        <h4 class="font-semibold text-blue-800 text-sm mb-2">Category</h4>
                        <a href="/category/${post.category_id}" class="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-lg text-sm font-medium hover:bg-blue-200 transition-colors">
                            ${post.category_name}
                        </a>
                    </div>

                    ${post.tags.length > 0 ? `
                    <div class="p-4 bg-purple-50 rounded-xl">
                        <h4 class="font-semibold text-purple-800 text-sm mb-2">Tags</h4>
                        <div class="flex flex-wrap gap-2">
                            ${post.tags.map(tag => `<span class="px-2 py-1 bg-purple-100 text-purple-700 rounded-md text-xs font-medium">#${tag}</span>`).join('')}
                        </div>
                    </div>
                    ` : ''}

                    <div class="p-4 bg-gray-50 rounded-xl">
                        <h4 class="font-semibold text-gray-800 text-sm mb-2">Security Rating</h4>
                        ${getSpamBadge(post.is_spam, post.spam_score)}
                        <div class="mt-2 text-xs text-gray-600">
                            Confidence: ${(100 - post.spam_score * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>
            `;
        }

        await loadComments(postId);

        // Load and display similar posts
        if (post.similar_posts) {
            renderSimilarPosts(post.similar_posts);
        }

        // Add action buttons if the current user is the author of the post
        if (currentUser && post.author_id === currentUser.id) {
            // Check that the button container has not already been created
            if (!document.getElementById('post-actions-container')) {
                const actionsContainer = document.createElement('div');
                actionsContainer.id = 'post-actions-container'; // Add ID for checking
                actionsContainer.className = 'p-4 bg-gray-100 rounded-xl';
                actionsContainer.innerHTML = `
                    <h4 class="font-semibold text-gray-800 text-sm mb-2">Actions</h4>
                    <div class="space-y-2">
                        <a href="/posts/${post.id}/edit" class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors flex items-center">
                            <i class="fas fa-pencil-alt mr-2"></i>
                            Edit Post
                        </a>
                        <button
                            onclick="handleDeletePost('${post.id}')"
                            class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium bg-red-100 text-red-800 hover:bg-red-200 transition-colors flex items-center">
                            <i class="fas fa-trash-alt mr-2"></i>
                            Delete Post
                        </button>
                    </div>
                `;
                metaContainer.querySelector('.space-y-4').appendChild(actionsContainer);
            }
        }

    } catch (error) {
        console.error('Error loading post detail:', error);
        document.getElementById('post-detail-container').innerHTML =
            `<div class="bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
                <i class="fas fa-exclamation-triangle text-red-500 text-3xl mb-4"></i>
                <h3 class="text-red-800 font-bold text-lg mb-2">Error loading post</h3>
                <p class="text-red-600">Post not found or server error</p>
            </div>`;
    }
}

async function loadComments(postId) {
    try {
        const comments = await api.getPostComments(postId);
        const container = document.getElementById('comments-container');

        if (comments.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <i class="fas fa-comments text-gray-400"></i>
                    </div>
                    <p class="text-gray-500">No comments yet</p>
                    <p class="text-gray-400 text-sm">Be the first to leave a comment!</p>
                </div>
            `;
            return;
        }

        container.innerHTML = comments.map(comment => `
            <div class="border-b border-gray-100 pb-6 mb-6 last:border-b-0">
                <div class="flex items-start space-x-4">
                    <div class="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                        <i class="fas fa-user text-white text-sm"></i>
                    </div>
                    <div class="flex-1">
                        <div class="flex items-center space-x-2 mb-2">
                            <span class="font-semibold text-gray-800">${comment.author_username}</span>
                            <span class="text-gray-400 text-sm">•</span>
                            <span class="text-gray-500 text-sm">${timeAgo(comment.created_at)}</span>
                        </div>
                        <p class="text-gray-700 leading-relaxed">${comment.content}</p>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

async function handleCommentForm(postId) {
    const form = document.getElementById('add-comment-form');
    if (!form) return;

    // Check if the handler has already been assigned to avoid duplication
    if (form.dataset.commentFormHandled) {
        return;
    }
    form.dataset.commentFormHandled = 'true';

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const contentInput = document.getElementById('comment-content');
        const content = contentInput.value.trim();
        const submitBtn = form.querySelector('button[type="submit"]');

        if (!content) {
            showAlert('Comment cannot be empty.', 'warning');
            return;
        }

        // Show loading state
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Submitting...';
        submitBtn.disabled = true;

        try {
            await api.createComment({ post_id: postId, content: content });
            showAlert('Comment added successfully!', 'success');
            contentInput.value = '';
            await loadComments(postId); // Reload comments
        } catch (error) {
            console.error('Error creating comment:', error);
            showAlert(error.message || 'Error adding comment.', 'danger');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

async function handleDeletePost(postId) {
    if (confirm('Are you sure you want to delete this post? This action is irreversible.')) {
        try {
            await api.deletePost(postId);
            showAlert('Post deleted successfully. Redirecting to homepage...', 'success');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } catch (error) {
            console.error('Error deleting post:', error);
            showAlert('Error deleting post. You may not have permission.', 'danger');
        }
    }
}

function renderSimilarPosts(posts) {
    const container = document.getElementById('similar-posts-container');
    if (!container) return;

    if (!posts || posts.length === 0) {
        container.innerHTML = `
            <div class="text-center py-6 text-gray-500">
                <i class="fas fa-search mb-2 text-2xl"></i>
                <p class="text-sm">No similar posts found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="space-y-3">
            ${posts.map(post => `
                <a href="/posts/${post.id}" class="block p-4 rounded-xl hover:bg-gray-50 transition-colors group">
                    <h4 class="font-medium text-gray-800 group-hover:text-blue-600 text-sm mb-2 leading-snug">${post.title}</h4>
                    <div class="flex items-center text-xs text-gray-500">
                        <i class="fas fa-user mr-1"></i>
                        <span>${post.author_username}</span>
                    </div>
                </a>
            `).join('')}
        </div>
    `;
}

async function loadStatsForHomePage() {
    try {
        const stats = await api.getSystemStats();
        const spamStatsContainer = document.getElementById('spam-stats');
        const quickStatsContainer = document.getElementById('quick-stats'); // New ID for the quick stats block

        // Update the "Spam Protection" block
        if (spamStatsContainer) {
            spamStatsContainer.innerHTML = `
                <div class="text-center">
                    <i class="fas fa-shield-alt mb-2 text-3xl text-green-500"></i>
                    <p class="text-gray-700 font-semibold text-lg">Spam Statistics</p>
                    <p class="text-gray-600 text-sm">Detected: <span class="font-bold text-red-600">${stats.spam_posts}</span> posts</p>
                    <p class="text-gray-600 text-sm">Spam percentage: <span class="font-bold text-yellow-600">${stats.spam_percentage}%</span></p>
                </div>
            `;
        }

        // Update the "Quick Stats" block
        if (quickStatsContainer) {
            quickStatsContainer.innerHTML = `
                <div class="space-y-3">
                    <div class="flex justify-between items-center p-3 bg-gradient-to-r from-green-50 to-yellow-50 rounded-lg">
                        <span class="text-gray-600">Total Posts</span>
                        <span class="font-bold text-green-700">${stats.total_posts}</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-gradient-to-r from-green-50 to-yellow-50 rounded-lg">
                        <span class="text-gray-600">Published Posts</span>
                        <span class="font-bold text-green-700">${stats.published_posts}</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-gradient-to-r from-green-50 to-yellow-50 rounded-lg">
                        <span class="text-gray-600">Total Comments</span>
                        <span class="font-bold text-green-700">${stats.total_comments}</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-gradient-to-r from-green-50 to-yellow-50 rounded-lg">
                        <span class="text-gray-600">Spam Posts Blocked</span>
                        <span class="font-bold text-yellow-700">${stats.spam_posts}</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-gradient-to-r from-green-50 to-yellow-50 rounded-lg">
                        <span class="text-gray-600">Spam Comments Blocked</span>
                        <span class="font-bold text-yellow-700">${stats.spam_comments}</span>
                    </div>
                </div>
            `;
        }

    } catch (error) {
        console.error('Error loading home page stats:', error);
        const errorHtml = `
            <div class="p-4 text-sm text-red-700 bg-red-100 rounded-lg" role="alert">
                Error loading statistics.
            </div>
        `;
        const spamStatsContainer = document.getElementById('spam-stats');
        const quickStatsContainer = document.getElementById('quick-stats');
        if (spamStatsContainer) spamStatsContainer.innerHTML = errorHtml;
        if (quickStatsContainer) quickStatsContainer.innerHTML = errorHtml;
    }
}

function showAlert(message, type = 'info') {
    const colors = {
        success: 'bg-green-50 border-green-200 text-green-800',
        danger: 'bg-red-50 border-red-200 text-red-800',
        warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
        info: 'bg-blue-50 border-blue-200 text-blue-800'
    };

    const icons = {
        success: 'fas fa-check-circle text-green-500',
        danger: 'fas fa-exclamation-triangle text-red-500',
        warning: 'fas fa-exclamation-triangle text-yellow-500',
        info: 'fas fa-info-circle text-blue-500'
    };

    const alertDiv = document.createElement('div');
    alertDiv.className = `${colors[type]} border rounded-xl p-4 mb-6 flex items-center space-x-3 animate-slide-up`;
    alertDiv.innerHTML = `
        <i class="${icons[type]}"></i>
        <span class="font-medium">${message}</span>
        <button onclick="this.parentElement.remove()" class="ml-auto text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
        </button>
    `;

    document.querySelector('main').insertBefore(alertDiv, document.querySelector('main').firstChild);

    // Automatically hide after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentElement) {
            alertDiv.remove();
        }
    }, 5000);
}

// Create Post page functions
async function initCreatePostPage() {
    // Load categories into the select element
    try {
        const categories = await api.getCategories();
        const select = document.getElementById('post-category');
        select.innerHTML = '<option value="">Select a category</option>' +
            categories.map(cat => `<option value="${cat.id}">${cat.name}</option>`).join('');
    } catch (error) {
        console.error('Error loading categories for select:', error);
    }

    // Configure form submission
    const form = document.getElementById('create-post-form');
    if (!form) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Creating post...';
        submitBtn.disabled = true;

        try {
            const postData = {
                title: document.getElementById('post-title').value,
                content: document.getElementById('post-content').value,
                category_id: document.getElementById('post-category').value,
                tags: document.getElementById('post-tags').value.split(',').map(tag => tag.trim()).filter(tag => tag)
            };

            if (!postData.title || !postData.content || !postData.category_id) {
                 showAlert('Please fill in all required fields: title, content, and category.', 'warning');
                 throw new Error("Required fields are missing.");
            }

            const newPost = await api.createPost(postData);

            if (newPost.is_spam) {
                // Show spam message in a dedicated container
                const spamContainer = document.getElementById('spam-message-container');
                if (spamContainer) {
                    spamContainer.innerHTML = `
                        <i class="fas fa-exclamation-triangle text-yellow-500 text-2xl mb-2"></i>
                        <p class="text-yellow-800 font-medium">Your post has been identified as spam.</p>
                        <p class="text-yellow-600 text-sm">It will not be visible to other users, but it will help us train our moderation system.</p>
                    `;
                    spamContainer.classList.remove('hidden');
                }
                // Lock the submit button and change the text
                submitBtn.innerHTML = '<i class="fas fa-check-circle mr-2"></i> Checked';
                // Do not redirect the user or show the standard alert
            } else {
                showAlert('Post created successfully! Redirecting...', 'success');
                setTimeout(() => {
                    window.location.href = `/posts/${newPost.id}`;
                }, 2000);
            }

        } catch (error) {
            console.error('Error creating post:', error);
            // Use the detailed error message from the API
            showAlert(error.message || 'An unknown error occurred. Please try again.', 'danger');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
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
            resultsContainer.innerHTML = `
                <div class="bg-yellow-50 border border-yellow-200 rounded-2xl p-6 text-center">
                    <i class="fas fa-exclamation-triangle text-yellow-500 text-2xl mb-2"></i>
                    <p class="text-yellow-800 font-medium">Search query must be at least 2 characters long</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = `
            <div class="text-center py-12">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
                <p class="text-gray-600">Searching the database...</p>
            </div>
        `;

        try {
            const posts = await api.searchPosts(query);
            renderSearchResults(posts, resultsContainer);
        } catch (error) {
            console.error('Search error:', error);
            resultsContainer.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
                    <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                    <p class="text-red-700 font-medium">An error occurred during the search</p>
                    <p class="text-red-600 text-sm">Please try again or contact an administrator</p>
                </div>
            `;
        }
    }
}

function renderSearchResults(posts, container) {
    if (posts.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12">
                <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <i class="fas fa-search text-gray-400 text-2xl"></i>
                </div>
                <h3 class="text-xl font-semibold text-gray-800 mb-2">Nothing found</h3>
                <p class="text-gray-600">Try changing your search query or using other keywords</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="mb-6">
            <p class="text-gray-600">Found results: <span class="font-semibold text-blue-600">${posts.length}</span></p>
        </div>
        <div class="space-y-6">
            ${posts.map(post => `
                <div class="bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 overflow-hidden group">
                    <div class="p-6">
                        <div class="flex items-start justify-between mb-4">
                            <h3 class="text-xl font-bold text-gray-800 group-hover:text-blue-600 transition-colors flex-1 mr-4">
                                <a href="/posts/${post.id}" class="hover:underline">${post.title}</a>
                            </h3>
                            ${getSpamBadge(post.is_spam, post.spam_score)}
                        </div>

                        <p class="text-gray-600 mb-4 leading-relaxed">${post.content.substring(0, 300)}${post.content.length > 300 ? '...' : ''}</p>

                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-4 text-sm text-gray-500">
                                <span class="flex items-center">
                                    <i class="fas fa-user mr-1 text-blue-500"></i>
                                    ${post.author_username}
                                </span>
                                <span class="flex items-center">
                                    <i class="fas fa-clock mr-1 text-orange-500"></i>
                                    ${timeAgo(post.created_at)}
                                </span>
                            </div>
                            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                ${post.category_name}
                            </span>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// Initialize page content
document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;

    if (path === '/') {
        loadPosts();
        loadCategories();
        loadStatsForHomePage();
    } else if (path.startsWith('/category/')) {
        const parts = path.split('/').filter(p => p);
        const categoryId = parts[1];
        loadPosts({ categoryId: categoryId });
        loadCategories(); // Also load categories on this page for consistency
    } else if (path.startsWith('/create')) {
        initCreatePostPage();
    } else if (path.startsWith('/posts/')) {
        const parts = path.split('/').filter(p => p);
        if (parts.length === 3 && parts[2] === 'edit') {
            const postId = parts[1];
            initEditPostPage(postId);
        } else if (parts.length === 2) {
            const postId = parts[1];
            loadPostDetail(postId);
            handleCommentForm(postId);
        }
    } else if (path.startsWith('/search')) {
        handleSearchForm();
    }
});

async function initEditPostPage(postId) {
    const form = document.getElementById('edit-post-form');
    if (!form) return;

    const titleInput = document.getElementById('post-title');
    const contentInput = document.getElementById('post-content');
    const categorySelect = document.getElementById('post-category');
    const tagsInput = document.getElementById('post-tags');

    // 1. Load categories and post data in parallel
    try {
        const [categories, post] = await Promise.all([
            api.getCategories(),
            api.getPost(postId)
        ]);

        // Fill in the categories
        categorySelect.innerHTML = categories.map(cat => `<option value="${cat.id}">${cat.name}</option>`).join('');

        // Fill in the form fields
        titleInput.value = post.title;
        contentInput.value = post.content; // Now just text
        categorySelect.value = post.category_id;
        tagsInput.value = post.tags.join(', ');

    } catch (error) {
        console.error('Error loading data for edit page:', error);
        showAlert('Error loading data for editing.', 'danger');
        if (form) form.innerHTML = '<p class="text-red-500">Could not load data.</p>';
        return;
    }

    // 2. Handle form submission
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Saving...';
        submitBtn.disabled = true;

        try {
            const postData = {
                title: titleInput.value,
                content: contentInput.value,
                category_id: categorySelect.value,
                tags: tagsInput.value.split(',').map(tag => tag.trim()).filter(tag => tag)
            };

            await api.updatePost(postId, postData);
                showAlert('Post updated successfully!', 'success');
                setTimeout(() => window.location.href = `/posts/${postId}`, 1500);

            } catch (error) {
                console.error('Error updating post:', error);
                showAlert(error.message || 'Error updating post.', 'danger');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
}
