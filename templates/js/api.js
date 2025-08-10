import { logout } from './auth.js';

// Função para fazer requisições autenticadas
export async function authenticatedFetch(url, options = {}) {
    const token = localStorage.getItem('accessToken');
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
        // Token expirado ou inválido, força o logout
        logout();
        throw new Error('Sessão expirada. Por favor, faça login novamente.');
    }

    return response;
}
