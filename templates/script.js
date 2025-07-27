document.addEventListener('DOMContentLoaded', () => {
    checkAuthAndLoadContent();
    setupTabSwitching();
    updateFormAndButtonStates(false);
    attachStaticEventListeners();
});

let editingTenantId = null;
let editingProductId = null;
let editingOpcionalId = null;
let editingPromocaoId = null;

// --- Core Functions ---

async function checkAuthAndLoadContent() {
    console.log("Checking auth and loading content");
    const loginScreen = document.getElementById('login-screen');
    const mainContent = document.getElementById('main-content');

    if (localStorage.getItem('access_token')) {
        console.log("Access token found");
        if (loginScreen) loginScreen.style.display = 'none';
        if (mainContent) mainContent.style.display = 'block';
        try {
            await fetchClients();
            await populateFreteSelect();
        } catch (error) {
            console.error("Authentication failed during initial load:", error);
        }
    } else {
        console.log("No access token found");
        if (loginScreen) loginScreen.style.display = 'flex';
        if (mainContent) mainContent.style.display = 'none';
    }
}

function updateFormAndButtonStates(isEditing) {
    const tenantIdField = document.getElementById('tenant_id_create');
    if (tenantIdField) tenantIdField.readOnly = isEditing;

    const submitButton = document.querySelector('#create-tenant-form button[type="submit"]');
    if (submitButton) submitButton.textContent = isEditing ? 'Atualizar Cliente' : 'Salvar Cliente';

    const cancelEditButton = document.getElementById('cancel-edit');
    if (cancelEditButton) cancelEditButton.style.display = isEditing ? 'inline-block' : 'none';

    const menuImagesUpload = document.getElementById('menu_images_upload');
    if (menuImagesUpload) menuImagesUpload.disabled = !isEditing;
    
    const uploadMenuImagesButton = document.getElementById('upload-menu-images');
    if (uploadMenuImagesButton) uploadMenuImagesButton.disabled = !isEditing;

    // Clear and set initial text if not editing
    if (!isEditing) {
        document.getElementById('products-list').innerHTML = '<p>Selecione um cliente para gerenciar.</p>';
        document.getElementById('opcionais-list').innerHTML = '<p>Selecione um cliente para gerenciar.</p>';
        document.getElementById('promocoes-list').innerHTML = '<p>Selecione um cliente para gerenciar.</p>';
        document.getElementById('uploaded-menu-images-preview').innerHTML = '<p>Selecione um cliente para gerenciar.</p>';

        // Reset forms
        document.getElementById('product-form')?.reset();
        document.getElementById('opcional-form')?.reset();
        document.getElementById('promocao-form')?.reset();
        editingProductId = null;
        editingOpcionalId = null;
        editingPromocaoId = null;
    }
}

function attachStaticEventListeners() {
    document.getElementById('login-form')?.addEventListener('submit', handleLogin);
    document.getElementById('logout-button')?.addEventListener('click', logout);
    document.getElementById('create-tenant-form')?.addEventListener('submit', handleTenantFormSubmit);
    document.getElementById('cancel-edit')?.addEventListener('click', cancelEdit);
    document.getElementById('download_loja_txt')?.addEventListener('click', downloadLojaTxt);
    document.getElementById('calcular-frete-form')?.addEventListener('submit', handleFreightCalculation);
    document.getElementById('upload-menu-images')?.addEventListener('click', handleUploadMenuImages);

    // Product, Opcional, Promocao form submissions
    document.getElementById('product-form')?.addEventListener('submit', handleProductFormSubmit);
    document.getElementById('opcional-form')?.addEventListener('submit', handleOpcionalFormSubmit);
    document.getElementById('promocao-form')?.addEventListener('submit', handlePromocaoFormSubmit);

    // Cancel buttons for product, opcional, promocao forms
    document.getElementById('cancel-product-edit')?.addEventListener('click', () => resetForm('product-form', 'editingProductId'));
    document.getElementById('cancel-opcional-edit')?.addEventListener('click', () => resetForm('opcional-form', 'editingOpcionalId'));
    document.getElementById('cancel-promocao-edit')?.addEventListener('click', () => resetForm('promocao-form', 'editingPromocaoId'));

    setupPromocaoForm();

    // Event delegation for item lists
    document.getElementById('products-list')?.addEventListener('click', handleItemClick);
    document.getElementById('opcionais-list')?.addEventListener('click', handleItemClick);
    document.getElementById('promocoes-list')?.addEventListener('click', handleItemClick);
}

function resetForm(formId, editingIdVar) {
    document.getElementById(formId)?.reset();
    window[editingIdVar] = null;
}

async function handleItemClick(event) {
    const target = event.target;
    const listItem = target.closest('li');
    if (!listItem) return;

    const id = listItem.dataset.id;
    const type = listItem.dataset.type;

    if (target.classList.contains('edit-button')) {
        if (type === 'product') await editProduct(id);
        else if (type === 'opcional') await editOpcional(id);
        else if (type === 'promocao') await editPromocao(id);
    } else if (target.classList.contains('delete-button')) {
        if (type === 'product') await deleteProduct(id);
        else if (type === 'opcional') await deleteOpcional(id);
        else if (type === 'promocao') await deletePromocao(id);
    }
}

// --- Authentication ---

async function handleLogin(e) {
    e.preventDefault();
    const passwordInput = document.getElementById('password');
    const errorMessage = document.getElementById('login-error');
    if (!passwordInput || !errorMessage) return;

    const formData = new FormData();
    formData.append('password', passwordInput.value);

    try {
        const response = await fetch('/login', { method: 'POST', body: formData });
        if (response.ok) {
            const result = await response.json();
            console.log("Login successful, saving token");
            localStorage.setItem('access_token', result.access_token);
            await checkAuthAndLoadContent();
        } else {
            const errorData = await response.json();
            errorMessage.textContent = errorData.detail || "Senha incorreta.";
            errorMessage.style.display = 'block';
        }
    } catch (error) {
        errorMessage.textContent = "Erro de rede ou servidor.";
        errorMessage.style.display = 'block';
    }
}

function logout() {
    localStorage.removeItem('access_token');
    window.location.reload();
}

async function authenticatedFetch(url, options = {}) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        logout();
        throw new Error("Não autenticado.");
    }
    options.headers = { ...options.headers, 'Authorization': `Bearer ${accessToken}` };
    const response = await fetch(url, options);
    if ([401, 403].includes(response.status)) {
        logout();
        throw new Error("Sessão expirada ou não autorizada.");
    }
    return response;
}

// --- Tenant Management ---

async function fetchClients() {
    console.log("Fetching clients");
    try {
        const response = await authenticatedFetch('/tenants/');
        const clients = await response.json();
        console.log("Clients received:", clients);
        const clientList = document.getElementById('client-list');
        if (!clientList) return;
        clientList.innerHTML = '';
        clients.forEach(client => {
            const li = document.createElement('li');
            li.className = 'client-item';
            li.innerHTML = `
                <div>
                    <strong>${client.nome_loja || client.tenant_id}</strong><br>
                    <small>ID: ${client.tenant_id} | ${client.is_active ? 'Ativo' : 'Inativo'}</small>
                </div>
                <div class="button-group">
                    <button onclick="editClient('${client.tenant_id}')">Editar</button>
                    <button onclick="deleteClient('${client.tenant_id}')">Remover</button>
                    <button onclick="toggleClientStatus('${client.tenant_id}', ${client.is_active})">${client.is_active ? 'Desativar' : 'Ativar'}</button>
                </div>`;
            clientList.appendChild(li);
        });
    } catch (error) {
        console.error("Erro ao buscar clientes:", error);
    }
}

async function toggleClientStatus(tenantId, currentStatus) {
    const newStatus = !currentStatus;
    if (confirm(`Tem certeza que deseja ${newStatus ? 'ativar' : 'desativar'} o cliente "${tenantId}"?`)) {
        try {
            const response = await authenticatedFetch(`/tenants/${tenantId}/toggle-status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: newStatus })
            });
            if (response.ok) {
                alert(`Cliente ${tenantId} ${newStatus ? 'ativado' : 'desativado'} com sucesso!`);
                await fetchClients(); // Recarrega a lista para atualizar o status
            } else {
                const errorJson = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
                alert(`Erro ao alterar status do cliente: ${errorJson.detail}`);
            }
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
}

async function editClient(tenantId) {
    editingTenantId = tenantId;
    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}`);
        const client = await response.json();

        document.getElementById('tenant_id_create').value = client.tenant_id;
        document.getElementById('nome_loja_create').value = client.nome_loja || '';
        document.getElementById('ia_personality_create').value = client.id_pronpt || '';
        document.getElementById('endereco_create').value = client.endereco || '';
        document.getElementById('cep_create').value = client.cep || '';
        document.getElementById('latitude_create').value = client.latitude || '';
        document.getElementById('longitude_create').value = client.longitude || '';
        document.getElementById('freight_config_create').value = client.freight_config || '';

        await fetchAndDisplayLojaTxt(tenantId);
        
        if (client.id_pronpt) {
            await fetchAndDisplayPersonalityPrompt(client.id_pronpt);
        } else {
            const promptDesc = document.getElementById('ai_prompt_description_create');
            if (promptDesc) promptDesc.value = '';
        }

        updateFormAndButtonStates(true);

        // Load related data for the selected tenant
        await Promise.all([
            loadProducts(tenantId),
            loadOpcionais(tenantId),
            loadPromocoes(tenantId),
            loadMenuImages(tenantId)
        ]);

    } catch (error) {
        console.error("Erro ao editar cliente:", error);
        alert("Não foi possível carregar os dados do cliente.");
        cancelEdit();
    }
}

function cancelEdit() {
    editingTenantId = null;
    document.getElementById('create-tenant-form')?.reset();
    
    const lojaTxtContent = document.getElementById('loja_txt_content');
    if (lojaTxtContent) lojaTxtContent.style.display = 'none';

    const lojaTxtUpload = document.getElementById('loja_txt_upload');
    if (lojaTxtUpload) lojaTxtUpload.style.display = 'block';

    const downloadLojaTxtBtn = document.getElementById('download_loja_txt');
    if (downloadLojaTxtBtn) downloadLojaTxtBtn.style.display = 'none';

    updateFormAndButtonStates(false);
}

async function handleTenantFormSubmit(e) {
    e.preventDefault();
    const form = e.target;
    if (!form) return;

    const formData = new FormData(form);
    const lojaTxtContentEl = document.getElementById('loja_txt_content');
    const lojaTxtUploadEl = document.getElementById('loja_txt_upload');

    if (editingTenantId && lojaTxtContentEl?.value) {
        formData.append('loja_txt', new Blob([lojaTxtContentEl.value], { type: 'text/plain' }), 'loja_info.txt');
    } else if (lojaTxtUploadEl?.files[0]) {
        formData.append('loja_txt', lojaTxtUploadEl.files[0]);
    }

    const url = editingTenantId ? `/tenants/${editingTenantId}` : '/tenants/';
    const method = editingTenantId ? 'PUT' : 'POST';

    try {
        const response = await authenticatedFetch(url, { method, body: formData });
        if (response.ok) {
            alert(`Cliente ${editingTenantId ? 'atualizado' : 'criado'} com sucesso!`);
            cancelEdit();
            await fetchClients();
        } else {
            const errorJson = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
            alert(`Erro ao salvar cliente: ${errorJson.detail}`);
        }
    } catch (error) {
        alert(`Erro de rede: ${error.message}`);
    }
}

async function deleteClient(tenantId) {
    if (confirm(`Tem certeza que deseja remover o cliente "${tenantId}"?`)) {
        try {
            const response = await authenticatedFetch(`/tenants/${tenantId}`, { method: 'DELETE' });
            if (response.ok) {
                alert('Cliente removido com sucesso!');
                await fetchClients();
                if (editingTenantId === tenantId) cancelEdit();
            } else {
                const errorJson = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
                alert(`Erro ao remover cliente: ${errorJson.detail}`);
            }
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
}

// --- Helper Functions ---

async function fetchAndDisplayLojaTxt(tenantId) {
    const lojaTxtContent = document.getElementById('loja_txt_content');
    const lojaTxtUpload = document.getElementById('loja_txt_upload');
    const downloadLojaTxtBtn = document.getElementById('download_loja_txt');
    
    if (!lojaTxtContent || !lojaTxtUpload || !downloadLojaTxtBtn) return;

    lojaTxtUpload.style.display = 'none';
    lojaTxtContent.style.display = 'block';
    downloadLojaTxtBtn.style.display = 'inline-block';

    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}/loja_txt`);
        lojaTxtContent.value = await response.text();
    } catch (error) {
        lojaTxtContent.value = 'Erro ao carregar informações da empresa.';
    }
}

async function fetchAndDisplayPersonalityPrompt(personalityName) {
    const promptDesc = document.getElementById('ai_prompt_description_create');
    if (!promptDesc) return;
    try {
        const response = await authenticatedFetch(`/personalities/${personalityName}`);
        const personality = await response.json();
        promptDesc.value = personality.prompt || '';
    } catch (error) {
        promptDesc.value = 'Erro ao carregar descrição do prompt.';
    }
}

async function downloadLojaTxt() {
    if (!editingTenantId) return;
    try {
        const response = await authenticatedFetch(`/tenants/${editingTenantId}/loja_txt`);
        const blob = new Blob([await response.text()], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement('a'), { href: url, download: `loja_${editingTenantId}.txt` });
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
    } catch (error) {
        alert("Erro ao baixar o arquivo.");
    }
}

// --- Freight Calculation ---

async function populateFreteSelect() {
    const select = document.getElementById('frete_tenant_id');
    if (!select) return;
    try {
        const response = await authenticatedFetch('/tenants/');
        const clients = await response.json();
        select.innerHTML = '<option value="">Selecione uma loja...</option>';
        clients.forEach(client => {
            if (client.is_active) {
                select.add(new Option(`${client.nome_loja || client.tenant_id}`, client.tenant_id));
            }
        });
    } catch (error) {
        console.error("Erro ao popular seleção de frete:", error);
    }
}

async function handleFreightCalculation(e) {
    e.preventDefault();
    const form = e.target;
    const resultDiv = document.getElementById('frete-result');
    if (!form || !resultDiv) return;

    const formData = new FormData(form);
    const params = new URLSearchParams({ tenant_id: formData.get('tenant_id'), cliente_lat: formData.get('cliente_lat'), cliente_lng: formData.get('cliente_lng') });

    try {
        const response = await authenticatedFetch(`/calcular-frete?${params.toString()}`);
        const result = await response.json();
        resultDiv.style.display = 'block';
        if (response.ok) {
            resultDiv.innerHTML = `<h4>Resultado:</h4><p><strong>Distância:</strong> ${result.distancia_km.toFixed(2)} km</p><p><strong>Valor do Frete:</strong> R$ ${result.valor_frete.toFixed(2)}</p>`;
        } else {
            resultDiv.innerHTML = `<p style="color: red;">Erro: ${result.detail}</p>`;
        }
    } catch (error) {
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = `<p style="color: red;">Erro na comunicação: ${error.message}</p>`;
    }
}

// --- Tab Switching ---

function setupTabSwitching() {
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
            button.classList.add('active');
            const tabPane = document.getElementById(`${button.dataset.tab}-tab`);
            if (tabPane) tabPane.classList.add('active');
        });
    });
}

// --- Product Management ---

async function loadProducts(tenantId) {
    const productList = document.getElementById('products-list');
    if (!productList) return;
    productList.innerHTML = '<p>Carregando produtos...</p>';
    try {
        const response = await authenticatedFetch(`/products/${tenantId}`);
        const products = await response.json();
        
        console.log(`Produtos recebidos para o tenant ${tenantId}:`, JSON.stringify(products, null, 2)); // Log dos produtos recebidos

        productList.innerHTML = '';
        if (products.length === 0) {
            productList.innerHTML = '<p>Nenhum produto cadastrado.</p>';
            return;
        }
        products.forEach(product => {
            const li = document.createElement('li');
            li.dataset.id = product.id_produto;
            li.dataset.type = 'product';
            const preco = typeof product.preco_base === 'number' ? product.preco_base.toFixed(2) : '0.00';
            li.innerHTML = `
                <span class="item-name">${product.nome_produto} (R$ ${preco})</span>
                <div class="item-actions">
                    <button class="edit-button">Editar</button>
                    <button class="delete-button">Remover</button>
                </div>`;
            productList.appendChild(li);
        });
    } catch (error) {
        console.error("Erro ao carregar produtos:", error);
        productList.innerHTML = '<p>Erro ao carregar produtos.</p>';
    }
}

async function editProduct(productId) {
    if (!editingTenantId) return;
    try {
        const product = await (await authenticatedFetch(`/products/${editingTenantId}/${productId}`)).json();
        document.getElementById('product_id').value = product.id_produto;
        document.getElementById('nome_produto').value = product.nome_produto;
        document.getElementById('descricao_produto').value = product.descricao_produto || '';
        document.getElementById('categoria_produto').value = product.categoria_produto || '';
        document.getElementById('preco_base').value = product.preco_base;
        document.getElementById('tempo_preparo_min').value = product.tempo_preparo_min || '';
        document.getElementById('disponivel_hoje').checked = product.disponivel_hoje === 'Sim';
        editingProductId = productId;
        loadProductOpcionalLinking(productId);
    } catch (error) {
        console.error("Erro ao carregar produto para edição:", error);
        alert("Não foi possível carregar o produto para edição.");
    }
}

async function handleProductFormSubmit(e) {
    e.preventDefault();
    if (!editingTenantId) return;
    const form = e.target;
    const formData = {
        nome_produto: form.nome_produto.value,
        descricao_produto: form.descricao_produto.value,
        categoria_produto: form.categoria_produto.value,
        preco_base: parseFloat(form.preco_base.value),
        tempo_preparo_min: parseInt(form.tempo_preparo_min.value) || null,
        disponivel_hoje: form.disponivel_hoje.checked ? 'Sim' : 'Não'
    };

    const url = editingProductId ? `/products/${editingTenantId}/${editingProductId}` : `/products/${editingTenantId}`;
    const method = editingProductId ? 'PUT' : 'POST';

    try {
        const response = await authenticatedFetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert(`Produto ${editingProductId ? 'atualizado' : 'adicionado'} com sucesso!`);
        resetForm('product-form', 'editingProductId');
        loadProducts(editingTenantId);
    } catch (error) {
        alert(`Erro ao salvar produto: ${error.message}`);
    }
}

async function deleteProduct(productId) {
    if (!editingTenantId || !confirm('Tem certeza que deseja remover este produto?')) return;
    try {
        const response = await authenticatedFetch(`/products/${editingTenantId}/${productId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert('Produto removido com sucesso!');
        loadProducts(editingTenantId);
    } catch (error) {
        alert(`Erro ao remover produto: ${error.message}`);
    }
}

// --- Opcional Management ---

async function loadOpcionais(tenantId) {
    const opcionalList = document.getElementById('opcionais-list');
    if (!opcionalList) return;
    opcionalList.innerHTML = '<p>Carregando opcionais...</p>';
    try {
        const opcionais = await (await authenticatedFetch(`/opcionais/${tenantId}`)).json();
        opcionalList.innerHTML = '';
        if (opcionais.length === 0) {
            opcionalList.innerHTML = '<p>Nenhum opcional cadastrado.</p>';
            return;
        }
        opcionais.forEach(opcional => {
            const li = document.createElement('li');
            li.dataset.id = opcional.id_opcional;
            li.dataset.type = 'opcional';
            const preco = typeof opcional.preco_adicional === 'number' ? opcional.preco_adicional.toFixed(2) : '0.00';
            li.innerHTML = `
                <span class="item-name">${opcional.nome_opcional} (R$ ${preco})</span>
                <div class="item-actions">
                    <button class="edit-button">Editar</button>
                    <button class="delete-button">Remover</button>
                </div>`;
            opcionalList.appendChild(li);
        });
    } catch (error) {
        console.error("Erro ao carregar opcionais:", error);
        opcionalList.innerHTML = '<p>Erro ao carregar opcionais.</p>';
    }
}

async function editOpcional(opcionalId) {
    if (!editingTenantId) return;
    try {
        const opcional = await (await authenticatedFetch(`/opcionais/${editingTenantId}/${opcionalId}`)).json();
        document.getElementById('opcional_id').value = opcional.id_opcional;
        document.getElementById('nome_opcional').value = opcional.nome_opcional;
        document.getElementById('tipo_opcional').value = opcional.tipo_opcional || '';
        document.getElementById('preco_adicional').value = opcional.preco_adicional;
        editingOpcionalId = opcionalId;
    } catch (error) {
        console.error("Erro ao carregar opcional para edição:", error);
        alert("Não foi possível carregar o opcional para edição.");
    }
}

async function handleOpcionalFormSubmit(e) {
    e.preventDefault();
    if (!editingTenantId) return;
    const form = e.target;
    const formData = {
        nome_opcional: form.nome_opcional.value,
        tipo_opcional: form.tipo_opcional.value,
        preco_adicional: parseFloat(form.preco_adicional.value)
    };

    const url = editingOpcionalId ? `/opcionais/${editingTenantId}/${editingOpcionalId}` : `/opcionais/${editingTenantId}`;
    const method = editingOpcionalId ? 'PUT' : 'POST';

    try {
        const response = await authenticatedFetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert(`Opcional ${editingOpcionalId ? 'atualizado' : 'adicionado'} com sucesso!`);
        resetForm('opcional-form', 'editingOpcionalId');
        loadOpcionais(editingTenantId);
    } catch (error) {
        alert(`Erro ao salvar opcional: ${error.message}`);
    }
}

async function deleteOpcional(opcionalId) {
    if (!editingTenantId || !confirm('Tem certeza que deseja remover este opcional?')) return;
    try {
        const response = await authenticatedFetch(`/opcionais/${editingTenantId}/${opcionalId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert('Opcional removido com sucesso!');
        loadOpcionais(editingTenantId);
    } catch (error) {
        alert(`Erro ao remover opcional: ${error.message}`);
    }
}

// --- Promocao Management ---

async function loadPromocoes(tenantId) {
    const promocaoList = document.getElementById('promocoes-list');
    if (!promocaoList) return;
    promocaoList.innerHTML = '<p>Carregando promoções...</p>';
    try {
        const response = await authenticatedFetch(`/promocoes/${tenantId}`);
        const promocoes = await response.json();

        console.log(`Promoções recebidas para o tenant ${tenantId}:`, JSON.stringify(promocoes, null, 2)); // Log

        promocaoList.innerHTML = '';
        if (promocoes.length === 0) {
            promocaoList.innerHTML = '<p>Nenhuma promoção cadastrada.</p>';
            return;
        }
        promocoes.forEach(promocao => {
            const li = document.createElement('li');
            li.dataset.id = promocao.id_promocao;
            li.dataset.type = 'promocao';
            li.innerHTML = `
                <span class="item-name">${promocao.nome_promocao} (${promocao.tipo_desconto || ''} ${promocao.valor_desconto || ''})</span>
                <div class="item-actions">
                    <button class="edit-button">Editar</button>
                    <button class="delete-button">Remover</button>
                </div>`;
            promocaoList.appendChild(li);
        });
    } catch (error) {
        console.error("Erro ao carregar promoções:", error);
        promocaoList.innerHTML = '<p>Erro ao carregar promoções.</p>';
    }
}

async function editPromocao(promocaoId) {
    if (!editingTenantId) return;
    try {
        const promocao = await (await authenticatedFetch(`/promocoes/${editingTenantId}/${promocaoId}`)).json();
        document.getElementById('promocao_id').value = promocao.id_promocao;
        document.getElementById('nome_promocao').value = promocao.nome_promocao;
        document.getElementById('tipo_promocao').value = promocao.tipo_promocao || '';
        document.getElementById('condicao_ativacao').value = promocao.condicao_ativacao || '';
        document.getElementById('tipo_desconto').value = promocao.tipo_desconto || '';
        document.getElementById('valor_desconto').value = promocao.valor_desconto || '';
        document.getElementById('dia_semana_ativo').value = promocao.dia_semana_ativo || '';
        editingPromocaoId = promocaoId;
    } catch (error) {
        console.error("Erro ao carregar promoção para edição:", error);
        alert("Não foi possível carregar a promoção para edição.");
    }
}

async function handlePromocaoFormSubmit(e) {
    e.preventDefault();
    if (!editingTenantId) return;
    const form = e.target;
    const { condicao_json, acao_json } = buildPromocaoJson();

    const formData = {
        nome_promocao: form.nome_promocao.value,
        descricao_para_ia: form.descricao_para_ia.value,
        condicao_json: condicao_json,
        acao_json: acao_json,
        is_ativa: true // Opcional: Adicionar um checkbox para isso no futuro
    };

    const url = editingPromocaoId ? `/promocoes/${editingTenantId}/${editingPromocaoId}` : `/promocoes/${editingTenantId}`;
    const method = editingPromocaoId ? 'PUT' : 'POST';

    try {
        const response = await authenticatedFetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert(`Promoção ${editingPromocaoId ? 'atualizada' : 'adicionada'} com sucesso!`);
        resetForm('promocao-form', 'editingPromocaoId');
        loadPromocoes(editingTenantId);
    } catch (error) {
        alert(`Erro ao salvar promoção: ${error.message}`);
    }
}

async function deletePromocao(promocaoId) {
    if (!editingTenantId || !confirm('Tem certeza que deseja remover esta promoção?')) return;
    try {
        const response = await authenticatedFetch(`/promocoes/${editingTenantId}/${promocaoId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert('Promoção removida com sucesso!');
        loadPromocoes(editingTenantId);
    } catch (error) {
        alert(`Erro ao remover promoção: ${error.message}`);
    }
}

async function loadProductOpcionalLinking(productId) {
    const linkingDiv = document.getElementById('product-opcionais-linking');
    if (!linkingDiv) return;

    try {
        const [linkedRes, allRes] = await Promise.all([
            authenticatedFetch(`/products/${productId}/opcionais`),
            authenticatedFetch(`/opcionais/${editingTenantId}`)
        ]);

        const linkedOpcionais = await linkedRes.json();
        const allOpcionais = await allRes.json();
        const linkedIds = new Set(linkedOpcionais.map(op => op.id_opcional));

        linkingDiv.innerHTML = '<h4>Vincular Opcionais</h4>';
        allOpcionais.forEach(opcional => {
            const isChecked = linkedIds.has(opcional.id_opcional);
            linkingDiv.innerHTML += `
                <div>
                    <input type="checkbox" id="opcional-link-${opcional.id_opcional}" 
                           data-product-id="${productId}" data-opcional-id="${opcional.id_opcional}" 
                           onchange="handleOpcionalCheckboxChange(event)" ${isChecked ? 'checked' : ''}>
                    <label for="opcional-link-${opcional.id_opcional}">${opcional.nome_opcional}</label>
                </div>`;
        });
    } catch (error) {
        linkingDiv.innerHTML = '<p>Erro ao carregar opcionais para vinculação.</p>';
        console.error(error);
    }
}

async function handleOpcionalCheckboxChange(event) {
    const checkbox = event.target;
    const productId = checkbox.dataset.productId;
    const opcionalId = checkbox.dataset.opcionalId;
    const method = checkbox.checked ? 'POST' : 'DELETE';

    try {
        const response = await authenticatedFetch(`/products/${productId}/opcionais/${opcionalId}`, { method });
        if (!response.ok) {
            throw new Error((await response.json()).detail);
        }
        console.log(`Opcional ${opcionalId} ${checkbox.checked ? 'vinculado' : 'desvinculado'} do produto ${productId}`);
    } catch (error) {
        alert(`Erro ao atualizar vínculo do opcional: ${error.message}`);
        checkbox.checked = !checkbox.checked; // Reverte a mudança visual em caso de erro
    }
}

// --- Menu Image Management ---

async function loadMenuImages(tenantId) {
    const previewDiv = document.getElementById('uploaded-menu-images-preview');
    if (!previewDiv) return;
    previewDiv.innerHTML = '<p>Carregando imagens...</p>';
    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}/menu-images/`);
        const images = await response.json();
        previewDiv.innerHTML = images.length === 0 ? '<p>Nenhuma imagem cadastrada.</p>' : '';
        images.forEach(image => {
            const imgContainer = document.createElement('div');
            imgContainer.className = 'menu-image-item';
            imgContainer.innerHTML = `
                <img src="${image.image_url}" alt="Cardápio" loading="lazy">
                <button onclick="deleteMenuImage(${image.id}, '${tenantId}')">×</button>`;
            previewDiv.appendChild(imgContainer);
        });
    } catch (error) {
        previewDiv.innerHTML = '<p>Erro ao carregar imagens.</p>';
    }
}

async function handleUploadMenuImages() {
    if (!editingTenantId) return;
    const fileInput = document.getElementById('menu_images_upload');
    if (!fileInput?.files.length) {
        alert('Selecione pelo menos uma imagem.');
        return;
    }
    const formData = new FormData();
    for (const file of fileInput.files) {
        formData.append('files', file);
    }

    try {
        const response = await authenticatedFetch(`/tenants/${editingTenantId}/menu-images/`, { method: 'POST', body: formData });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert('Imagens enviadas com sucesso!');
        fileInput.value = '';
        loadMenuImages(editingTenantId);
    } catch (error) {
        alert(`Erro ao enviar imagens: ${error.message}`);
    }
}

async function deleteMenuImage(imageId, tenantId) {
    if (!confirm('Tem certeza que deseja remover esta imagem?')) return;
    try {
        const response = await authenticatedFetch(`/tenants/${tenantId}/menu-images/${imageId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error((await response.json()).detail);
        alert('Imagem removida com sucesso!');
        loadMenuImages(tenantId);
    } catch (error) {
        alert(`Erro ao remover imagem: ${error.message}`);
    }
}

function setupPromocaoForm() {
    const condicaoTipo = document.getElementById('condicao_tipo');
    const acaoTipo = document.getElementById('acao_tipo');
    const condicaoCampos = document.getElementById('condicao_campos');
    const acaoCampos = document.getElementById('acao_campos');

    condicaoTipo.addEventListener('change', () => {
        condicaoCampos.innerHTML = '';
        switch (condicaoTipo.value) {
            case 'DIA_SEMANA':
                condicaoCampos.innerHTML = `
                    <label>Dias Válidos:</label>
                    <div>
                        <input type="checkbox" id="dia_seg" value="MON"><label for="dia_seg">Seg</label>
                        <input type="checkbox" id="dia_ter" value="TUE"><label for="dia_ter">Ter</label>
                        <input type="checkbox" id="dia_qua" value="WED"><label for="dia_qua">Qua</label>
                        <input type="checkbox" id="dia_qui" value="THU"><label for="dia_qui">Qui</label>
                        <input type="checkbox" id="dia_sex" value="FRI"><label for="dia_sex">Sex</label>
                        <input type="checkbox" id="dia_sab" value="SAT"><label for="dia_sab">Sáb</label>
                        <input type="checkbox" id="dia_dom" value="SUN"><label for="dia_dom">Dom</label>
                    </div>`;
                break;
            case 'VALOR_MINIMO':
                condicaoCampos.innerHTML = `<label for="condicao_valor">Valor Mínimo:</label><input type="number" id="condicao_valor" step="0.01">`;
                break;
        }
    });

    acaoTipo.addEventListener('change', () => {
        acaoCampos.innerHTML = '';
        switch (acaoTipo.value) {
            case 'DESCONTO_PERCENTUAL':
                acaoCampos.innerHTML = `<label for="acao_valor">Valor (%):</label><input type="number" id="acao_valor">`;
                break;
            case 'DESCONTO_FIXO':
                acaoCampos.innerHTML = `<label for="acao_valor">Valor (R$):</label><input type="number" id="acao_valor" step="0.01">`;
                break;
            case 'BRINDE':
                acaoCampos.innerHTML = `<label for="acao_valor">Nome do Brinde:</label><input type="text" id="acao_valor">`;
                break;
        }
    });
}

function buildPromocaoJson() {
    const condicao_json = { tipo: document.getElementById('condicao_tipo').value };
    switch (condicao_json.tipo) {
        case 'DIA_SEMANA':
            condicao_json.dias = Array.from(document.querySelectorAll('#condicao_campos input:checked')).map(cb => cb.value);
            break;
        case 'VALOR_MINIMO':
            condicao_json.valor = parseFloat(document.getElementById('condicao_valor').value);
            break;
    }

    const acao_json = { tipo: document.getElementById('acao_tipo').value };
    const acaoValorEl = document.getElementById('acao_valor');
    if (acaoValorEl) {
        if (acao_json.tipo === 'BRINDE') {
            acao_json.valor = acaoValorEl.value;
        } else {
            acao_json.valor = parseFloat(acaoValorEl.value);
        }
    }

    return { condicao_json, acao_json };
}