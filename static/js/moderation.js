document.addEventListener('DOMContentLoaded', function() {
    const tableBody = document.querySelector('#moderation-table tbody');

    // Функция для загрузки и отображения сообщений
    async function loadMessages() {
        try {
            const response = await fetch('/api/moderation');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const messages = await response.json();
            
            // Очищаем таблицу перед заполнением
            tableBody.innerHTML = '';

            if (messages.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="4">Сообщений не найдено.</td></tr>';
                return;
            }

            messages.forEach(msg => {
                const row = document.createElement('tr');
                
                const statusText = msg.is_spam ? 'Спам' : 'Обычное';
                const statusClass = msg.is_spam ? 'status-spam' : 'status-ok';

                row.innerHTML = `
                    <td>${escapeHTML(msg.text)}</td>
                    <td class="${statusClass}">${statusText}</td>
                    <td>${new Date(msg.timestamp).toLocaleString()}</td>
                    <td class="actions">
                        <button class="btn-toggle-spam" data-id="${msg.id}" data-spam="${!msg.is_spam}">
                            ${msg.is_spam ? 'Сделать не спамом' : 'Сделать спамом'}
                        </button>
                        <button class="btn-delete" data-id="${msg.id}">Удалить</button>
                    </td>
                `;
                tableBody.appendChild(row);
            });

            // Добавляем обработчики событий на новые кнопки
            addEventListeners();

        } catch (error) {
            console.error('Ошибка при загрузке сообщений:', error);
            tableBody.innerHTML = '<tr><td colspan="4">Не удалось загрузить сообщения.</td></tr>';
        }
    }

    // Функция для добавления обработчиков событий
    function addEventListeners() {
        document.querySelectorAll('.btn-toggle-spam').forEach(button => {
            button.addEventListener('click', toggleSpamStatus);
        });
        document.querySelectorAll('.btn-delete').forEach(button => {
            button.addEventListener('click', deleteMessage);
        });
    }

    // Функция для изменения статуса спама
    async function toggleSpamStatus(event) {
        const button = event.target;
        const messageId = button.dataset.id;
        const newStatus = button.dataset.spam === 'true';

        try {
            const response = await fetch(`/api/moderation/update/${messageId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_spam: newStatus })
            });

            if (!response.ok) {
                throw new Error('Не удалось обновить статус.');
            }
            
            // Перезагружаем сообщения, чтобы увидеть изменения
            loadMessages();

        } catch (error) {
            console.error('Ошибка при изменении статуса:', error);
            alert('Произошла ошибка. Пожалуйста, попробуйте снова.');
        }
    }

    // Функция для удаления сообщения
    async function deleteMessage(event) {
        const button = event.target;
        const messageId = button.dataset.id;

        if (!confirm('Вы уверены, что хотите удалить это сообщение?')) {
            return;
        }

        try {
            const response = await fetch(`/api/moderation/delete/${messageId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Не удалось удалить сообщение.');
            }

            // Перезагружаем сообщения
            loadMessages();

        } catch (error) {
            console.error('Ошибка при удалении:', error);
            alert('Произошла ошибка. Пожалуйста, попробуйте снова.');
        }
    }

    // Функция для экранирования HTML
    function escapeHTML(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // Первоначальная загрузка сообщений
    loadMessages();
});
