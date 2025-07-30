document.addEventListener('DOMContentLoaded', () => {
    const postForm = document.getElementById('new-post-form');
    const postsList = document.getElementById('posts-list');
    const errorMessage = document.getElementById('error-message');

    /**
     * Simple HTML escaping function to prevent XSS
     * @param {string} str The string to escape
     * @returns {string} The escaped string
     */
    const escapeHTML = (str) => {
        const p = document.createElement('p');
        p.appendChild(document.createTextNode(str));
        return p.innerHTML;
    };

    /**
     * Displays an error message to the user.
     * @param {string} message The error message to display.
     */
    const showError = (message) => {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    };

    /**
     * Fetches posts from the API and renders them to the page.
     */
    const fetchPosts = async () => {
        try {
            const response = await fetch('/api/posts');
            if (!response.ok) {
                throw new Error('Failed to fetch posts. The server might be down.');
            }
            const posts = await response.json();
            
            postsList.innerHTML = ''; // Clear existing posts
            if (posts.length === 0) {
                postsList.innerHTML = '<p>No posts yet. Be the first!</p>';
                return;
            }

            posts.forEach(post => {
                const postElement = document.createElement('div');
                postElement.className = 'post';
                postElement.innerHTML = `
                    <h3>${escapeHTML(post.title)}</h3>
                    <p class="post-meta">By <strong>${escapeHTML(post.author)}</strong> on ${new Date(post.timestamp).toLocaleString()}</p>
                    <p class="post-content">${escapeHTML(post.content)}</p>
                `;
                postsList.appendChild(postElement);
            });
        } catch (error) {
            showError(error.message);
        }
    };

    /**
     * Handles the submission of the new post form.
     */
    postForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorMessage.style.display = 'none'; // Hide previous errors

        const author = document.getElementById('author').value;
        const title = document.getElementById('title').value;
        const content = document.getElementById('content').value;
        const submitButton = postForm.querySelector('button');

        submitButton.disabled = true;
        submitButton.textContent = 'Submitting...';

        try {
            const response = await fetch('/api/posts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ author, title, content }),
            });

            if (!response.ok) {
                let errorText = 'An unknown error occurred.';
                try {
                    const errorData = await response.json();
                    // Check for FastAPI validation errors (HTTP 422)
                    if (response.status === 422 && Array.isArray(errorData.detail)) {
                        errorText = errorData.detail.map(err => {
                            const field = err.loc[err.loc.length - 1];
                            return `${field}: ${err.msg}`;
                        }).join('; ');
                    } else {
                        // Handle other JSON errors (like spam filter)
                        errorText = errorData.detail || JSON.stringify(errorData);
                    }
                } catch (e) {
                    // Fallback for non-JSON error responses
                    errorText = await response.text();
                }
                throw new Error(errorText);
            }

            // Clear form and refresh posts on success
            postForm.reset();
            await fetchPosts();

        } catch (error) {
            showError(error.message);
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = 'Submit Post';
        }
    });

    // Initial fetch of posts when the page loads
    fetchPosts();
});
