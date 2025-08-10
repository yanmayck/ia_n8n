import { authenticatedFetch } from './api.js';
import { setupApiKeyEventListeners } from './api_keys.js';

let editingTenantId = null;

// Função para carregar e exibir os tenants na lista
export async function loadTenants() {
    const clientList = document.getElementById('client-list');
    if (!clientList) return;

    try {
        const response = await authenticatedFetch('/tenants/');
        if (!response.ok) {
            throw new Error('Falha ao buscar clientes.');
        }
        const tenants = await response.json();

        clientList.innerHTML = ''; // Limpa a lista antes de adicionar os novos itens
        if (tenants.length === 0) {
            clientList.innerHTML = '<li>Nenhum cliente cadastrado.</li>';
            return;
        }

        tenants.forEach(tenant => {
            const listItem = document.createElement('li');
            listItem.className = 'client-item';
            const statusClass = tenant.is_active ? 'status-active' : 'status-inactive';
            const statusText = tenant.is_active ? 'Ativo' : 'Inativo';

            listItem.innerHTML = `
                <div>
                    <span class="client-name">${tenant.nome_loja} (${tenant.tenant_id})</span>
                    <span class="client-status ${statusClass}">${statusText}</span>
                </div>
                <div>
                    <button class="toggle-status-button" data-tenant-id="${tenant.tenant_id}" data-current-status="${tenant.is_active}">${tenant.is_active ? 'Desativar' : 'Ativar'}</button>
                    <button class="edit-button" data-tenant-id="${tenant.tenant_id}">Editar</button>
                    <button class="delete-button" data-tenant-id="${tenant.tenant_id}">Excluir</button>
                </div>
            `;
            clientList.appendChild(listItem);
        });

    } catch (error) {
        console.error('Erro ao carregar clientes:', error);
        clientList.innerHTML = '<li>Erro ao carregar clientes.</li>';
    }
}

async function handleTenantFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    const url = editingTenantId ? `/tenants/${editingTenantId}` : '/tenants/';
    const method = editingTenantId ? 'PUT' : 'POST';

    try {
        const response = await authenticatedFetch(url, {
            method: method,
            body: formData,
        });

        if (response.ok) {
            alert(`Cliente ${editingTenantId ? 'atualizado' : 'criado'} com sucesso!`);
            form.reset();
            editingTenantId = null; // Reseta o modo de edição
            document.getElementById('cancel-edit').style.display = 'none';
            document.getElementById('tenant_id_create').disabled = false;
            loadTenants(); // Atualiza a lista
        } else {
            const errorData = await response.json();
            alert(`Erro: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Erro ao salvar cliente:', error);
        alert('Ocorreu um erro de rede. Tente novamente.');
    }
}

async function handleDeleteTenant(tenantId) {
    if (!confirm(`Tem certeza que deseja excluir o cliente ${tenantId}?`)) {
        return;
    }

    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}`, {
            method: 'DELETE',
        });

        if (response.ok) {
            alert('Cliente excluído com sucesso!');
            loadTenants(); // Atualiza a lista
        } else {
            const errorData = await response.json();
            alert(`Erro ao excluir cliente: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Erro ao excluir cliente:', error);
        alert('Ocorreu um erro de rede. Tente novamente.');
    }
}

async function handleToggleStatus(tenantId, currentStatus) {
    const newStatus = !currentStatus;
    const actionText = newStatus ? 'ativar' : 'desativar';

    if (!confirm(`Tem certeza que deseja ${actionText} o cliente ${tenantId}?`)) {
        return;
    }

    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}/toggle-status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ is_active: newStatus })
        });

        if (response.ok) {
            alert(`Cliente ${actionText} com sucesso!`);
            loadTenants(); // Atualiza a lista
        } else {
            const errorData = await response.json();
            alert(`Erro ao alterar status: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Erro ao alterar status:', error);
        alert('Ocorreu um erro de rede. Tente novamente.');
    }
}

async function populateFormForEdit(tenant) {
    // Mostra o campo de texto e esconde o de upload
    const lojaTxtContent = document.getElementById('loja_txt_content');
    const lojaTxtUpload = document.getElementById('loja_txt_upload');
    const downloadLojaTxtButton = document.getElementById('download_loja_txt');

    lojaTxtContent.style.display = 'block';
    lojaTxtUpload.style.display = 'none';
    downloadLojaTxtButton.style.display = 'inline-block';
    
    // Preenche os campos básicos
    document.getElementById('tenant_id_create').value = tenant.tenant_id;
    document.getElementById('tenant_id_create').disabled = true;
    document.getElementById('nome_loja_create').value = tenant.nome_loja;
    
    // Preenche os campos de personalidade da IA
    if (tenant.personality) {
        document.getElementById('ia_personality_create').value = tenant.personality.name;
        document.getElementById('ai_prompt_description_create').value = tenant.personality.prompt;
    } else {
        document.getElementById('ia_personality_create').value = '';
        document.getElementById('ai_prompt_description_create').value = '';
    }

    document.getElementById('endereco_create').value = tenant.endereco;
    document.getElementById('cep_create').value = tenant.cep;
    document.getElementById('latitude_create').value = tenant.latitude;
    document.getElementById('longitude_create').value = tenant.longitude;
    document.getElementById('freight_config_create').value = tenant.freight_config;

    // Busca e preenche o conteúdo do arquivo de texto
    try {
        const response = await authenticatedFetch(`/tenants/${tenant.tenant_id}/loja_txt`);
        if (response.ok) {
            const textContent = await response.text();
            lojaTxtContent.value = textContent;
        } else {
            lojaTxtContent.value = "Erro ao carregar a descrição da loja.";
        }
    } catch (error) {
        console.error("Erro ao buscar loja.txt:", error);
        lojaTxtContent.value = "Não foi possível carregar a descrição da loja.";
    }
    
    // Configura o botão de download
    downloadLojaTxtButton.onclick = () => {
        const blob = new Blob([lojaTxtContent.value], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `${tenant.tenant_id}_loja.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    };

    editingTenantId = tenant.tenant_id;
    document.getElementById('cancel-edit').style.display = 'inline-block';
    
    // Ativa a seção de produtos e carrega a lista
    document.getElementById('product-management-section').style.display = 'block';
    localStorage.setItem('selectedTenantId', tenant.tenant_id); // Armazena o tenantId selecionado
    setupApiKeyEventListeners(tenant.tenant_id);

    window.scrollTo(0, 0); // Rola para o topo para mostrar o formulário de edição
}

export function setupTenantForm() {
    const createTenantForm = document.getElementById('create-tenant-form');
    const clientList = document.getElementById('client-list');
    const cancelEditButton = document.getElementById('cancel-edit');

    if (createTenantForm) {
        createTenantForm.addEventListener('submit', handleTenantFormSubmit);
    }

    if (clientList) {
        clientList.addEventListener('click', (event) => {
            const button = event.target;
            const tenantId = button.dataset.tenantId;

            if (button.classList.contains('edit-button')) {
                authenticatedFetch(`/tenants/${tenantId}`)
                    .then(response => response.json())
                    .then(tenant => populateFormForEdit(tenant))
                    .catch(err => console.error('Falha ao buscar dados do cliente para edição:', err));
            } else if (button.classList.contains('delete-button')) {
                handleDeleteTenant(tenantId);
            } else if (button.classList.contains('toggle-status-button')) {
                const currentStatus = button.dataset.currentStatus === 'true';
                handleToggleStatus(tenantId, currentStatus);
            }
        });
    }

    if(cancelEditButton) {
        cancelEditButton.addEventListener('click', () => {
            editingTenantId = null;
            createTenantForm.reset();
            document.getElementById('tenant_id_create').disabled = false;
            cancelEditButton.style.display = 'none';

            // Restaura a visibilidade dos campos de arquivo
            document.getElementById('loja_txt_content').style.display = 'none';
            document.getElementById('loja_txt_upload').style.display = 'block';
            document.getElementById('download_loja_txt').style.display = 'none';
            
            // Esconde a seção de produtos
            document.getElementById('product-management-section').style.display = 'none';
            document.getElementById('api-key-management-section').style.display = 'none';
            localStorage.removeItem('selectedTenantId'); // Limpa o tenantId selecionado
        });
    }
}