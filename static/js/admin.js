/** Администратор — CRUD справочника */
let adminCache = { themes: [], ages: [], partTypes: [], hoTypes: [], enums: [] };

        // Функции загрузки данных
        async function loadTree() { showLoading(); try {
            const trees = await apiRequest('/categories/tree?include_products=true');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-tree"></i> Дерево классификатора<div class="float-end"><button class="btn btn-sm btn-primary" onclick="loadTree()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div id="treeContainer">`;
            for (const root of trees) html += renderTree(root);
            html += `</div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        function renderTree(node) {
            const hasChildren = (node.children?.length > 0) || (node.products?.length > 0);
            let html = `<div class="tree-node"><span class="tree-toggle" onclick="toggleTreeNode(this)">${hasChildren ? '▼' : '•'}</span><span class="tree-icon">${getNodeIconEmoji(node.node_type)}</span><span class="tree-name">${escapeHtml(node.name)}</span><span class="tree-type">(${node.node_type}, ID: ${node.id})</span><div class="float-end"><button class="btn btn-sm btn-outline-primary" onclick="showEditCategoryModal(${node.id}, '${escapeHtml(node.name)}', ${node.sort_order})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-outline-secondary" onclick="showMoveNodeModal(${node.id})"><i class="fas fa-arrows-alt"></i></button><button class="btn btn-sm btn-outline-danger" onclick="deleteNode(${node.id})"><i class="fas fa-trash"></i></button></div></div><div class="tree-children">`;
            if (node.children) for (const child of node.children) html += renderTree(child);
            if (node.products?.length > 0) { html += `<div class="tree-products">`;
                for (const product of node.products) html += `<div class="product-item">${getProductIconEmoji(product.type)} ${escapeHtml(product.name)} <span class="text-muted">[${product.type}]</span></div>`;
                html += `</div>`; }
            html += `</div>`;
            return html;
        }

        function toggleTreeNode(el) { const children = el.parentElement.nextElementSibling; if (children?.classList.contains('tree-children')) { if (children.style.display === 'none') { children.style.display = 'block'; el.textContent = '▼'; } else { children.style.display = 'none'; el.textContent = '▶'; } } }

        async function loadCategories() { showLoading(); try {
            const cats = await apiRequest('/categories');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-folder"></i> Категории<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateCategoryModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadCategories()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead></tr><th>ID</th><th>Название</th><th>Тип</th><th>Родитель</th><th>Сортировка</th><th>Действия</th></tr></thead><tbody>`;
            for (const cat of cats) html += `<tr><td>${cat.id}</td><td>${escapeHtml(cat.name)}</td><td><span class="badge bg-secondary">${cat.node_type}</span></td><td>${cat.parent_id || '-'}</td><td>${cat.sort_order}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditCategoryModal(${cat.id}, '${escapeHtml(cat.name)}', ${cat.sort_order})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteNode(${cat.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadSets() { showLoading(); try {
            const sets = await apiRequest('/sets');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-cubes"></i> Наборы LEGO<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateSetModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadSets()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>ID</th><th>Название</th><th>Каталог</th><th>Год</th><th>Цена</th><th>Деталей</th><th>Действия</th></tr></thead><tbody>`;
            for (const set of sets) html += `<tr><td>${set.id}</td><td>${escapeHtml(set.name)}</td><td>${escapeHtml(set.catalog_number)}</td><td>${set.year}</td><td>$${set.price}</td><td>${set.parts_count}</td><td class="action-buttons"><button class="btn btn-sm btn-info" onclick="showSetContents(${set.id})"><i class="fas fa-eye"></i></button><button class="btn btn-sm btn-warning" onclick="showEditSetModal(${set.id})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteSet(${set.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadParts() { showLoading(); try {
            const parts = await apiRequest('/parts');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-microchip"></i> Детали LEGO <small class="text-muted">(характеристики задаются параметрами изделий)</small><div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreatePartModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadParts()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>ID</th><th>Название</th><th>Тип детали</th><th>Действия</th></tr></thead><tbody>`;
            for (const part of parts) html += `<tr><td>${part.id}</td><td>${escapeHtml(part.name)}</td><td>${escapeHtml(part.type_name || '—')}</td><td class="action-buttons"><button class="btn btn-sm btn-danger" onclick="deletePart(${part.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadMinifigures() { showLoading(); try {
        // Фигурки теперь — изделия класса «Мини-фигурка»
        const allProducts = await apiRequest('/products');
        const mfs = allProducts.filter(p => p.класс_название === 'Мини-фигурка');
        let html = `<div class="card"><div class="card-header"><i class="fas fa-user-astronaut"></i> Мини-фигурки LEGO
            <small class="text-muted ms-2">(хранятся как изделия)</small>
            <div class="float-end">
                <button class="btn btn-sm btn-primary" onclick="loadMinifigures()"><i class="fas fa-sync-alt"></i> Обновить</button>
            </div></div>
            <div class="card-body"><div class="table-responsive">
            <table class="table table-bordered"><thead><tr>
                <th>ID</th><th>Название</th><th>Артикул</th><th>Действия</th>
            </tr></thead><tbody>`;
        for (const mf of mfs) {
            html += `<tr>
                <td>${mf.id}</td>
                <td>${escapeHtml(mf.наименование)}</td>
                <td><code>${mf.артикул || '-'}</code></td>
                <td class="action-buttons">
                    <button class="btn btn-sm btn-info" onclick="showProductParams(${mf.id})"><i class="fas fa-chart-line"></i> Параметры</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteProduct(${mf.id})"><i class="fas fa-trash"></i></button>
                </td></tr>`;
        }
        html += `</tbody></table></div></div></div>`;
        document.getElementById('content').innerHTML = html;
    } catch(e) { showError(e.message); } }

        async function loadThemes() { showLoading(); try {
            const themes = await apiRequest('/themes');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-tags"></i> Тематики<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateThemeModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadThemes()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="row">`;
            for (const theme of themes) html += `<div class="col-md-6 mb-3"><div class="card h-100"><div class="card-body"><h5>${escapeHtml(theme.name)}</h5><p>${escapeHtml(theme.description || 'Нет описания')}</p><small class="text-muted">ID: ${theme.id}</small><div class="mt-2"><button class="btn btn-sm btn-warning" onclick="showEditThemeModal(${theme.id}, '${escapeHtml(theme.name)}', '${escapeHtml(theme.description || '')}')"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteTheme(${theme.id})"><i class="fas fa-trash"></i></button></div></div></div></div>`;
            html += `</div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadAgeCategories() { showLoading(); try {
            const cats = await apiRequest('/age-categories');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-calendar-alt"></i> Возрастные категории<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateAgeCategoryModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadAgeCategories()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>ID</th><th>Название</th><th>Мин. возраст</th><th>Макс. возраст</th><th>Действия</th></tr></thead><tbody>`;
            for (const cat of cats) html += `<tr><td>${cat.id}</td><td>${escapeHtml(cat.name)}</td><td>${cat.min_age}</td><td>${cat.max_age}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditAgeCategoryModal(${cat.id}, '${escapeHtml(cat.name)}', ${cat.min_age}, ${cat.max_age})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteAgeCategory(${cat.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadPartTypes() { showLoading(); try {
            const types = await apiRequest('/part-types');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-cog"></i> Типы деталей<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreatePartTypeModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadPartTypes()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>ID</th><th>Название</th><th>Уровень</th><th>Действия</th></tr></thead><tbody>`;
            for (const type of types) html += `<tr><td>${type.id}</td><td>${escapeHtml(type.name)}</td><td>${type.hierarchy_level}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditPartTypeModal(${type.id}, '${escapeHtml(type.name)}', ${type.hierarchy_level})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deletePartType(${type.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadParameters() { showLoading(); try {
            const params = await apiRequest('/parameters');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-sliders-h"></i> Параметры<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateParameterModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadParameters()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>ID</th><th>Обозначение</th><th>Полное имя</th><th>Тип</th><th>Ед. изм.</th><th>Действия</th></tr></thead><tbody>`;
            for (const p of params) html += `<tr><td>${p.id}</td><td><code>${escapeHtml(p.обозначение)}</code></td><td>${escapeHtml(p.полное_имя)}</td><td><span class="badge bg-info">${p.тип_параметра}</span></td><td>${p.единица_измерения || '-'}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditParameterModal(${p.id})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteParameter(${p.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadProducts() { showLoading(); try {
            const products = await apiRequest('/products');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-box"></i> Изделия (склад, параметры 1.3)<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateProductModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadProducts()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>ID</th><th>Наименование</th><th>Артикул</th><th>Класс</th><th>Действия</th></tr></thead><tbody>`;
            for (const p of products) html += `<tr><td>${p.id}</td><td>${escapeHtml(p.наименование)}</td><td><code>${p.артикул || '-'}</code></td><td>${escapeHtml(p.класс_название || p.класс_id)}</td><td class="action-buttons"><button class="btn btn-sm btn-info" onclick="showProductParams(${p.id})"><i class="fas fa-chart-line"></i></button><button class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadEnumerations() { showLoading(); try {
            const enums = await apiRequest('/enumerations');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-list"></i> Перечисления<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateEnumerationModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadEnumerations()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body">`;
            for (const e of enums) html += `<div class="card mb-3"><div class="card-body"><h5>${escapeHtml(e.name)}</h5><p>${e.description || ''}</p><small class="text-muted">Значений: ${e.values_count}, ID: ${e.id}</small><div class="mt-2"><button class="btn btn-sm btn-success" onclick="showAddEnumValueModal(${e.id})"><i class="fas fa-plus"></i> Добавить значение</button><button class="btn btn-sm btn-info" onclick="showEnumValues(${e.id})"><i class="fas fa-eye"></i> Значения</button><button class="btn btn-sm btn-warning" onclick="showEditEnumerationModal(${e.id}, '${escapeHtml(e.name)}', '${escapeHtml(e.description || '')}')"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteEnumeration(${e.id})"><i class="fas fa-trash"></i></button></div></div></div>`;
            html += `</div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadEnumValuesAll() { showLoading(); try {
            const enums = await apiRequest('/enumerations');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-tasks"></i> Значения перечислений<div class="float-end"><button class="btn btn-sm btn-primary" onclick="loadEnumValuesAll()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body">`;
            for (const e of enums) {
                const values = await apiRequest(`/enumerations/${e.id}/values`);
                html += `<div class="card mb-3"><div class="card-body"><h5>${escapeHtml(e.name)} (ID: ${e.id})</h5><div class="table-responsive"><table class="table table-sm"><thead><tr><th>ID</th><th>Значение</th><th>Порядок</th><th>Действия</th></tr></thead><tbody>`;
                for (const v of values) html += `<tr><td>${v.id}</td><td>${escapeHtml(v.value)}</td><td>${v.sort_order}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditEnumValueModal(${v.id}, ${e.id}, '${escapeHtml(v.value)}', ${v.sort_order})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteEnumValue(${v.id})"><i class="fas fa-trash"></i></button></td></tr>`;
                html += `</tbody></table></div></div></div>`;
            }
            html += `</div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadHOTypes() { showLoading(); try {
            const types = await apiRequest('/ho-types');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-exchange-alt"></i> Типы ХО<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateHOTypeModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadHOTypes()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table"><thead><tr><th>ID</th><th>Название</th><th>Родитель</th><th>Действия</th></tr></thead><tbody>`;
            for (const t of types) html += `<tr><td>${t.id}</td><td>${escapeHtml(t.название)}</td><td>${t.родительский_id || '-'}</td><td class="action-buttons"><button class="btn btn-sm btn-success" onclick="showAddHORoleModal(${t.id})"><i class="fas fa-plus"></i> Роль</button><button class="btn btn-sm btn-info" onclick="showHOTypeRoles(${t.id})"><i class="fas fa-list"></i></button><button class="btn btn-sm btn-warning" onclick="showEditHOTypeModal(${t.id}, '${escapeHtml(t.название)}', ${t.родительский_id || ''})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteHOType(${t.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadHORoles() { showLoading(); try {
            const types = await apiRequest('/ho-types');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-user-tag"></i> Роли ХО<div class="float-end"><button class="btn btn-sm btn-primary" onclick="loadHORoles()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body">`;
            for (const t of types) {
                const roles = await apiRequest(`/ho-types/${t.id}/roles`);
                if (roles.length > 0) {
                    html += `<div class="card mb-3"><div class="card-body"><h5>${escapeHtml(t.название)} (ID: ${t.id})</h5><div class="table-responsive"><table class="table table-sm"><thead><tr><th>ID</th><th>Название</th><th>Допустимый класс</th><th>Действия</th></tr></thead><tbody>`;
                    for (const r of roles) html += `<tr><td>${r.id}</td><td>${escapeHtml(r.название)}</td><td>${r.допустимый_класс_СХД || '-'}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditHORoleModal(${r.id}, '${escapeHtml(r.название)}', ${r.допустимый_класс_СХД || ''})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteHORole(${r.id})"><i class="fas fa-trash"></i></button></td></tr>`;
                    html += `</tbody></table></div></div></div>`;
                }
            }
            html += `</div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadSubjects() { showLoading(); try {
            const subjects = await apiRequest('/subjects');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-building"></i> Субъекты<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateSubjectModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadSubjects()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table"><thead><tr><th>ID</th><th>Наименование</th><th>ИНН</th><th>Контакт</th><th>Телефон</th><th>Действия</th></tr></thead><tbody>`;
            for (const s of subjects) html += `<tr><td>${s.id}</td><td>${escapeHtml(s.наименование)}</td><td>${s.инн || '-'}</td><td>${s.контактное_лицо || '-'}</td><td>${s.телефон || '-'}</td><td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditSubjectModal(${s.id}, '${escapeHtml(s.наименование)}', '${s.инн || ''}', '${s.контактное_лицо || ''}', '${s.телефон || ''}')"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteSubject(${s.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        async function loadHOOps() { showLoading(); try {
            const ops = await apiRequest('/ho-operations');
            let html = `<div class="card"><div class="card-header"><i class="fas fa-file-invoice"></i> Операции<div class="float-end"><button class="btn btn-sm btn-success me-2" onclick="showCreateHOOperationModal()"><i class="fas fa-plus"></i> Создать</button><button class="btn btn-sm btn-primary" onclick="loadHOOps()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body"><div class="table-responsive"><table class="table"><thead><tr><th>ID</th><th>Номер</th><th>Дата</th><th>Сумма</th><th>Действия</th></tr></thead><tbody>`;
            for (const op of ops) html += `<tr><td>${op.id}</td><td><code>${escapeHtml(op.номер)}</code></td><td>${new Date(op.дата).toLocaleString()}</td><td>$${op.сумма}</td><td class="action-buttons"><button class="btn btn-sm btn-info" onclick="showHOOpsDetails(${op.id})"><i class="fas fa-eye"></i></button><button class="btn btn-sm btn-danger" onclick="deleteHOOperation(${op.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            html += `</tbody></table></div></div></div>`;
            document.getElementById('content').innerHTML = html;
        } catch(e) { showError(e.message); } }

        // CRUD операции создания
        async function createCategory() { const name = document.getElementById('catName').value.trim(); if(!name){showToast('Введите название','error');return;}
            const data={name:name}; if(document.getElementById('catParentId').value) data.parent_id=parseInt(document.getElementById('catParentId').value);
            if(document.getElementById('catSortOrder').value) data.sort_order=parseInt(document.getElementById('catSortOrder').value);
            try{await apiRequest('/categories','POST',data); showToast('Категория создана'); bootstrap.Modal.getInstance(document.getElementById('createCategoryModal')).hide(); loadCategories();}catch(e){showToast(e.message,'error');} }

        async function createSet() { const data={name:document.getElementById('setName').value.trim(),catalog_number:document.getElementById('setCatalog').value.trim(),year:parseInt(document.getElementById('setYear').value),price:parseFloat(document.getElementById('setPrice').value),parts_count:parseInt(document.getElementById('setParts').value),age_category_id:parseInt(document.getElementById('setAgeId').value),theme_id:parseInt(document.getElementById('setThemeId').value)};
            if(!data.name||!data.catalog_number){showToast('Заполните обязательные поля','error');return;}
            try{await apiRequest('/sets','POST',data); showToast('Набор создан'); bootstrap.Modal.getInstance(document.getElementById('createSetModal')).hide(); loadSets();}catch(e){showToast(e.message,'error');} }

        async function createPart() { const data={name:document.getElementById('partName').value.trim(),part_type_id:parseInt(document.getElementById('partTypeId').value)};
            if(!data.name||!data.part_type_id){showToast('Заполните все поля','error');return;}
            try{await apiRequest('/parts','POST',data); showToast('Деталь создана'); bootstrap.Modal.getInstance(document.getElementById('createPartModal')).hide(); loadParts();}catch(e){showToast(e.message,'error');} }

        async function createMinifigure() { const data={name:document.getElementById('mfName').value.trim(),character:document.getElementById('mfCharacter').value.trim(),series:document.getElementById('mfSeries').value.trim(),unique_code:document.getElementById('mfCode').value.trim()};
            if(!data.name||!data.character||!data.series||!data.unique_code){showToast('Заполните все поля','error');return;}
            try{await apiRequest('/minifigures','POST',data); showToast('Мини-фигурка создана'); bootstrap.Modal.getInstance(document.getElementById('createMinifigureModal')).hide(); loadMinifigures();}catch(e){showToast(e.message,'error');} }

        async function createTheme() { const data={name:document.getElementById('themeName').value.trim(),description:document.getElementById('themeDesc').value.trim()};
            if(!data.name){showToast('Введите название','error');return;}
            try{await apiRequest('/themes','POST',data); showToast('Тематика создана'); bootstrap.Modal.getInstance(document.getElementById('createThemeModal')).hide(); loadThemes();}catch(e){showToast(e.message,'error');} }

        async function createAgeCategory() { const data={name:document.getElementById('ageName').value.trim(),min_age:parseInt(document.getElementById('ageMin').value),max_age:parseInt(document.getElementById('ageMax').value)};
            if(!data.name||!data.min_age||!data.max_age){showToast('Заполните все поля','error');return;}
            try{await apiRequest('/age-categories','POST',data); showToast('Возрастная категория создана'); bootstrap.Modal.getInstance(document.getElementById('createAgeCategoryModal')).hide(); loadAgeCategories();}catch(e){showToast(e.message,'error');} }

        async function createPartType() { const data={name:document.getElementById('ptName').value.trim(),hierarchy_level:parseInt(document.getElementById('ptLevel').value)};
            if(!data.name||!data.hierarchy_level){showToast('Заполните все поля','error');return;}
            try{await apiRequest('/part-types','POST',data); showToast('Тип детали создан'); bootstrap.Modal.getInstance(document.getElementById('createPartTypeModal')).hide(); loadPartTypes();}catch(e){showToast(e.message,'error');} }

        async function createParameter() { const data={обозначение:document.getElementById('paramCode').value.trim(),полное_имя:document.getElementById('paramName').value.trim(),тип_параметра:document.getElementById('paramType').value,единица_измерения:document.getElementById('paramUnit').value.trim()||null,перечисление_id:document.getElementById('paramEnumId').value?parseInt(document.getElementById('paramEnumId').value):null};
            if(!data.обозначение||!data.полное_имя){showToast('Заполните обязательные поля','error');return;}
            try{await apiRequest('/parameters','POST',data); showToast('Параметр создан'); bootstrap.Modal.getInstance(document.getElementById('createParameterModal')).hide(); loadParameters();}catch(e){showToast(e.message,'error');} }

        async function createEnumeration() { const data={name:document.getElementById('enumName').value.trim(),description:document.getElementById('enumDesc').value.trim()||null};
            if(!data.name){showToast('Введите название','error');return;}
            try{await apiRequest('/enumerations','POST',data); showToast('Перечисление создано'); bootstrap.Modal.getInstance(document.getElementById('createEnumerationModal')).hide(); loadEnumerations();}catch(e){showToast(e.message,'error');} }

        async function createProduct() { const data={класс_id:parseInt(document.getElementById('productClassId').value),наименование:document.getElementById('productName').value.trim(),артикул:document.getElementById('productArticle').value.trim()||null};
            if(!data.класс_id||!data.наименование){showToast('Заполните обязательные поля','error');return;}
            try{await apiRequest('/products','POST',data); showToast('Изделие создано'); bootstrap.Modal.getInstance(document.getElementById('createProductModal')).hide(); loadProducts();}catch(e){showToast(e.message,'error');} }

        async function createHOType() { const data={название:document.getElementById('hoTypeName').value.trim(),родительский_id:document.getElementById('hoTypeParent').value?parseInt(document.getElementById('hoTypeParent').value):null};
            if(!data.название){showToast('Введите название','error');return;}
            try{await apiRequest('/ho-types','POST',data); showToast('Тип ХО создан'); bootstrap.Modal.getInstance(document.getElementById('createHOTypeModal')).hide(); loadHOTypes();}catch(e){showToast(e.message,'error');} }

        async function createSubject() { const data={наименование:document.getElementById('subjectName').value.trim(),инн:document.getElementById('subjectInn').value.trim()||null,контактное_лицо:document.getElementById('subjectContact').value.trim()||null,телефон:document.getElementById('subjectPhone').value.trim()||null};
            if(!data.наименование){showToast('Введите наименование','error');return;}
            try{await apiRequest('/subjects','POST',data); showToast('Субъект создан'); bootstrap.Modal.getInstance(document.getElementById('createSubjectModal')).hide(); loadSubjects();}catch(e){showToast(e.message,'error');} }

        async function createHOOperation() { const date = document.getElementById('hoOpDate').value; const data={тип_хо_id:parseInt(document.getElementById('hoOpTypeId').value),номер_документа:document.getElementById('hoOpNumber').value.trim(),дата:date?new Date(date).toISOString():new Date().toISOString()};
            if(!data.тип_хо_id||!data.номер_документа){showToast('Заполните обязательные поля','error');return;}
            try{await apiRequest('/ho-operations','POST',data); showToast('Операция создана'); bootstrap.Modal.getInstance(document.getElementById('createHOOperationModal')).hide(); loadHOOps();}catch(e){showToast(e.message,'error');} }

        // Функции обновления
        async function updateCategory() { const id=document.getElementById('editCatId').value; const name=document.getElementById('editCatName').value.trim(); const sort_order=document.getElementById('editCatSortOrder').value;
            if(!name){showToast('Введите название','error');return;}
            try{await apiRequest(`/categories/${id}`,'PUT',{name:name,sort_order:parseInt(sort_order)}); showToast('Категория обновлена'); bootstrap.Modal.getInstance(document.getElementById('editCategoryModal')).hide(); loadCategories();}catch(e){showToast(e.message,'error');} }

        async function updateSet() { const id=document.getElementById('editSetId').value; const data={name:document.getElementById('editSetName').value.trim(),catalog_number:document.getElementById('editSetCatalog').value.trim(),year:parseInt(document.getElementById('editSetYear').value),price:parseFloat(document.getElementById('editSetPrice').value),parts_count:parseInt(document.getElementById('editSetParts').value),age_category_id:parseInt(document.getElementById('editSetAgeId').value),theme_id:parseInt(document.getElementById('editSetThemeId').value)};
            try{await apiRequest(`/sets/${id}`,'PUT',data); showToast('Набор обновлён'); bootstrap.Modal.getInstance(document.getElementById('editSetModal')).hide(); loadSets();}catch(e){showToast(e.message,'error');} }

        async function updateTheme() { const id=document.getElementById('editThemeId').value; const data={name:document.getElementById('editThemeName').value.trim(),description:document.getElementById('editThemeDesc').value.trim()};
            try{await apiRequest(`/themes/${id}`,'PUT',data); showToast('Тематика обновлена'); bootstrap.Modal.getInstance(document.getElementById('editThemeModal')).hide(); loadThemes();}catch(e){showToast(e.message,'error');} }

        async function updateAgeCategory() { const id=document.getElementById('editAgeId').value; const data={name:document.getElementById('editAgeName').value.trim(),min_age:parseInt(document.getElementById('editAgeMin').value),max_age:parseInt(document.getElementById('editAgeMax').value)};
            try{await apiRequest(`/age-categories/${id}`,'PUT',data); showToast('Возрастная категория обновлена'); bootstrap.Modal.getInstance(document.getElementById('editAgeCategoryModal')).hide(); loadAgeCategories();}catch(e){showToast(e.message,'error');} }

        async function updatePartType() { const id=document.getElementById('editPartTypeId').value; const data={name:document.getElementById('editPartTypeName').value.trim(),hierarchy_level:parseInt(document.getElementById('editPartTypeLevel').value)};
            try{await apiRequest(`/part-types/${id}`,'PUT',data); showToast('Тип детали обновлён'); bootstrap.Modal.getInstance(document.getElementById('editPartTypeModal')).hide(); loadPartTypes();}catch(e){showToast(e.message,'error');} }

        async function updateParameter() { const id=document.getElementById('editParamId').value; const data={обозначение:document.getElementById('editParamCode').value.trim(),полное_имя:document.getElementById('editParamName').value.trim(),тип_параметра:document.getElementById('editParamType').value,единица_измерения:document.getElementById('editParamUnit').value.trim()||null,перечисление_id:document.getElementById('editParamEnumId').value?parseInt(document.getElementById('editParamEnumId').value):null};
            try{await apiRequest(`/parameters/${id}`,'PUT',data); showToast('Параметр обновлён'); bootstrap.Modal.getInstance(document.getElementById('editParameterModal')).hide(); loadParameters();}catch(e){showToast(e.message,'error');} }

        async function updateEnumeration() { const id=document.getElementById('editEnumId').value; const data={name:document.getElementById('editEnumName').value.trim(),description:document.getElementById('editEnumDesc').value.trim()||null};
            try{await apiRequest(`/enumerations/${id}`,'PUT',data); showToast('Перечисление обновлено'); bootstrap.Modal.getInstance(document.getElementById('editEnumerationModal')).hide(); loadEnumerations();}catch(e){showToast(e.message,'error');} }

        async function updateEnumValue() { const id=document.getElementById('editEnumValueId').value; const data={value:document.getElementById('editEnumValue').value.trim(),sort_order:parseInt(document.getElementById('editEnumValueOrder').value)};
            try{await apiRequest(`/enum-values/${id}`,'PUT',data); showToast('Значение обновлено'); bootstrap.Modal.getInstance(document.getElementById('editEnumValueModal')).hide(); loadEnumValuesAll();}catch(e){showToast(e.message,'error');} }

        async function updateSubject() { const id=document.getElementById('editSubjectId').value; const data={наименование:document.getElementById('editSubjectName').value.trim(),инн:document.getElementById('editSubjectInn').value.trim()||null,контактное_лицо:document.getElementById('editSubjectContact').value.trim()||null,телефон:document.getElementById('editSubjectPhone').value.trim()||null};
            try{await apiRequest(`/subjects/${id}`,'PUT',data); showToast('Субъект обновлён'); bootstrap.Modal.getInstance(document.getElementById('editSubjectModal')).hide(); loadSubjects();}catch(e){showToast(e.message,'error');} }

        async function updateHOType() { const id=document.getElementById('editHOTypeId').value; const data={название:document.getElementById('editHOTypeName').value.trim(),родительский_id:document.getElementById('editHOTypeParent').value?parseInt(document.getElementById('editHOTypeParent').value):null};
            try{await apiRequest(`/ho-types/${id}`,'PUT',data); showToast('Тип ХО обновлён'); bootstrap.Modal.getInstance(document.getElementById('editHOTypeModal')).hide(); loadHOTypes();}catch(e){showToast(e.message,'error');} }

        async function updateHORole() { const id=document.getElementById('editRoleId').value; const data={название:document.getElementById('editRoleName').value.trim(),допустимый_класс_СХД:document.getElementById('editRoleClassId').value?parseInt(document.getElementById('editRoleClassId').value):null};
            try{await apiRequest(`/ho-roles/${id}`,'PUT',data); showToast('Роль обновлена'); bootstrap.Modal.getInstance(document.getElementById('editHORoleModal')).hide(); loadHORoles();}catch(e){showToast(e.message,'error');} }

        // Функции удаления
        async function deleteNode(id) { if(confirm('Удалить узел?')) try{await apiRequest(`/categories/${id}`,'DELETE'); showToast('Узел удалён'); loadTree();}catch(e){showToast(e.message,'error');} }
        async function deleteSet(id) { if(confirm('Удалить набор?')) try{await apiRequest(`/sets/${id}`,'DELETE'); showToast('Набор удалён'); loadSets();}catch(e){showToast(e.message,'error');} }
        async function deletePart(id) { if(confirm('Удалить деталь?')) try{await apiRequest(`/parts/${id}`,'DELETE'); showToast('Деталь удалена'); loadParts();}catch(e){showToast(e.message,'error');} }
        async function deleteMinifigure(id) { if(confirm('Удалить мини-фигурку?')) try{await apiRequest(`/minifigures/${id}`,'DELETE'); showToast('Мини-фигурка удалена'); loadMinifigures();}catch(e){showToast(e.message,'error');} }
        async function deleteTheme(id) { if(confirm('Удалить тематику?')) try{await apiRequest(`/themes/${id}`,'DELETE'); showToast('Тематика удалена'); loadThemes();}catch(e){showToast(e.message,'error');} }
        async function deleteAgeCategory(id) { if(confirm('Удалить возрастную категорию?')) try{await apiRequest(`/age-categories/${id}`,'DELETE'); showToast('Категория удалена'); loadAgeCategories();}catch(e){showToast(e.message,'error');} }
        async function deletePartType(id) { if(confirm('Удалить тип детали?')) try{await apiRequest(`/part-types/${id}`,'DELETE'); showToast('Тип детали удалён'); loadPartTypes();}catch(e){showToast(e.message,'error');} }
        async function deleteParameter(id) { if(confirm('Удалить параметр?')) try{await apiRequest(`/parameters/${id}`,'DELETE'); showToast('Параметр удалён'); loadParameters();}catch(e){showToast(e.message,'error');} }
        async function deleteProduct(id) { if(confirm('Удалить изделие?')) try{await apiRequest(`/products/${id}`,'DELETE'); showToast('Изделие удалено'); loadProducts();}catch(e){showToast(e.message,'error');} }
        async function deleteEnumeration(id) { if(confirm('Удалить перечисление?')) try{await apiRequest(`/enumerations/${id}`,'DELETE'); showToast('Перечисление удалено'); loadEnumerations();}catch(e){showToast(e.message,'error');} }
        async function deleteEnumValue(id) { if(confirm('Удалить значение?')) try{await apiRequest(`/enum-values/${id}`,'DELETE'); showToast('Значение удалено'); loadEnumValuesAll();}catch(e){showToast(e.message,'error');} }
        async function deleteHOType(id) { if(confirm('Удалить тип ХО?')) try{await apiRequest(`/ho-types/${id}`,'DELETE'); showToast('Тип ХО удалён'); loadHOTypes();}catch(e){showToast(e.message,'error');} }
        async function deleteHORole(id) { if(confirm('Удалить роль?')) try{await apiRequest(`/ho-roles/${id}`,'DELETE'); showToast('Роль удалена'); loadHORoles();}catch(e){showToast(e.message,'error');} }
        async function deleteSubject(id) { if(confirm('Удалить субъекта?')) try{await apiRequest(`/subjects/${id}`,'DELETE'); showToast('Субъект удалён'); loadSubjects();}catch(e){showToast(e.message,'error');} }
        async function deleteHOOperation(id) { if(confirm('Удалить операцию?')) try{await apiRequest(`/ho-operations/${id}`,'DELETE'); showToast('Операция удалена'); loadHOOps();}catch(e){showToast(e.message,'error');} }

        // Дополнительные функции
        async function addEnumValue() { const enumId = parseInt(document.getElementById('currentEnumId').value); const value = document.getElementById('newEnumValue').value.trim(); const order = document.getElementById('newEnumValueOrder').value;
            if(!value){showToast('Введите значение','error');return;}
            const data={value:value,sort_order:order?parseInt(order):null};
            try{await apiRequest(`/enumerations/${enumId}/values`,'POST',data); showToast('Значение добавлено'); bootstrap.Modal.getInstance(document.getElementById('addEnumValueModal')).hide(); loadEnumerations();}catch(e){showToast(e.message,'error');} }

        async function addHORole() { const typeId = parseInt(document.getElementById('currentHOTypeId').value); const name = document.getElementById('newRoleName').value.trim(); const classId = document.getElementById('newRoleClassId').value;
            if(!name){showToast('Введите название роли','error');return;}
            const data={название:name,допустимый_класс_СХД:classId?parseInt(classId):null};
            try{await apiRequest(`/ho-types/${typeId}/roles`,'POST',data); showToast('Роль добавлена'); bootstrap.Modal.getInstance(document.getElementById('addHORoleModal')).hide(); loadHOTypes();}catch(e){showToast(e.message,'error');} }

        async function loadTestData() { if(confirm('Загрузить тестовые данные? База будет очищена!')) try{await apiRequest('/test-data','POST'); showToast('Тестовые данные загружены'); loadTree();}catch(e){showToast(e.message,'error');} }
        async function clearDatabase() { if(confirm('Очистить БД? Это необратимо!')) try{await apiRequest('/clear','DELETE'); showToast('База очищена'); loadTree();}catch(e){showToast(e.message,'error');} }

        async function showSetContents(id) { try{const c=await apiRequest(`/sets/${id}/contents`); let html='<div class="modal-body"><ul>'; for(const i of c) html+=`<li>${escapeHtml(i.item_name)} - ${i.quantity} шт.</li>`; html+='</ul></div>';
            const modal=document.createElement('div'); modal.className='modal fade'; modal.innerHTML=`<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>Состав набора</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>${html}<div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div></div></div>`;
            document.body.appendChild(modal); new bootstrap.Modal(modal).show(); modal.addEventListener('hidden.bs.modal',()=>modal.remove()); }catch(e){showToast(e.message,'error');} }

        async function showProductParams(id) { try{const p=await apiRequest(`/products/${id}/values`); let html='<div class="modal-body"><table class="table"><thead><tr><th>Параметр</th><th>Значение</th></tr></thead><tbody>'; for(const param of p) html+=`<tr><td>${escapeHtml(param.обозначение)}</td><td>${param.значение||'-'}</td></tr>`; html+='</tbody></table></div>';
            const modal=document.createElement('div'); modal.className='modal fade'; modal.innerHTML=`<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>Параметры изделия</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>${html}<div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div></div></div>`;
            document.body.appendChild(modal); new bootstrap.Modal(modal).show(); modal.addEventListener('hidden.bs.modal',()=>modal.remove()); }catch(e){showToast(e.message,'error');} }

        async function showEnumValues(enumId) { try{const v=await apiRequest(`/enumerations/${enumId}/values`); let html='<div class="modal-body"><ul>'; for(const val of v) html+=`<li>${escapeHtml(val.value)} (порядок: ${val.sort_order})</li>`; html+='</ul></div>';
            const modal=document.createElement('div'); modal.className='modal fade'; modal.innerHTML=`<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>Значения</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>${html}<div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div></div></div>`;
            document.body.appendChild(modal); new bootstrap.Modal(modal).show(); modal.addEventListener('hidden.bs.modal',()=>modal.remove()); }catch(e){showToast(e.message,'error');} }

        async function showHOTypeRoles(typeId) { try{const r=await apiRequest(`/ho-types/${typeId}/roles`); let html='<div class="modal-body"><ul>'; for(const role of r) html+=`<li>${escapeHtml(role.название)} (ID: ${role.id})</li>`; html+='</ul></div>';
            const modal=document.createElement('div'); modal.className='modal fade'; modal.innerHTML=`<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>Роли типа ХО</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>${html}<div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div></div></div>`;
            document.body.appendChild(modal); new bootstrap.Modal(modal).show(); modal.addEventListener('hidden.bs.modal',()=>modal.remove()); }catch(e){showToast(e.message,'error');} }

        async function showHOOpsDetails(opId) { try{const d=await apiRequest(`/ho-operations/${opId}`); let html=`<div class="modal-body"><p><strong>Номер:</strong> ${escapeHtml(d.номер_документа)}</p><p><strong>Сумма:</strong> $${d.сумма}</p><h6>Роли:</h6><ul>`; for(const r of d.роли) html+=`<li>${escapeHtml(r.роль)}: ${escapeHtml(r.субъект||'Не назначен')}</li>`; html+=`</ul><h6>Позиции:</h6><ul>`; for(const i of d.позиции) html+=`<li>${escapeHtml(i.изделие)} - ${i.количество} шт. x $${i.цена} = $${i.сумма}</li>`; html+=`</ul></div>`;
            const modal=document.createElement('div'); modal.className='modal fade modal-lg'; modal.innerHTML=`<div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5>Детали операции</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>${html}<div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div></div></div>`;
            document.body.appendChild(modal); new bootstrap.Modal(modal).show(); modal.addEventListener('hidden.bs.modal',()=>modal.remove()); }catch(e){showToast(e.message,'error');} }

        async function moveNode(id,newParentId){ try{await apiRequest(`/categories/${id}/move`,'PUT',{new_parent_id:newParentId}); showToast('Узел перемещён'); loadTree();}catch(e){showToast(e.message,'error');} }
        function showMoveNodeModal(id){ const pid=prompt('Введите ID нового родительского узла (или 0 для корневого):'); if(pid!==null) moveNode(id,parseInt(pid)||null); }
        function showAddEnumValueModal(id){ document.getElementById('currentEnumId').value=id; document.getElementById('newEnumValue').value=''; document.getElementById('newEnumValueOrder').value=''; new bootstrap.Modal(document.getElementById('addEnumValueModal')).show(); }
        function showAddHORoleModal(id){ document.getElementById('currentHOTypeId').value=id; document.getElementById('newRoleName').value=''; document.getElementById('newRoleClassId').value=''; new bootstrap.Modal(document.getElementById('addHORoleModal')).show(); }

        // Функции показа модальных окон редактирования
        function showEditCategoryModal(id,name,sort){ document.getElementById('editCatId').value=id; document.getElementById('editCatName').value=name; document.getElementById('editCatSortOrder').value=sort; new bootstrap.Modal(document.getElementById('editCategoryModal')).show(); }
        async function showEditSetModal(id){ try{const s=await apiRequest(`/sets/${id}`); await fillSetSelects('editSet'); document.getElementById('editSetId').value=s.id; document.getElementById('editSetName').value=s.name; document.getElementById('editSetCatalog').value=s.catalog_number; document.getElementById('editSetYear').value=s.year; document.getElementById('editSetPrice').value=s.price; document.getElementById('editSetParts').value=s.parts_count; document.getElementById('editSetAgeId').value=s.age_category_id; document.getElementById('editSetThemeId').value=s.theme_id; new bootstrap.Modal(document.getElementById('editSetModal')).show();}catch(e){showToast(e.message,'error');} }
        function showEditThemeModal(id,name,desc){ document.getElementById('editThemeId').value=id; document.getElementById('editThemeName').value=name; document.getElementById('editThemeDesc').value=desc; new bootstrap.Modal(document.getElementById('editThemeModal')).show(); }
        function showEditAgeCategoryModal(id,name,min,max){ document.getElementById('editAgeId').value=id; document.getElementById('editAgeName').value=name; document.getElementById('editAgeMin').value=min; document.getElementById('editAgeMax').value=max; new bootstrap.Modal(document.getElementById('editAgeCategoryModal')).show(); }
        function showEditPartTypeModal(id,name,level){ document.getElementById('editPartTypeId').value=id; document.getElementById('editPartTypeName').value=name; document.getElementById('editPartTypeLevel').value=level; new bootstrap.Modal(document.getElementById('editPartTypeModal')).show(); }
        async function showEditParameterModal(id){ try{const p=await apiRequest(`/parameters/${id}`); document.getElementById('editParamId').value=p.id; document.getElementById('editParamCode').value=p.обозначение; document.getElementById('editParamName').value=p.полное_имя; document.getElementById('editParamType').value=p.тип_параметра; document.getElementById('editParamUnit').value=p.единица_измерения||''; document.getElementById('editParamEnumId').value=p.перечисление_id||''; new bootstrap.Modal(document.getElementById('editParameterModal')).show();}catch(e){showToast(e.message,'error');} }
        function showEditEnumerationModal(id,name,desc){ document.getElementById('editEnumId').value=id; document.getElementById('editEnumName').value=name; document.getElementById('editEnumDesc').value=desc; new bootstrap.Modal(document.getElementById('editEnumerationModal')).show(); }
        function showEditEnumValueModal(id,eid,val,order){ document.getElementById('editEnumValueId').value=id; document.getElementById('editEnumValueEnumId').value=eid; document.getElementById('editEnumValue').value=val; document.getElementById('editEnumValueOrder').value=order; new bootstrap.Modal(document.getElementById('editEnumValueModal')).show(); }
        function showEditSubjectModal(id,name,inn,contact,phone){ document.getElementById('editSubjectId').value=id; document.getElementById('editSubjectName').value=name; document.getElementById('editSubjectInn').value=inn; document.getElementById('editSubjectContact').value=contact; document.getElementById('editSubjectPhone').value=phone; new bootstrap.Modal(document.getElementById('editSubjectModal')).show(); }
        function showEditHOTypeModal(id,name,parent){ document.getElementById('editHOTypeId').value=id; document.getElementById('editHOTypeName').value=name; document.getElementById('editHOTypeParent').value=parent; new bootstrap.Modal(document.getElementById('editHOTypeModal')).show(); }
        function showEditHORoleModal(id,name,classId){ document.getElementById('editRoleId').value=id; document.getElementById('editRoleName').value=name; document.getElementById('editRoleClassId').value=classId; new bootstrap.Modal(document.getElementById('editHORoleModal')).show(); }

        // Функции показа модальных окон создания
        function showCreateCategoryModal(){ document.getElementById('catName').value=''; document.getElementById('catParentId').value=''; document.getElementById('catSortOrder').value='0'; new bootstrap.Modal(document.getElementById('createCategoryModal')).show(); }
        async function showCreateSetModal(){ await fillSetSelects('set'); document.getElementById('setName').value=''; document.getElementById('setCatalog').value=''; document.getElementById('setYear').value=''; document.getElementById('setPrice').value=''; document.getElementById('setParts').value=''; document.getElementById('setAgeId').value=''; document.getElementById('setThemeId').value=''; new bootstrap.Modal(document.getElementById('createSetModal')).show(); }
        async function showCreatePartModal(){ await fillPartTypeSelect('part'); document.getElementById('partName').value=''; document.getElementById('partTypeId').value=''; new bootstrap.Modal(document.getElementById('createPartModal')).show(); }
        function showCreateMinifigureModal(){ document.getElementById('mfName').value=''; document.getElementById('mfCharacter').value=''; document.getElementById('mfSeries').value=''; document.getElementById('mfCode').value=''; new bootstrap.Modal(document.getElementById('createMinifigureModal')).show(); }
        function showCreateThemeModal(){ document.getElementById('themeName').value=''; document.getElementById('themeDesc').value=''; new bootstrap.Modal(document.getElementById('createThemeModal')).show(); }
        function showCreateAgeCategoryModal(){ document.getElementById('ageName').value=''; document.getElementById('ageMin').value=''; document.getElementById('ageMax').value=''; new bootstrap.Modal(document.getElementById('createAgeCategoryModal')).show(); }
        function showCreatePartTypeModal(){ document.getElementById('ptName').value=''; document.getElementById('ptLevel').value=''; new bootstrap.Modal(document.getElementById('createPartTypeModal')).show(); }
        function showCreateParameterModal(){ document.getElementById('paramCode').value=''; document.getElementById('paramName').value=''; document.getElementById('paramType').value='REAL'; document.getElementById('paramUnit').value=''; document.getElementById('paramEnumId').value=''; new bootstrap.Modal(document.getElementById('createParameterModal')).show(); }
        function showCreateEnumerationModal(){ document.getElementById('enumName').value=''; document.getElementById('enumDesc').value=''; new bootstrap.Modal(document.getElementById('createEnumerationModal')).show(); }
        async function showCreateProductModal() {
            document.getElementById('productName').value = '';
            document.getElementById('productArticle').value = '';
            // Загружаем только терминальные классы
            try {
                const cats = await apiRequest('/categories');
                const terminal = cats.filter(c => c.node_type === 'терминальный');
                const opts = '<option value="">— выберите класс —</option>' +
                    terminal.map(c => `<option value="${c.id}">${escapeHtml(c.name)} (ID: ${c.id})</option>`).join('');
                const el = document.getElementById('productClassId');
                if (el) el.outerHTML = `<select class="form-select mb-2" id="productClassId">${opts}</select>`;
            } catch(e) { showToast('Не удалось загрузить классы: ' + e.message, 'error'); }
            new bootstrap.Modal(document.getElementById('createProductModal')).show();
        }
        function showCreateHOTypeModal(){ document.getElementById('hoTypeName').value=''; document.getElementById('hoTypeParent').value=''; new bootstrap.Modal(document.getElementById('createHOTypeModal')).show(); }
        function showCreateSubjectModal(){ document.getElementById('subjectName').value=''; document.getElementById('subjectInn').value=''; document.getElementById('subjectContact').value=''; document.getElementById('subjectPhone').value=''; new bootstrap.Modal(document.getElementById('createSubjectModal')).show(); }
        async function showCreateHOOperationModal(){ await preloadAdminRefs(); const el = document.getElementById('hoOpTypeId'); if (el && el.tagName === 'INPUT') el.outerHTML = `<select class="form-select mb-2" id="hoOpTypeId">${buildSelectOptions(adminCache.hoTypes, 'id', 'название')}</select>`; document.getElementById('hoOpNumber').value=''; document.getElementById('hoOpDate').value=''; new bootstrap.Modal(document.getElementById('createHOOperationModal')).show(); }
            
        function getNodeIconEmoji(t){const i={'промежуточный':'📁','терминальный':'📄','набор':'🧩','тематика':'🏷️','возрастная_категория':'🎂','тип_детали':'⚙️'}; return i[t]||'📦';}
        function getProductIconEmoji(t){const i={'set':'🧩','part':'🔧','minifigure':'🧸'}; return i[t]||'📦';}

function navigateAdmin(ev, fn) { if (ev?.preventDefault) ev.preventDefault(); if (ev?.currentTarget) setActiveNav(ev.currentTarget); fn(); }
async function preloadAdminRefs() { try { adminCache.themes = await apiRequest("/themes"); adminCache.ages = await apiRequest("/age-categories"); adminCache.partTypes = await apiRequest("/part-types"); adminCache.enums = await apiRequest("/enumerations"); } catch (_) {} }
async function fillSetSelects(prefix) { await preloadAdminRefs(); const age = document.getElementById(prefix + "AgeId"); const theme = document.getElementById(prefix + "ThemeId"); if (age) age.outerHTML = `<select class="form-select mb-2" id="${prefix}AgeId">${buildSelectOptions(adminCache.ages, "id", "name")}</select>`; if (theme) theme.outerHTML = `<select class="form-select mb-2" id="${prefix}ThemeId">${buildSelectOptions(adminCache.themes, "id", "name")}</select>`; }
async function fillPartTypeSelect(prefix) { await preloadAdminRefs(); const el = document.getElementById(prefix + "TypeId"); if (el) el.outerHTML = `<select class="form-select" id="${prefix}TypeId">${buildSelectOptions(adminCache.partTypes, "id", "name")}</select>`; }
document.addEventListener("DOMContentLoaded", () => {
    initSidebarToggle();
    preloadAdminRefs();
    initGlobalSearch(async (q) => {
        if (!q) { loadTree(); return; }
        navigateAdmin(null, loadSets);
        const sets = await apiRequest('/sets');
        const filtered = sets.filter(s =>
            `${s.name} ${s.catalog_number}`.toLowerCase().includes(q.toLowerCase())
        );
        let html = `<div class="page-header"><h1>Результаты поиска</h1><p class="subtitle">«${escapeHtml(q)}»</p></div>`;
        html += `<div class="card-panel"><div class="card-panel-body table-responsive"><table class="data-table"><thead><tr><th>ID</th><th>Название</th><th>Каталог</th><th>Год</th><th>Цена</th></tr></thead><tbody>`;
        for (const s of filtered) {
            html += `<tr><td>${s.id}</td><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.catalog_number)}</td><td>${s.year}</td><td>${formatPrice(s.price)}</td></tr>`;
        }
        html += `</tbody></table></div></div>`;
        document.getElementById('content').innerHTML = html;
    });
    loadTree();
});
