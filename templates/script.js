// JavaScript for the AI Customer Service Assistant Configuration Page

document.addEventListener('DOMContentLoaded', () => {
    checkAuthAndLoadContent();
});

let editingTenantId = null;

async function checkAuthAndLoadContent() {
    const accessToken = localStorage.getItem('access_token');
    if (accessToken) {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('main-content').style.display = 'block';
        fetchClients();
        populateFreteSelect();
    } else {
        document.getElementById('login-screen').style.display = 'flex';
        document.getElementById('main-content').style.display = 'none';
    }
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('login-error');

    try {
        const formData = new FormData();
        formData.append('password', password);

        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            localStorage.setItem('access_token', result.access_token);
            checkAuthAndLoadContent();
        } else {
            const errorData = await response.json();
            errorMessage.textContent = errorData.detail || "Senha incorreta.";
            errorMessage.style.display = 'block';
        }
    } catch (error) {
        errorMessage.textContent = "Erro de rede ou servidor.";
        errorMessage.style.display = 'block';
        console.error("Login error:", error);
    }
});

// Função auxiliar para adicionar o token às requisições
async function authenticatedFetch(url, options = {}) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        // Se não tem token, redireciona para login e impede a requisição
        checkAuthAndLoadContent();
        throw new Error("Não autenticado.");
    }

    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${accessToken}`
    };

    const response = await fetch(url, options);
    
    if (response.status === 401 || response.status === 403) {
        // Token inválido ou expirado, desloga e redireciona
        logout(); // Usa a nova função de logout
        alert("Sessão expirada ou não autorizada. Faça login novamente.");
        throw new Error("Não autorizado.");
    }

    return response;
}

// Nova função de logout
function logout() {
    localStorage.removeItem('access_token');
    checkAuthAndLoadContent();
    alert("Você foi desconectado.");
}

// Conectar o botão de logout
document.getElementById('logout-button').addEventListener('click', logout);

// Agora, use authenticatedFetch em todas as chamadas que precisam de autenticação
async function fetchClients() {
    const response = await authenticatedFetch('/tenants/');
    const clients = await response.json();
    const clientList = document.getElementById('client-list');
    clientList.innerHTML = '';
    clients.forEach(client => {
        const li = document.createElement('li');
        li.className = 'client-item';
        li.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>${client.nome_loja || client.tenant_id}</strong><br>
                    <small>Instância: ${client.tenant_id}</small><br>
                    <small>Personalidade: ${client.id_pronpt || 'N/A'}</small><br>
                    <small>Endereço: ${client.endereco || 'N/A'}</small><br>
                    <small>Status: ${client.is_active ? 'Ativo' : 'Inativo'}</small>
                    ${client.menu_image_url ? `<small>Cardápio: <a href="${client.menu_image_url}" target="_blank">Ver Imagem</a></small>` : ''}
                </div>
                <div>
                    <button onclick="editClient('${client.tenant_id}')" style="background: #f39c12; margin: 2px; padding: 5px 10px; font-size: 0.8rem;">Editar</button>
                    <button onclick="toggleClientStatus('${client.tenant_id}', ${client.is_active})" style="background: ${client.is_active ? '#e74c3c' : '#27ae60'}; margin: 2px; padding: 5px 10px; font-size: 0.8rem;">${client.is_active ? 'Desativar' : 'Ativar'}</button>
                    <button onclick="deleteClient('${client.tenant_id}')" style="background: #c0392b; margin: 2px; padding: 5px 10px; font-size: 0.8rem;">Remover</button>
                </div>
            </div>
        `;
        clientList.appendChild(li);
    });
    
    // Atualizar também o select de frete
    populateFreteSelect();
}

function editClient(tenantId) {
    editingTenantId = tenantId;
    // Buscar dados do cliente para preencher o formulário
    authenticatedFetch(`/tenants/${tenantId}`)
        .then(response => response.json())
        .then(client => {
            document.getElementById('tenant_id_create').value = client.tenant_id;
            document.getElementById('nome_loja_create').value = client.nome_loja || '';
            document.getElementById('ia_personality_create').value = client.id_pronpt || '';
            document.getElementById('endereco_create').value = client.endereco || '';
            document.getElementById('cep_create').value = client.cep || '';
            document.getElementById('latitude_create').value = client.latitude || '';
            document.getElementById('longitude_create').value = client.longitude || '';

            // Lógica para loja_txt: exibir textarea ou upload
            const lojaTxtContent = document.getElementById('loja_txt_content');
            const lojaTxtUpload = document.getElementById('loja_txt_upload');
            const downloadLojaTxtBtn = document.getElementById('download_loja_txt');
            const downloadExcelBtn = document.getElementById('download_produtos_excel');

            // Oculta o campo de upload original e mostra a textarea para edição
            lojaTxtUpload.style.display = 'none';
            lojaTxtContent.style.display = 'block';
            downloadLojaTxtBtn.style.display = 'inline-block';
            downloadExcelBtn.style.display = 'inline-block';
            
            // Buscar conteúdo do loja_txt (config_ai)
            authenticatedFetch(`/tenants/${tenantId}/loja_txt`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Erro ao buscar informações da loja: ${response.statusText}`);
                    }
                    return response.text();
                })
                .then(text_content => {
                    lojaTxtContent.value = text_content; // Preenche a textarea
                })
                .catch(error => {
                    console.error("Erro ao carregar conteúdo do loja_txt:", error);
                    lojaTxtContent.value = 'Erro ao carregar informações da empresa.';
                });

            // Exibir a imagem do cardápio existente, se houver
            const menuImagePreviewDiv = document.getElementById('current_menu_image_preview');
            if (client.menu_image_url) {
                menuImagePreviewDiv.innerHTML = `<p>Imagem atual:</p><img src="${client.menu_image_url}" alt="Cardápio" style="max-width: 200px; height: auto; display: block; margin-top: 5px;">`;
            } else {
                menuImagePreviewDiv.innerHTML = '<p>Nenhuma imagem de cardápio cadastrada.</p>';
            }
            
            // Buscar o prompt da personalidade e preencher o textarea
            if (client.id_pronpt) {
                authenticatedFetch(`/personalities/${client.id_pronpt}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`Erro ao buscar personalidade: ${response.statusText}`);
                        }
                        return response.json();
                    })
                    .then(personality => {
                        document.getElementById('ai_prompt_description_create').value = personality.prompt || '';
                    })
                    .catch(error => {
                        console.error("Erro ao carregar prompt da personalidade:", error);
                        document.getElementById('ai_prompt_description_create').value = 'Erro ao carregar descrição do prompt.';
                    });
            } else {
                document.getElementById('ai_prompt_description_create').value = '';
            }
            
            // Mudar texto do botão
            document.querySelector('#create-tenant-form button[type="submit"]').textContent = 'Atualizar Cliente';
            document.getElementById('cancel-edit').style.display = 'inline-block';
            
            // Desabilitar campo tenant_id durante edição
            document.getElementById('tenant_id_create').readOnly = true;
        });
}

function cancelEdit() {
    editingTenantId = null;
    document.getElementById('create-tenant-form').reset();
    document.querySelector('#create-tenant-form button[type="submit"]').textContent = 'Salvar Cliente';
    document.getElementById('cancel-edit').style.display = 'none';
    document.getElementById('tenant_id_create').readOnly = false;
    document.getElementById('current_menu_image_preview').innerHTML = ''; // Limpar preview da imagem

    // Voltar os campos de loja_txt para o estado inicial (upload de arquivo)
    document.getElementById('loja_txt_content').style.display = 'none';
    document.getElementById('loja_txt_upload').style.display = 'block';
    document.getElementById('download_loja_txt').style.display = 'none';
    document.getElementById('download_produtos_excel').style.display = 'none';

}

async function toggleClientStatus(tenantId, currentStatus) {
    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}/toggle-status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ is_active: !currentStatus })
        });
        if (response.ok) {
            alert(`Cliente ${currentStatus ? 'desativado' : 'ativado'} com sucesso!`);
            fetchClients();
        } else {
            alert('Erro ao alterar status do cliente');
        }
    } catch (error) {
        alert(`Erro: ${error.message}`);
    }
}

async function deleteClient(tenantId) {
    if (confirm(`Tem certeza que deseja remover o cliente "${tenantId}"?`)) {
        try {
            const response = await authenticatedFetch(`/tenants/${tenantId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                alert('Cliente removido com sucesso!');
                fetchClients();
            } else {
                alert('Erro ao remover cliente');
            }
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
}

document.getElementById('create-tenant-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    // --- DEBUG: Log FormData content before sending ---
    console.log("Conteúdo do FormData antes do envio:");
    for (let pair of formData.entries()) {
        console.log(pair[0]+ ': ' + pair[1]); 
    }
    // --- FIM DEBUG ---

    // Lógica para lidar com loja_txt: priorizar textarea se visível, senão o arquivo
    const lojaTxtContentElement = document.getElementById('loja_txt_content');
    const lojaTxtUploadElement = document.getElementById('loja_txt_upload');
    
    // Remover os antigos campos do formData se eles foram incluídos automaticamente
    // (pode ser redundante, mas garante que a lógica de prioridade funciona)
    formData.delete('loja_txt'); // Remove o campo original de UploadFile
    formData.delete('loja_txt_upload'); // Remove o novo campo de UploadFile
    formData.delete('loja_txt_content'); // Remove o novo campo de textarea

    if (lojaTxtContentElement.style.display === 'block') {
        // Se a textarea está visível, use seu conteúdo
        formData.append('loja_txt', new Blob([lojaTxtContentElement.value], { type: 'text/plain' }), 'loja_info.txt');
    } else if (lojaTxtUploadElement.files.length > 0) {
        // Se a textarea não está visível e um novo arquivo foi selecionado no input de upload
        formData.append('loja_txt', lojaTxtUploadElement.files[0]);
    } else if (editingTenantId) {
        // Se está em modo de edição e nenhum novo arquivo/texto foi fornecido, 
        // precisamos enviar o valor atual do config_ai do tenant para evitar NotNullViolation
        // Isso deve ser feito buscando o tenant atual e pegando o config_ai dele.
        // No entanto, o FastAPI exige um `UploadFile` ou um `Form` para `loja_txt`.
        // A melhor abordagem é ter certeza que a `textarea` ou o `UploadFile` seja sempre preenchido/enviado.
        // Para o contexto atual de PUT, se nada for enviado, o campo `loja_txt` (no backend) será `None`.
        // O problema é que o backend espera `UploadFile` para `loja_txt` no @app.put. 
        // Uma solução mais elegante seria ter `conteudo_loja` como um campo de formulário separado, 
        // OU garantir que sempre um arquivo (ainda que vazio) seja enviado.
        // Por enquanto, vamos priorizar o que o usuário modificou na tela.
        // Se `loja_txt` não for fornecido aqui, o endpoint PUT receberá `None` para `loja_txt`,
        // o que está correto pois o parâmetro é `UploadFile = File(None)`.
        // A preocupação é se `conteudo_loja` é obrigatório no `crud.update_tenant`.
        // No crud.update_tenant, `conteudo_loja` é `Optional[str] = None`.
        // Isso significa que se `loja_txt` não for fornecido, `conteudo_loja` será `None` e o crud aceitará.
        // O problema anterior era o `nome_loja` e outros campos de texto.
        // Essa nova estrutura de `update_tenant` com `Form(...)` deve resolver isso.
        // Portanto, para `loja_txt`, o comportamento atual de só enviar se houver alteração ou novo arquivo está OK.
    }

    try {
        let url = '/tenants/';
        let method = 'POST';
        
        if (editingTenantId) {
            url = `/tenants/${editingTenantId}`;
            method = 'PUT';
        }
        
        const response = await authenticatedFetch(url, {
            method: method,
            body: formData
        });
        
        const result = await response.json();
        if (response.ok) {
            alert(editingTenantId ? 'Cliente atualizado com sucesso!' : 'Cliente criado com sucesso!');
            cancelEdit();
            fetchClients();
        } else {
            alert(`Erro: ${result.detail || response.statusText}`);
        }
    } catch (error) {
        alert(`Erro de rede: ${error.message}`);
    }
});

// Download de arquivos
document.getElementById('download_loja_txt').addEventListener('click', async () => {
    if (editingTenantId) {
        try {
            const response = await authenticatedFetch(`/tenants/${editingTenantId}/loja_txt`);
            const textContent = await response.text();
            const blob = new Blob([textContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `loja_${editingTenantId}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Erro ao baixar loja_txt:", error);
            alert("Erro ao baixar o arquivo de informações da loja.");
        }
    } else {
        alert("Selecione um cliente para baixar o arquivo.");
    }
});

document.getElementById('download_produtos_excel').addEventListener('click', () => {
    // O arquivo Excel não é armazenado como um campo no DB ou no Supabase Storage de forma direta como o TXT ou imagem.
    // Apenas seus dados são processados e salvos em `models.Product`.
    // Para permitir o download do Excel original, o backend precisaria ter um endpoint
    // que recupere o arquivo original do upload ou gere um Excel a partir dos dados do DB.
    // Isso exigiria uma mudança na arquitetura de como o Excel é armazenado.
    // Por agora, este botão será apenas um placeholder.
    alert("A funcionalidade de baixar o arquivo Excel original não está implementada, pois o arquivo não é armazenado diretamente. Apenas os dados são processados e salvos.");
});

document.getElementById('cancel-edit').addEventListener('click', cancelEdit);

// Popular select de clientes para cálculo de frete
async function populateFreteSelect() {
    const response = await authenticatedFetch('/tenants/'); // Usar authenticatedFetch
    const clients = await response.json();
    const select = document.getElementById('frete_tenant_id');
    select.innerHTML = '<option value="">Selecione uma loja...</option>';
    clients.forEach(client => {
        const option = document.createElement('option');
        option.value = client.tenant_id;
        option.textContent = `${client.tenant_id} - ${client.nome_loja || 'Sem nome de loja'}`;
        select.appendChild(option);
    });
}

// Calcular frete
document.getElementById('calcular-frete-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    try {
        const response = await authenticatedFetch('/calcular-frete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({
                tenant_id: formData.get('tenant_id'),
                cliente_lat: formData.get('cliente_lat'),
                cliente_lng: formData.get('cliente_lng')
            })
        });
        
        const result = await response.json();
        if (response.ok) {
            const resultDiv = document.getElementById('frete-result');
            resultDiv.innerHTML = `
                <h4>Resultado do Cálculo:</h4>
                <p><strong>Distância:</strong> ${result.distancia_km.toFixed(2)} km</p>
                <p><strong>Origem:</strong> ${result.origem.endereco}</p>
                <p><strong>Coordenadas da loja:</strong> ${result.origem.latitude}, ${result.origem.longitude}</p>
                <p><strong>Coordenadas do cliente:</strong> ${result.destino.latitude}, ${result.destino.longitude}</p>
            `;
            resultDiv.style.display = 'block';
        } else {
            alert(`Erro: ${result.detail}`);
        }
    } catch (error) {
        alert(`Erro: ${error.message}`);
    }
}); 