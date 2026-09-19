let currentUser = null;

function postHtml(post) {
    const author = post.author || {};
    const avatar = Nexa.avatarUrl(author);
    const liked = post.liked ? 'liked' : '';
    const likeIcon = post.liked ? '❤️' : '🤍';

    return `
        <div class="post-card" data-post-id="${post.id}">
            <div class="post-header">
                <img class="avatar" src="${avatar}" alt="">
                <div class="post-author">
                    <a href="/profile/${Nexa.escapeHtml(author.username)}" class="post-author-name">${Nexa.escapeHtml(author.display_name || author.username)}</a>
                    <span class="post-author-username">@${Nexa.escapeHtml(author.username)}</span>
                </div>
                <span class="post-date">${Nexa.timeAgo(post.created_at)}</span>
            </div>
            <div class="post-content">${Nexa.escapeHtml(post.content)}</div>
            ${post.image ? `<img src="${Nexa.escapeHtml(post.image)}" style="border-radius:12px;margin-bottom:15px;max-height:500px;object-fit:cover;width:100%">` : ''}
            <div class="post-actions">
                <button class="post-action ${liked}" data-action="like">
                    ${likeIcon} <span class="like-count">${post.likes_count || 0}</span>
                </button>
                <button class="post-action" data-action="comment">
                    💬 <span>${post.comments_count || 0}</span>
                </button>
                ${currentUser && currentUser.id === author.id ? `
                    <button class="post-action" data-action="delete" style="margin-left:auto">
                        🗑️
                    </button>
                ` : ''}
            </div>
            <div class="post-comments hidden" data-comments>
                <div class="comments-list"></div>
                <form class="comment-form" data-comment-form>
                    <input type="text" placeholder="Écrire un commentaire..." maxlength="1000">
                    <button type="submit" class="btn btn-primary btn-sm">Envoyer</button>
                </form>
            </div>
        </div>
    `;
}

async function loadFeed() {
    const container = document.getElementById('feed-container');
    try {
        const data = await Nexa.get('/api/posts?limit=20');
        if (!data.ok) {
            container.innerHTML = '<div class="loader">Erreur de chargement.</div>';
            return;
        }
        if (data.posts.length === 0) {
            container.innerHTML = '<div class="loader">Aucune publication pour le moment. Sois le premier !</div>';
            return;
        }
        container.innerHTML = data.posts.map(postHtml).join('');
        attachPostHandlers();
    } catch (e) {
        container.innerHTML = '<div class="loader">Erreur réseau.</div>';
    }
}

function attachPostHandlers() {
    document.querySelectorAll('.post-card').forEach(function (card) {
        const postId = card.getAttribute('data-post-id');

        const likeBtn = card.querySelector('[data-action="like"]');
        if (likeBtn) {
            likeBtn.addEventListener('click', async function () {
                try {
                    const res = await Nexa.post('/api/posts/' + postId + '/like');
                    if (res.ok) {
                        if (res.liked) {
                            likeBtn.classList.add('liked');
                            likeBtn.innerHTML = '❤️ <span class="like-count">' + res.count + '</span>';
                        } else {
                            likeBtn.classList.remove('liked');
                            likeBtn.innerHTML = '🤍 <span class="like-count">' + res.count + '</span>';
                        }
                    }
                } catch (e) {}
            });
        }

        const commentBtn = card.querySelector('[data-action="comment"]');
        const commentsBox = card.querySelector('[data-comments]');
        if (commentBtn && commentsBox) {
            commentBtn.addEventListener('click', function () {
                commentsBox.classList.toggle('hidden');
                if (!commentsBox.classList.contains('hidden')) {
                    loadComments(postId, commentsBox.querySelector('.comments-list'));
                }
            });
        }

        const deleteBtn = card.querySelector('[data-action="delete"]');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async function () {
                if (!confirm('Supprimer cette publication ?')) return;
                try {
                    const res = await Nexa.del('/api/posts/' + postId);
                    if (res.ok) {
                        card.remove();
                        showToast('Publication supprimée', 'success');
                    }
                } catch (e) {}
            });
        }

        const form = card.querySelector('[data-comment-form]');
        if (form) {
            form.addEventListener('submit', async function (e) {
                e.preventDefault();
                const input = form.querySelector('input');
                const content = input.value.trim();
                if (!content) return;

                try {
                    const res = await Nexa.post('/api/posts/' + postId + '/comments', { content: content });
                    if (res.ok) {
                        input.value = '';
                        loadComments(postId, commentsBox.querySelector('.comments-list'));
                        const countSpan = commentBtn.querySelector('span');
                        if (countSpan) countSpan.textContent = parseInt(countSpan.textContent) + 1;
                    }
                } catch (e) {}
            });
        }
    });
}

async function loadComments(postId, container) {
    container.innerHTML = '<div class="loader-small">Chargement...</div>';
    try {
        const data = await Nexa.get('/api/posts/' + postId + '/comments');
        if (!data.ok || data.comments.length === 0) {
            container.innerHTML = '<div class="loader-small">Aucun commentaire</div>';
            return;
        }
        container.innerHTML = data.comments.map(function (c) {
            const a = c.author || {};
            return `
                <div class="comment">
                    <img class="avatar" src="${Nexa.avatarUrl(a)}" alt="">
                    <div class="comment-body">
                        <div class="comment-author">${Nexa.escapeHtml(a.display_name || a.username)}</div>
                        <div class="comment-text">${Nexa.escapeHtml(c.content)}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="loader-small">Erreur</div>';
    }
}

function initComposer() {
    const textarea = document.getElementById('post-content');
    const count = document.getElementById('composer-count');
    const btn = document.getElementById('post-btn');

    if (!textarea || !btn) return;

    textarea.addEventListener('input', function () {
        count.textContent = textarea.value.length + ' / 5000';
    });

    btn.addEventListener('click', async function () {
        const content = textarea.value.trim();
        if (!content) return;

        btn.disabled = true;
        btn.textContent = 'Publication...';

        try {
            const res = await Nexa.post('/api/posts', { content: content });
            if (res.ok) {
                textarea.value = '';
                count.textContent = '0 / 5000';
                showToast('Publication créée ✨', 'success');
                const container = document.getElementById('feed-container');
                const firstCard = container.querySelector('.post-card');
                const html = postHtml(res.post);
                if (firstCard) {
                    firstCard.insertAdjacentHTML('beforebegin', html);
                } else {
                    container.innerHTML = html;
                }
                attachPostHandlers();
            } else {
                showToast(res.error || 'Erreur', 'error');
            }
        } catch (e) {
            showToast('Erreur réseau', 'error');
        }

        btn.disabled = false;
        btn.textContent = 'Publier';
    });
}

async function initSidebar() {
    try {
        const data = await Nexa.get('/api/profile/me');
        if (!data.ok) return;
        currentUser = data.profile;

        const avatar = document.getElementById('sidebar-avatar');
        const name = document.getElementById('sidebar-name');
        const username = document.getElementById('sidebar-username');
        const posts = document.getElementById('sidebar-posts');
        const followers = document.getElementById('sidebar-followers');
        const following = document.getElementById('sidebar-following');

        if (avatar) avatar.src = Nexa.avatarUrl(currentUser);
        if (name) name.textContent = currentUser.display_name || currentUser.username;
        if (username) username.textContent = '@' + currentUser.username;
        if (posts) posts.textContent = currentUser.posts_count;
        if (followers) followers.textContent = currentUser.followers_count;
        if (following) following.textContent = currentUser.following_count;

        const composerAvatar = document.getElementById('composer-avatar');
        if (composerAvatar) composerAvatar.src = Nexa.avatarUrl(currentUser);
    } catch (e) {}
}

async function loadSuggestions() {
    const container = document.getElementById('suggestions-list');
    if (!container) return;

    try {
        const data = await Nexa.get('/api/search/users?q=a');
        if (!data.ok) return;
        const users = (data.users || []).filter(function (u) {
            return !currentUser || u.id !== currentUser.id;
        }).slice(0, 5);

        if (users.length === 0) {
            container.innerHTML = '<div class="loader-small">Aucune suggestion</div>';
            return;
        }

        container.innerHTML = users.map(function (u) {
            return `
                <a href="/profile/${Nexa.escapeHtml(u.username)}" class="suggestion">
                    <img class="avatar" src="${Nexa.avatarUrl(u)}" alt="">
                    <div class="suggestion-info">
                        <div class="suggestion-name">${Nexa.escapeHtml(u.display_name || u.username)}</div>
                        <div class="suggestion-username">@${Nexa.escapeHtml(u.username)}</div>
                    </div>
                </a>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="loader-small">Erreur</div>';
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    if (!Nexa.isLoggedIn()) {
        window.location.href = '/login';
        return;
    }
    await initSidebar();
    loadFeed();
    loadSuggestions();
    initComposer();
});
