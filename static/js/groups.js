let currentTab = 'all';
let currentUser = null;

function groupHtml(group) {
    const isPrivate = group.is_private ? '<span class="group-private-badge">PRIVÉ</span>' : '';
    const isMember = group.is_member;
    const myRole = group.my_role;

    let actionBtn = '';
    if (isMember) {
        if (myRole === 'owner') {
            actionBtn = '<button class="btn btn-outline btn-sm" data-action="open">Ouvrir</button>';
        } else {
            actionBtn = '<button class="btn btn-outline btn-sm" data-action="open">Ouvrir</button>';
        }
    } else {
        actionBtn = '<button class="btn btn-primary btn-sm" data-action="join">Rejoindre</button>';
    }

    return `
        <div class="group-card" data-group-id="${group.id}">
            <div class="group-cover">👥</div>
            <div class="group-body">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <div class="group-name">${Nexa.escapeHtml(group.name)}</div>
                    ${isPrivate}
                </div>
                <div class="group-desc">${Nexa.escapeHtml(group.description || 'Aucune description')}</div>
                <div class="group-meta">
                    <span>👤 ${group.members_count} membres</span>
                    ${actionBtn}
                </div>
            </div>
        </div>
    `;
}

async function loadGroups() {
    const container = document.getElementById('groups-list');
    if (!container) return;

    const search = document.getElementById('groups-search');
    const query = search ? search.value.trim() : '';

    let url = '/api/groups?';
    if (currentTab === 'mine') {
        url += 'mine=1';
    } else if (query) {
        url += 'search=' + encodeURIComponent(query);
    }

    try {
        const data = await Nexa.get(url);
        if (!data.ok) {
            container.innerHTML = '<div class="loader">Erreur de chargement</div>';
            return;
        }
        if (data.groups.length === 0) {
            container.innerHTML = '<div class="loader">Aucun groupe pour le moment</div>';
            return;
        }
        container.innerHTML = data.groups.map(groupHtml).join('');
        attachGroupHandlers();
    } catch (e) {
        container.innerHTML = '<div class="loader">Erreur réseau</div>';
    }
}

function attachGroupHandlers() {
    document.querySelectorAll('.group-card').forEach(function (card) {
        const groupId = card.getAttribute('data-group-id');

        const joinBtn = card.querySelector('[data-action="join"]');
        if (joinBtn) {
            joinBtn.addEventListener('click', async function (e) {
                e.stopPropagation();
                try {
                    const res = await Nexa.post('/api/groups/' + groupId + '/join');
                    if (res.ok) {
                        showToast('Groupe rejoint ✅', 'success');
                        loadGroups();
                    } else {
                        showToast(res.error || 'Erreur', 'error');
                    }
                } catch (e) {}
            });
        }

        card.addEventListener('click', function () {
            window.location.href = '/groups/' + groupId;
        });
    });
}

function initTabs() {
    document.querySelectorAll('.groups-tabs .tab-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.groups-tabs .tab-btn').forEach(function (b) {
                b.classList.remove('active');
            });
            btn.classList.add('active');
            currentTab = btn.getAttribute('data-tab');
            loadGroups();
        });
    });
}

function initSearch() {
    const input = document.getElementById('groups-search');
    if (!input) return;
    let t = null;
    input.addEventListener('input', function () {
        clearTimeout(t);
        t = setTimeout(loadGroups, 400);
    });
}

function initCreateModal() {
    const openBtn = document.getElementById('create-group-btn');
    const modal = document.getElementById('create-group-modal');
    const closeBtn = document.getElementById('close-modal');
    const cancelBtn = document.getElementById('cancel-create');
    const form = document.getElementById('create-group-form');

    if (!openBtn || !modal) return;

    openBtn.addEventListener('click', function () {
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
            const name = document.getElementById('group-name').value.trim();
            const description = document.getElementById('group-description').value.trim();
            const isPrivate = document.getElementById('group-private').checked;
            const err = document.getElementById('create-group-error');
            const submitBtn = document.getElementById('submit-create');

            err.classList.add('hidden');

            if (!name || name.length < 2) {
                err.textContent = 'Le nom doit contenir au moins 2 caractères';
                err.classList.remove('hidden');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Création...';

            try {
                const res = await Nexa.post('/api/groups', {
                    name: name,
                    description: description,
                    is_private: isPrivate
                });

                if (res.ok) {
                    showToast('Groupe créé 🎉', 'success');
                    form.reset();
                    close();
                    currentTab = 'mine';
                    document.querySelectorAll('.groups-tabs .tab-btn').forEach(function (b) {
                        b.classList.remove('active');
                        if (b.getAttribute('data-tab') === 'mine') b.classList.add('active');
                    });
                    loadGroups();
                } else {
                    err.textContent = res.error || 'Erreur';
                    err.classList.remove('hidden');
                }
            } catch (e) {
                err.textContent = 'Erreur réseau';
                err.classList.remove('hidden');
            }

            submitBtn.disabled = false;
            submitBtn.textContent = 'Créer';
        });
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    if (!Nexa.isLoggedIn()) {
        window.location.href = '/login';
        return;
    }

    try {
        const me = await Nexa.get('/api/profile/me');
        if (me.ok) currentUser = me.profile;
    } catch (e) {}

    loadGroups();
    initTabs();
    initSearch();
    initCreateModal();
});
