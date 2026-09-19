let socket = null;
let currentChatUser = null;
let typingTimeout = null;

function messageHtml(msg, isMe) {
    const cls = isMe ? 'message me' : 'message';
    return `
        <div class="${cls}" data-msg-id="${msg.id}">
            <div class="message-bubble">${Nexa.escapeHtml(msg.content)}</div>
            <span class="message-time">${Nexa.timeAgo(msg.created_at)}</span>
        </div>
    `;
}

function conversationHtml(conv) {
    const u = conv.user || {};
    const last = conv.last_message || {};
    const unread = conv.unread > 0 ? '<span class="unread-dot"></span>' : '';
    const active = currentChatUser && currentChatUser.id === u.id ? 'active' : '';

    return `
        <div class="conversation ${active}" data-user-id="${u.id}">
            <img class="avatar" src="${Nexa.avatarUrl(u)}" alt="">
            <div class="conversation-info">
                <div class="conversation-name">${Nexa.escapeHtml(u.display_name || u.username)}</div>
                <div class="conversation-last">${Nexa.escapeHtml(last.content || 'Nouvelle conversation')}</div>
            </div>
            <div class="conversation-meta">
                <div class="conversation-time">${Nexa.timeAgo(last.created_at)}</div>
                ${unread}
            </div>
        </div>
    `;
}

async function loadConversations() {
    const container = document.getElementById('conversations-list');
    if (!container) return;

    try {
        const data = await Nexa.get('/api/chat/conversations');
        if (!data.ok || data.conversations.length === 0) {
            container.innerHTML = '<div class="loader-small">Aucune conversation</div>';
            return;
        }
        container.innerHTML = data.conversations.map(conversationHtml).join('');

        container.querySelectorAll('.conversation').forEach(function (el) {
            el.addEventListener('click', function () {
                const uid = parseInt(el.getAttribute('data-user-id'));
                openChat(uid);
            });
        });
    } catch (e) {
        container.innerHTML = '<div class="loader-small">Erreur</div>';
    }
}

async function openChat(userId) {
    try {
        const data = await Nexa.get('/api/chat/with/' + userId);
        if (!data.ok) {
            showToast('Erreur de chargement', 'error');
            return;
        }

        currentChatUser = data.user;

        document.getElementById('chat-empty').classList.add('hidden');
        document.getElementById('chat-window').classList.remove('hidden');

        document.getElementById('chat-header-avatar').src = Nexa.avatarUrl(currentChatUser);
        const nameLink = document.getElementById('chat-header-name');
        nameLink.textContent = currentChatUser.display_name || currentChatUser.username;
        nameLink.href = '/profile/' + currentChatUser.username;

        const container = document.getElementById('messages-container');
        if (data.messages.length === 0) {
            container.innerHTML = '<div class="loader-small">Aucun message. Dis bonjour !</div>';
        } else {
            container.innerHTML = data.messages.map(function (m) {
                return messageHtml(m, m.from_user === Nexa.user.id);
            }).join('');
        }

        container.scrollTop = container.scrollHeight;

        document.querySelectorAll('.conversation').forEach(function (el) {
            el.classList.remove('active');
            if (parseInt(el.getAttribute('data-user-id')) === userId) {
                el.classList.add('active');
            }
        });

        Nexa.updateNavBadges();
    } catch (e) {
        showToast('Erreur réseau', 'error');
    }
}

function appendMessage(msg) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const isMe = msg.from_user === Nexa.user.id;
    const isCurrent = currentChatUser && (
        (isMe && msg.to_user === currentChatUser.id) ||
        (!isMe && msg.from_user === currentChatUser.id)
    );

    if (!isCurrent) return;

    if (container.querySelector('[data-msg-id="' + msg.id + '"]')) return;

    const emptyLoader = container.querySelector('.loader-small');
    if (emptyLoader) emptyLoader.remove();

    container.insertAdjacentHTML('beforeend', messageHtml(msg, isMe));
    container.scrollTop = container.scrollHeight;
}

function initSocket() {
    if (!window.io) {
        console.warn('SocketIO not loaded');
        return;
    }

    socket = io({
        auth: { token: Nexa.token }
    });

    socket.on('connect', function () {
        console.log('Socket connected');
    });

    socket.on('private_message', function (data) {
        appendMessage(data.message);
        loadConversations();
        Nexa.updateNavBadges();
    });

    socket.on('private_message_sent', function (data) {
        appendMessage(data.message);
        loadConversations();
    });

    socket.on('typing', function (data) {
        if (!currentChatUser) return;
        if (data.type === 'private' && data.from_user === currentChatUser.id) {
            const indicator = document.getElementById('typing-indicator');
            indicator.classList.remove('hidden');
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(function () {
                indicator.classList.add('hidden');
            }, 2000);
        }
    });

    socket.on('disconnect', function () {
        console.log('Socket disconnected');
    });
}

function initMessageForm() {
    const form = document.getElementById('message-form');
    const input = document.getElementById('message-input');
    if (!form || !input) return;

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!currentChatUser || !socket) return;

        const content = input.value.trim();
        if (!content) return;

        socket.emit('private_message', {
            to_user: currentChatUser.id,
            content: content
        });

        input.value = '';
    });

    input.addEventListener('input', function () {
        if (!currentChatUser || !socket) return;
        socket.emit('typing', {
            type: 'private',
            to_user: currentChatUser.id
        });
    });
}

function initSearch() {
    const input = document.getElementById('chat-search-input');
    const results = document.getElementById('chat-search-results');
    if (!input || !results) return;

    let searchTimeout = null;

    input.addEventListener('input', function () {
        clearTimeout(searchTimeout);
        const q = input.value.trim();

        if (!q) {
            results.classList.add('hidden');
            return;
        }

        searchTimeout = setTimeout(async function () {
            try {
                const data = await Nexa.get('/api/search/users?q=' + encodeURIComponent(q));
                if (!data.ok || data.users.length === 0) {
                    results.innerHTML = '<div class="loader-small">Aucun résultat</div>';
                    results.classList.remove('hidden');
                    return;
                }

                results.innerHTML = data.users.map(function (u) {
                    return `
                        <div class="search-result" data-user-id="${u.id}">
                            <img class="avatar" src="${Nexa.avatarUrl(u)}" alt="">
                            <div class="suggestion-info">
                                <div class="suggestion-name">${Nexa.escapeHtml(u.display_name || u.username)}</div>
                                <div class="suggestion-username">@${Nexa.escapeHtml(u.username)}</div>
                            </div>
                        </div>
                    `;
                }).join('');

                results.classList.remove('hidden');

                results.querySelectorAll('.search-result').forEach(function (el) {
                    el.addEventListener('click', function () {
                        const uid = parseInt(el.getAttribute('data-user-id'));
                        results.classList.add('hidden');
                        input.value = '';
                        openChat(uid);
                    });
                });
            } catch (e) {}
        }, 300);
    });

    document.addEventListener('click', function (e) {
        if (!input.contains(e.target) && !results.contains(e.target)) {
            results.classList.add('hidden');
        }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    if (!Nexa.isLoggedIn()) {
        window.location.href = '/login';
        return;
    }
    loadConversations();
    initSocket();
    initMessageForm();
    initSearch();
});
