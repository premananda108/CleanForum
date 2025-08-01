// CleanForum - JavaScript для работы с API (Tailwind Version)

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
            // Пытаемся получить детальное сообщение об ошибке из тела ответа
            try {
                const errorData = await response.json();
                // FastAPI часто использует поле 'detail' для ошибок
                const message = errorData.detail || `HTTP error! status: ${response.status}`;
                const error = new Error(message);
                error.response = response; // Прикрепляем ответ для доп. контекста
                throw error;
            } catch (e) {
                // Если тело ответа не JSON или пустое, выбрасываем общую ошибку
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
        return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><i class="fas fa-ban mr-1"></i>СПАМ</span>';
    } else if (spamScore > 0.5) {
        return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"><i class="fas fa-exclamation-triangle mr-1"></i>Подозрительно</span>';
    } else if (spamScore > 0.3) {
        return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"><i class="fas fa-check-circle mr-1"></i>Проверено</span>';
    }
    return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><i class="fas fa-shield-alt mr-1"></i>Чисто</span>';
}

// Main page functions
async function loadPosts(categoryId = null) {
    try {
        const posts = await api.getPosts(20, 0, categoryId);
        const container = document.getElementById('posts-container');

        if (posts.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-comments text-gray-400 text-2xl"></i>
                    </div>
                    <p class="text-gray-500 text-lg">Пока нет постов</p>
                    <p class="text-gray-400 text-sm">Будьте первым, кто создаст пост!</p>
                </div>
            `;
            return;
        }

        container.innerHTML = posts.map(post => `
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 overflow-hidden group">
                <div class="p-6">
                    <div class="flex items-start justify-between mb-4">
                        <h3 class="text-xl font-bold text-gray-800 group-hover:text-blue-600 transition-colors flex-1 mr-4">
                            <a href="/posts/${post.id}" class="hover:underline">${post.title}</a>
                        </h3>
                        ${getSpamBadge(post.is_spam, post.spam_score)}
                    </div>

                    <p class="text-gray-600 mb-4 leading-relaxed">${post.content.substring(0, 200)}${post.content.length > 200 ? '...' : ''}</p>

                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-4 text-sm text-gray-500">
                            <span class="flex items-center">
                                <i class="fas fa-user mr-1 text-blue-500"></i>
                                ${post.author_username}
                            </span>
                            <span class="flex items-center">
                                <i class="fas fa-eye mr-1 text-green-500"></i>
                                ${post.view_count}
                            </span>
                            <span class="flex items-center">
                                <i class="fas fa-comments mr-1 text-purple-500"></i>
                                ${post.comment_count}
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
        `).join('');

    } catch (error) {
        console.error('Error loading posts:', error);
        document.getElementById('posts-container').innerHTML =
            `<div class="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
                <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                <p class="text-red-700 font-medium">Ошибка загрузки постов</p>
                <p class="text-red-600 text-sm">Попробуйте обновить страницу</p>
            </div>`;
    }
}

async function loadCategories() {
    try {
        const categories = await api.getCategories();
        const container = document.getElementById('categories-list');

        if (categories.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-center py-4">Нет категорий</p>';
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
    }
}

// Post Detail page functions
async function loadPostDetail(postId) {
    try {
        // Загружаем данные поста и текущего пользователя параллельно
        const [post, currentUser] = await Promise.all([
            api.getPost(postId),
            api.getMe()
        ]);

        const container = document.getElementById('post-detail-container');
        const metaContainer = document.getElementById('post-meta-container');

        document.title = `${post.title} - CleanForum`;

        let contentToRender;
        try {
            const edjsParser = edjsHTML();
            const parsedContent = JSON.parse(post.content);
            contentToRender = edjsParser.parse(parsedContent).join('');
        } catch (error) {
            console.warn("Не удалось обработать содержимое поста как данные EditorJS, будет отображен обычный текст.", post.content);
            contentToRender = post.content.replace(/\n/g, '<br>');
        }

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
                            <span>${post.view_count} просмотров</span>
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
                        <h4 class="font-semibold text-blue-800 text-sm mb-2">Категория</h4>
                        <a href="/category/${post.category_id}" class="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-lg text-sm font-medium hover:bg-blue-200 transition-colors">
                            ${post.category_name}
                        </a>
                    </div>

                    ${post.tags.length > 0 ? `
                    <div class="p-4 bg-purple-50 rounded-xl">
                        <h4 class="font-semibold text-purple-800 text-sm mb-2">Теги</h4>
                        <div class="flex flex-wrap gap-2">
                            ${post.tags.map(tag => `<span class="px-2 py-1 bg-purple-100 text-purple-700 rounded-md text-xs font-medium">#${tag}</span>`).join('')}
                        </div>
                    </div>
                    ` : ''}

                    <div class="p-4 bg-gray-50 rounded-xl">
                        <h4 class="font-semibold text-gray-800 text-sm mb-2">Оценка безопасности</h4>
                        ${getSpamBadge(post.is_spam, post.spam_score)}
                        <div class="mt-2 text-xs text-gray-600">
                            Достоверность: ${(100 - post.spam_score * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>
            `;
        }

        await loadComments(postId);

        // Загружаем и отображаем похожие посты
        if (post.similar_posts) {
            renderSimilarPosts(post.similar_posts);
        }

        // Добавляем кнопки действий, если текущий пользователь является автором поста
        if (currentUser && post.author_id === currentUser.id) {
            const actionsContainer = document.createElement('div');
            actionsContainer.className = 'p-4 bg-gray-100 rounded-xl';
            actionsContainer.innerHTML = `
                <h4 class="font-semibold text-gray-800 text-sm mb-2">Действия</h4>
                <div class="space-y-2">
                    <a href="/posts/${post.id}/edit" class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors flex items-center">
                        <i class="fas fa-pencil-alt mr-2"></i>
                        Редактировать пост
                    </a>
                    <button
                        onclick="handleDeletePost('${post.id}')"
                        class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium bg-red-100 text-red-800 hover:bg-red-200 transition-colors flex items-center">
                        <i class="fas fa-trash-alt mr-2"></i>
                        Удалить пост
                    </button>
                </div>
            `;
            metaContainer.querySelector('.space-y-4').appendChild(actionsContainer);
        }

    } catch (error) {
        console.error('Error loading post detail:', error);
        document.getElementById('post-detail-container').innerHTML =
            `<div class="bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
                <i class="fas fa-exclamation-triangle text-red-500 text-3xl mb-4"></i>
                <h3 class="text-red-800 font-bold text-lg mb-2">Ошибка загрузки поста</h3>
                <p class="text-red-600">Пост не найден или произошла ошибка сервера</p>
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
                    <p class="text-gray-500">Комментариев пока нет</p>
                    <p class="text-gray-400 text-sm">Будьте первым, кто оставит комментарий!</p>
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

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const content = document.getElementById('comment-content').value;
        const submitBtn = form.querySelector('button[type="submit"]');

        // Показываем состояние загрузки
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Отправка...';
        submitBtn.disabled = true;

        try {
            await api.createComment({ post_id: postId, content: content });
            showAlert('Комментарий успешно добавлен!', 'success');
            document.getElementById('comment-content').value = '';
            await loadComments(postId); // Перезагружаем комментарии
        } catch (error) {
            console.error('Error creating comment:', error);
            showAlert('Ошибка при добавлении комментария.', 'danger');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

async function handleDeletePost(postId) {
    if (confirm('Вы уверены, что хотите удалить этот пост? Это действие необратимо.')) {
        try {
            await api.deletePost(postId);
            showAlert('Пост успешно удален. Перенаправление на главную...', 'success');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } catch (error) {
            console.error('Error deleting post:', error);
            showAlert('Ошибка при удалении поста. Возможно, у вас нет прав.', 'danger');
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
                <p class="text-sm">Похожих постов не найдено</p>
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

    // Автоматически скрываем через 5 секунд
    setTimeout(() => {
        if (alertDiv.parentElement) {
            alertDiv.remove();
        }
    }, 5000);
}

// Create Post page functions
async function initCreatePostPage() {
    // Загружаем категории в селект
    try {
        const categories = await api.getCategories();
        const select = document.getElementById('post-category');
        select.innerHTML = '<option value="">Выберите категорию</option>' +
            categories.map(cat => `<option value="${cat.id}">${cat.name}</option>`).join('');
    } catch (error) {
        console.error('Error loading categories for select:', error);
    }

    // Инициализируем EditorJS
    const editor = new EditorJS({
        holder: 'editorjs',
        tools: {
            paragraph: {
                class: window.Paragraph,
                inlineToolbar: true,
            },
            header: {
                class: window.Header,
                inlineToolbar: ['link'],
                config: {
                    placeholder: 'Введите заголовок',
                    levels: [2, 3, 4],
                    defaultLevel: 2
                }
            },
            list: {
                class: window.EditorjsList,
                inlineToolbar: true
            },
            quote: {
                class: window.Quote,
                inlineToolbar: true,
                shortcut: 'CMD+SHIFT+O',
                config: {
                    quotePlaceholder: 'Введите цитату',
                    captionPlaceholder: 'Автор цитаты',
                },
            },
            code: {
                class: window.CodeTool
            }
        },
        placeholder: 'Начните писать вашу историю...',
        defaultBlock: 'paragraph',
    });

    // Настраиваем отправку формы
    const form = document.getElementById('create-post-form');
    if (!form) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Создание поста...';
        submitBtn.disabled = true;

        try {
            const savedData = await editor.save();
            const postData = {
                title: document.getElementById('post-title').value,
                content: JSON.stringify(savedData),
                category_id: document.getElementById('post-category').value,
                tags: document.getElementById('post-tags').value.split(',').map(tag => tag.trim()).filter(tag => tag)
            };

            const newPost = await api.createPost(postData);

            if (newPost.status === 'spam') {
                showAlert('Ваш пост отправлен на проверку и будет опубликован после одобрения модератором.', 'warning');
                setTimeout(() => {
                    window.location.href = '/'; // Перенаправляем на главную
                }, 3000);
            } else {
                showAlert('Пост успешно создан! Перенаправление...', 'success');
                setTimeout(() => {
                    window.location.href = `/posts/${newPost.id}`;
                }, 2000);
            }

        } catch (error) {
            console.error('Error creating post:', error);
            // Используем детальное сообщение об ошибке, полученное от API
            showAlert(error.message || 'Произошла неизвестная ошибка. Пожалуйста, попробуйте еще раз.', 'danger');
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
                    <p class="text-yellow-800 font-medium">Поисковый запрос должен содержать минимум 2 символа</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = `
            <div class="text-center py-12">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
                <p class="text-gray-600">Поиск по базе данных...</p>
            </div>
        `;

        try {
            const posts = await api.searchPosts(query);
            renderSearchResults(posts, resultsContainer);
        } catch (error) {
            console.error('Ошибка поиска:', error);
            resultsContainer.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
                    <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                    <p class="text-red-700 font-medium">Произошла ошибка во время поиска</p>
                    <p class="text-red-600 text-sm">Попробуйте еще раз или обратитесь к администратору</p>
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
                <h3 class="text-xl font-semibold text-gray-800 mb-2">Ничего не найдено</h3>
                <p class="text-gray-600">Попробуйте изменить поисковый запрос или использовать другие ключевые слова</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="mb-6">
            <p class="text-gray-600">Найдено результатов: <span class="font-semibold text-blue-600">${posts.length}</span></p>
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
    } else if (path.startsWith('/create')) {
        initCreatePostPage();
    } else if (path.startsWith('/posts/')) {
        const postId = path.split('/').pop();
        loadPostDetail(postId);
        handleCommentForm(postId);
    } else if (path.startsWith('/search')) {
        handleSearchForm();
    }
})