import { handleLogin, logout, checkAuth } from './auth.js';
import { setupTenantForm, loadTenants } from './tenants.js';
import { setupApiKeyEventListeners } from './api_keys.js';
import { setupSyncMenuButton } from './sync_menu.js'; // Nova importação

document.addEventListener('DOMContentLoaded', () => {
    // Setup
    checkAuth();
    setupTenantForm();
    setupSyncMenuButton(); // Nova chamada

    // Event Listeners
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }

    // Carrega os clientes se o usuário já estiver autenticado
    if (localStorage.getItem('accessToken')) {
        loadTenants();
    }
});
