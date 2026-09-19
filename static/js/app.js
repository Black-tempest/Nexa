Nexa.init = function () {
    this.loadAuth();
    this.setActiveNav();
    this.initLogout();

    if (this.isLoggedIn()) {
        const navbar = document.getElementById('main-navbar');
        const content = document.getElementById('main-content');
        if (navbar) navbar.classList.remove('hidden');
        if (content) content.style.paddingTop = '72px';
        this.updateNavBadges();
        setInterval(function () { Nexa.updateNavBadges(); }, 30000);
    } else {
        const content = document.getElementById('main-content');
        if (content) content.style.paddingTop = '0';
    }
};
