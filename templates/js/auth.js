import { loadTenants } from './tenants.js';

const loginScreen = document.getElementById('login-screen');
const mainContent = document.getElementById('main-content');
const loginError = document.getElementById('login-error');

// Função de Login
export async function handleLogin(event) {
    event.preventDefault();
    const password = document.getElementById('password').value;
    const formData = new FormData();
    formData.append('password', password);

    try {
        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access_token);
            showMainContent();
            loginError.style.display = 'none';
            loadTenants(); // Carrega os clientes após o login
        } else {
            loginError.style.display = 'block';
        }
    } catch (error) {
        console.error('Erro no login:', error);
        loginError.style.display = 'block';
    }
}

// Função de Logout
export function logout() {
    localStorage.removeItem('accessToken');
    showLoginScreen();
}

export function showLoginScreen() {
    loginScreen.style.display = 'flex';
    mainContent.style.display = 'none';
}

export function showMainContent() {
    loginScreen.style.display = 'none';
    mainContent.style.display = 'block';
}

export function checkAuth() {
    if (localStorage.getItem('accessToken')) {
        showMainContent();
    } else {
        showLoginScreen();
    }
}
