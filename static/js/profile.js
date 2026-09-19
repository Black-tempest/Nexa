let profileUser = null;
let isOwnProfile = false;

function getUsernameFromUrl() {
    const parts = window.location.pathname.split('/').filter(Boolean);
    if (parts.length >= 2 && parts[0] === 'profile') {
        return parts[1];
    }
    return null;
}

function renderProfile(profile) {
    document.title = (profile.display_name || profile.username) + ' — Nexa';

    const avatar = document.getElementById('profile-avatar');
    const name = document.getElementById('profile-display-name');
    const username = document.getElementById('profile-username');
    const bio = document.getElementById('profile-bio');
    const joined = document.getElementById('profile-joined');
    const statPosts = document.getElementById('stat-posts');
    const statFollowers = document.getElementById('stat-followers-count');
    const statFollowing = document.getElementById('stat-following-count');

    if (avatar) avatar.src = Nexa.avatarUrl(profile);
    if (name) name.textContent = profile.display_name || profile.username;
    if (username) username.textContent = '@' + profile.username;
    if (bio) bio.textContent = profile.bio || '';
    if (joined) joined.textContent = Nexa.formatDate(profile.created_at);
    if (statPosts) statPosts.textContent = profile.posts_count;
    if (statFollowers) statFollowers.textContent = profile.followers_count;
    if (statFollowing) statFollowing.textContent = profile.following_count;

    const editBtn = document.getElementById('edit-profile-btn');
    const followBtn = document.getElementById('follow-btn');
    const messageBtn = document.getElementById('message-btn');

    if (profile.is_me) {
        isOwnProfile = true;
        if (editBtn) editBtn.classList.remove('hidden');
        if (followBtn) followBtn.classList.add('hidden');
        if (messageBtn) messageBtn.classList.add('hidden');
    } else {
        isOwnProfile = false;
        if (editBtn) editBtn.classList.add('hidden');
        if (messageBtn) messageBtn.classList.remove('hidden');
        if (followBtn) {
            followBtn.classList.remove('hidden');
            followBtn.textContent = profile.is_following ? 'Ne plus suivre' : 'Suivre';
            followBtn.classList.toggle('btn-outline', profile.is_following);
            followBtn.classList.toggle('btn-primary', !profile.is_following);
        }
    }
}

async function loadProfile() {
    const username = getUsernameFromUrl();
    const url = username ? '/api/profile/' + encodeURIComponent(username) : '/api/profile/me';

    try {
        const data = await Nexa.get(url);
        if (!data.ok) {
            showToast('Profil introuvable', 'error');
            setTimeout(function () { window.location.href = '/feed'; }, 1500);
            return;
        }
        profileUser = data.profile;
        renderProfile(profileUser);
        loadProfilePosts(profileUser.id);
    } catch (e) {
        showToast('Erreur réseau', 'error');
    }
}

function postHtml(post) {
    const author = post.author || {};
    const liked = post.liked ? 'liked' : '';
    const likeIcon = post.liked ? '❤️' : '🤍';

    return `
        <div class="post-card" data-post-id="${post.id}">
            <div class="post-header">
                <img class="avatar" src="${Nexa.avatarUrl(author)}" alt="">
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
                ${isOwnProfile ? `
                    <button class="post-action" data-action="delete" style="margin-left:auto">🗑️</button>
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

async function loadProfilePosts(userId) {
    const container = document.getElementById('profile-posts');
    if (!container) return;

    try {
        const data = await Nexa.get('/api/posts?author=' + userId + '&limit=30');
        if (!data.ok) {
            container.innerHTML = '<div class="loader">Erreur</div>';
            return;
        }
        if (data.posts.length === 0) {
            container.innerHTML = '<div class="loader">Aucune publication</div>';
            return;
        }
        container.innerHTML = data.posts.map(postHtml).join('');
        attachPostHandlers();
    } catch (e) {
        container.innerHTML = '<div class="loader">Erreur réseau</div>';
    }
}

function attachPostHandlers() {
    document.querySelectorAll('#profile-posts .post-card').forEach(function (card) {
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

function initFollowButton() {
    const btn = document.getElementById('follow-btn');
    if (!btn) return;

    btn.addEventListener('click', async function () {
        if (!profileUser) return;

        btn.disabled = true;
        try {
            const res = await Nexa.post('/api/profile/' + profileUser.id + '/follow');
            if (res.ok) {
                const followers = document.getElementById('stat-followers-count');
                if (followers) followers.textContent = res.followers_count;

                if (res.following) {
                    btn.textContent = 'Ne plus suivre';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline');
                } else {
                    btn.textContent = 'Suivre';
                    btn.classList.remove('btn-outline');
                    btn.classList.add('btn-primary');
                }
            }
        } catch (e) {}
        btn.disabled = false;
    });
}

function initMessageButton() {
    const btn = document.getElementById('message-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
        if (!profileUser) return;
        window.location.href = '/chat?user=' + profileUser.id;
    });
}

function initEditModal() {
    const openBtn = document.getElementById('edit-profile-btn');
    const modal = document.getElementById('edit-profile-modal');
    const closeBtn = document.getElementById('close-edit-modal');
    const cancelBtn = document.getElementById('cancel-edit');
    const form = document.getElementById('edit-profile-form');

    if (!openBtn || !modal) return;

    openBtn.addEventListener('click', function () {
        document.getElementById('edit-display-name').value = profileUser.display_name || '';
        document.getElementById('edit-bio').value = profileUser.bio || '';
        document.getElementById('edit-avatar').value = profileUser.avatar || '';
        document.getElementById('edit-password').value = '';
        modal.classList.remove('hidden');
    });

    function close() {
        modal.classList.add('hidden');
    }

    if (closeBtn) closeBtn.addEventListener('click', close);
    if (cancelBtn) cancelBtn.addEventListener('click', close);

    modal.addEventListener('click', function (e) {
        if (e.target === modal) close();
    });

    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const err = document.getElementById('edit-profile-error');
            const submitBtn = document.getElementById('submit-edit');

            err.classList.add('hidden');

            const body = {
                display_name: document.getElementById('edit-display-name').value.trim(),
                bio: document.getElementById('edit-bio').value.trim(),
                avatar: document.getElementById('edit-avatar').value.trim()
            };

            const password = document.getElementById('edit-password').value;
            if (password) body.password = password;

            submitBtn.disabled = true;
            submitBtn.textContent = 'Enregistrement...';

            try {
                const res = await Nexa.post('/api/auth/update', body);
                if (res.ok) {
                    showToast('Profil mis à jour ✨', 'success');
                    profileUser = Object.assign(profileUser, res.user);
                    renderProfile(profileUser);
                    Nexa.saveAuth(Nexa.token, res.user);
                    close();
                } else {
                    err.textContent = res.error || 'Erreur';
                    err.classList.remove('hidden');
                }
            } catch (e) {
                err.textContent = 'Erreur réseau';
                err.classList.remove('hidden');
            }

            submitBtn.disabled = false;
            submitBtn.textContent = 'Enregistrer';
        });
    }
}

function initFollowersModal() {
    const modal = document.getElementById('followers-modal');
    const closeBtn = document.getElementById('close-followers-modal');
    const title = document.getElementById('followers-modal-title');
    const list = document.getElementById('followers-list');
    const statFollowers = document.getElementById('stat-followers');
    const statFollowing = document.getElementById('stat-following');

    if (!modal) return;

    function close() {
        modal.classList.add('hidden');
    }

    if (closeBtn) closeBtn.addEventListener('click', close);

    modal.addEventListener('click', function (e) {
        if (e.target === modal) close();
    });

    async function showList(type) {
        if (!profileUser) return;
        modal.classList.remove('hidden');
        title.textContent = type === 'followers' ? 'Abonnés' : 'Abonnements';
        list.innerHTML = '<div class="loader-small">Chargement...</div>';

        try {
            const url = '/api/profile/' + profileUser.id + '/' + type;
            const data = await Nexa.get(url);
            if (!data.ok || data.users.length === 0) {
                list.innerHTML = '<div class="loader-small">Aucun utilisateur</div>';
                return;
            }
            list.innerHTML = data.users.map(function (u) {
                return `
                    <a href="/profile/${Nexa.escapeHtml(u.username)}" class="suggestion" style="text-decoration:none;color:inherit">
                        <img class="avatar" src="${Nexa.avatarUrl(u)}" alt="">
                        <div class="suggestion-info">
                            <div class="suggestion-name">${Nexa.escapeHtml(u.display_name || u.username)}</div>
                            <div class="suggestion-username">@${Nexa.escapeHtml(u.username)}</div>
                        </div>
                    </a>
                `;
            }).join('');
        } catch (e) {
            list.innerHTML = '<div class="loader-small">Erreur</div>';
        }
    }

    if (statFollowers) {
        statFollowers.addEventListener('click', function () { showList('followers'); });
    }
    if (statFollowing) {
        statFollowing.addEventListener('click', function () { showList('following'); });
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    if (!Nexa.isLoggedIn()) {
        window.location.href = '/login';
        return;
    }
    await loadProfile();
    initFollowButton();
    initMessageButton();
    initEditModal();
    initFollowersModal();
});
