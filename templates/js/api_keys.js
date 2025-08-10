import { authenticatedFetch } from './api.js';

let currentTenantId = null;

async function loadApiKeys(tenantId) {
    currentTenantId = tenantId;
    const apiKeySection = document.getElementById('api-key-management-section');
    const apiKeysList = document.getElementById('api-keys-list');
    if (!apiKeySection || !apiKeysList) return;

    apiKeySection.style.display = 'block';

    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}/keys/`);
        if (!response.ok) throw new Error('Falha ao carregar chaves de API.');
        const keys = await response.json();

        apiKeysList.innerHTML = '';
        if (keys.length === 0) {
            apiKeysList.innerHTML = '<li>Nenhuma chave de API cadastrada.</li>';
            return;
        }

        keys.forEach(key => {
            const listItem = document.createElement('li');
            listItem.className = 'item-list-item';
            listItem.innerHTML = `
                <span class="item-name">****${key.api_key_value.slice(-4)} (${key.key_type} - Prio: ${key.priority})</span>
                <div class="item-actions">
                    <button class="button delete-button delete-apikey-button" data-key-id="${key.id}">Excluir</button>
                </div>
            `;
            apiKeysList.appendChild(listItem);
        });
    } catch (error) {
        console.error('Erro ao carregar chaves de API:', error);
        apiKeysList.innerHTML = '<li>Erro ao carregar chaves.</li>';
    }
}

async function handleApiKeyFormSubmit(event) {
    event.preventDefault();
    if (!currentTenantId) {
        alert('Selecione um cliente primeiro.');
        return;
    }

    const form = event.target;
    const keyData = {
        api_key_value: form.api_key_value.value,
        key_type: form.key_type.value,
        priority: parseInt(form.priority.value, 10)
    };

    try {
        const response = await authenticatedFetch(`/tenants/${currentTenantId}/keys/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(keyData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Falha ao salvar a chave de API.');
        }

        alert('Chave de API adicionada com sucesso!');
        form.reset();
        loadApiKeys(currentTenantId);
    } catch (error) {
        console.error('Erro ao salvar chave de API:', error);
        alert(error.message);
    }
}

async function handleApiKeyDelete(keyId) {
    if (!currentTenantId || !keyId) return;
    if (!confirm('Tem certeza que deseja excluir esta chave de API?')) return;

    try {
        const response = await authenticatedFetch(`/tenants/${currentTenantId}/keys/${keyId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Falha ao excluir a chave.');
        }

        alert('Chave de API excluída com sucesso!');
        loadApiKeys(currentTenantId);
    } catch (error) {
        console.error('Erro ao excluir chave de API:', error);
        alert(error.message);
    }
}

export function setupApiKeyEventListeners(tenantId) {
    currentTenantId = tenantId;
    const apiKeyForm = document.getElementById('api-key-form');
    const apiKeysList = document.getElementById('api-keys-list');

    if (apiKeyForm) {
        apiKeyForm.addEventListener('submit', handleApiKeyFormSubmit);
    }

    if (apiKeysList) {
        apiKeysList.addEventListener('click', (event) => {
            if (event.target.classList.contains('delete-apikey-button')) {
                const keyId = event.target.dataset.keyId;
                handleApiKeyDelete(keyId);
            }
        });
    }

    loadApiKeys(tenantId);
}
