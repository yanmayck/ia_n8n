import { authenticatedFetch } from './api.js';

export function setupSyncMenuButton() {
    const syncMenuButton = document.getElementById('sync-menu-button');
    if (syncMenuButton) {
        syncMenuButton.addEventListener('click', handleSyncMenu);
    }
}

async function handleSyncMenu() {
    const currentTenantId = localStorage.getItem('selectedTenantId'); // Assumindo que o tenant ID selecionado é armazenado aqui
    if (!currentTenantId) {
        alert('Por favor, selecione um cliente primeiro.');
        return;
    }

    if (!confirm(`Tem certeza que deseja sincronizar o cardápio para o cliente ${currentTenantId}? Isso irá sobrescrever os dados existentes.`)) {
        return;
    }

    try {
        // Chamar o novo endpoint de sincronização na API da IA
        const response = await authenticatedFetch(`/tenants/${currentTenantId}/sync-menu`, {
            method: 'POST',
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Falha ao sincronizar o cardápio.');
        }

        alert('Cardápio sincronizado com sucesso!');
    } catch (error) {
        console.error('Erro ao sincronizar cardápio:', error);
        alert(error.message);
    }
}
