const Nexa = {
    token: null,
    user: null
};

Nexa.loadAuth = function () {
    this.token = localStorage.getItem('nexa_token');
    const u = localStorage.getItem('nexa_user');
    if (u) {
        try { this.user = JSON.parse(u); } catch (e) { this.user = null; }
    }
};

Nexa.saveAuth = function (token, user) {
    this.token = token;
    this.user = user;
    localStorage.setItem('nexa_token', token);
    localStorage.setItem('nexa_user', JSON.stringify(user));
};

Nexa.clearAuth = function () {
    this.token = null;
    this.user = null;
    localStorage.removeItem('nexa_token');
    localStorage.removeItem('nexa_user');
};

Nexa.isLoggedIn = function () {
    return !!this.token;
};

Nexa.api = async function (path, options) {
    options = options || {};
    const headers = options.headers || {};
    headers['Content-Type'] = 'application/json';
    if (this.token) {
        headers['Authorization'] = 'Bearer ' + this.token;
    }
    options.headers = headers;

    const res = await fetch(path, options);

    if (res.status === 401) {
        this.clearAuth();
        if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
            window.location.href = '/login';
        }
        throw new Error('Not authenticated');
    }

    const data = await res.json();
    return data;
};

Nexa.get = function (path) {
    return this.api(path, { method: 'GET' });
};

Nexa.post = function (path, body) {
    return this.api(path, {
        method: 'POST',
        body: JSON.stringify(body || {})
    });
};

Nexa.del = function (path) {
    return this.api(path, { method: 'DELETE' });
};

Nexa.avatarUrl = function (user) {
    if (!user) return '';
    if (user.avatar) return user.avatar;
    const seed = user.username || user.id || 'x';
    const hue = (String(seed).charCodeAt(0) * 37) % 360;
    const letter = (user.display_name || user.username || '?').charAt(0).toUpperCase();
    return 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
        '<rect fill="hsl(' + hue + ',60%,45%)" width="100" height="100"/>' +
        '<text x="50" y="65" font-size="50" text-anchor="middle" fill="white" font-family="Arial">' +
        letter +
        '</text></svg>'
    );
};

Nexa.timeAgo = function (ms) {
    if (!ms) return '';
    const s = Math.floor((Date.now() - ms) / 1000);
    if (s < 60) return 'à l\'instant';
    if (s < 3600) return Math.floor(s / 60) + 'min';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    if (s < 604800) return Math.floor(s / 86400) + 'j';
    const d = new Date(ms);
    return d.toLocaleDateString('fr-FR');
};

Nexa.escapeHtml = function (text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
};

Nexa.formatDate = function (ms) {
    if (!ms) return '';
    const d = new Date(ms);
    return d.toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' });
};

window.showToast = function (message, type) {
    type = type || 'info';
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function () {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }, 3000);
};

Nexa.updateNavBadges = async function () {
    if (!this.isLoggedIn()) return;

    try {
        const pm = await this.get('/api/chat/unread');
        const pmBadge = document.getElementById('unread-badge');
        if (pmBadge) {
            if (pm.ok && pm.count > 0) {
                pmBadge.textContent = pm.count > 99 ? '99+' : pm.count;
                pmBadge.classList.remove('hidden');
            } else {
                pmBadge.classList.add('hidden');
            }
        }
    } catch (e) {}

    try {
        const n = await this.get('/api/notifications/unread');
        const nBadge = document.getElementById('notif-badge');
        if (nBadge) {
            if (n.ok && n.count > 0) {
                nBadge.textContent = n.count > 99 ? '99+' : n.count;
                nBadge.classList.remove('hidden');
            } else {
                nBadge.classList.add('hidden');
            }
        }
    } catch (e) {}
};

Nexa.setActiveNav = function () {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(function (link) {
        const href = link.getAttribute('href');
        if (href && path.indexOf(href) === 0) {
            link.classList.add('active');
        }
    });
    document.querySelectorAll('.sidebar-link').forEach(function (link) {
        const href = link.getAttribute('href');
        if (href && path.indexOf(href) === 0) {
            link.classList.add('active');
        }
    });
};

Nexa.initLogout = function () {
    const btn = document.getElementById('logout-btn');
    if (!btn) return;
    btn.addEventListener('click', async function () {
        try { await Nexa.post('/api/auth/logout'); } catch (e) {}
        Nexa.clearAuth();
        window.location.href = '/';
    });
};

Nexa.init = function () {
    this.loadAuth();
    this.setActiveNav();
    this.initLogout();

    if (this.isLoggedIn()) {
        this.updateNavBadges();
        setInterval(function () { Nexa.updateNavBadges(); }, 30000);
    }
};

window.Nexa = Nexa;

document.addEventListener('DOMContentLoaded', function () {
    Nexa.init();
});
