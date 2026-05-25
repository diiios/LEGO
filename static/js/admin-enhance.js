/** Доработки админки: валидация, выпадающие списки, дерево, редактирование */

// ——— Дерево классификатора ———
function renderTree(node) {
    const hasChildren = (node.children?.length > 0) || (node.products?.length > 0);
    const nameEsc = escapeHtml(node.name).replace(/'/g, '&#39;');
    let html = `<div class="tree-admin-row">
        <div class="tree-admin-main">
            <span class="tree-toggle" onclick="toggleTreeNode(this)">${hasChildren ? '▼' : '•'}</span>
            <span class="tree-icon">${getNodeIconEmoji(node.node_type)}</span>
            <span class="tree-name">${escapeHtml(node.name)}</span>
            <span class="tree-type">(${escapeHtml(node.node_type)}, ID: ${node.id})</span>
        </div>
        <div class="tree-admin-actions">
            <button type="button" class="btn btn-sm btn-outline-primary" title="Изменить" onclick="showEditCategoryModal(${node.id}, '${nameEsc}', ${node.sort_order || 0})"><i class="fas fa-edit"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary" title="Переместить" onclick="showMoveNodeModal(${node.id})"><i class="fas fa-arrows-alt"></i></button>
            <button type="button" class="btn btn-sm btn-outline-danger" title="Удалить" onclick="deleteNode(${node.id})"><i class="fas fa-trash"></i></button>
        </div>
    </div><div class="tree-children">`;
    if (node.children) for (const child of node.children) html += renderTree(child);
    if (node.products?.length > 0) {
        html += `<div class="tree-products">`;
        for (const product of node.products) {
            html += `<div class="product-item">${getProductIconEmoji(product.type)} ${escapeHtml(product.name)} <span class="text-muted">[${product.type}]</span></div>`;
        }
        html += `</div>`;
    }
    html += `</div>`;
    return html;
}

async function showMoveNodeModal(id) {
    document.getElementById('moveCatId').value = id;
    await setupCategoryParentSelect('moveCatParentId', id);
    openModal('moveCategoryModal');
}

async function confirmMoveCategory() {
    const id = document.getElementById('moveCatId').value;
    const parentVal = document.getElementById('moveCatParentId').value;
    const newParentId = parentVal ? parseInt(parentVal, 10) : null;
    if (newParentId === parseInt(id, 10)) {
        setFieldError('moveCatParentId', 'Нельзя выбрать сам узел родителем');
        return;
    }
    try {
        await apiRequest(`/categories/${id}/move`, 'PUT', { new_parent_id: newParentId });
        showToast('Категория перемещена');
        closeModal('moveCategoryModal');
        loadTree();
    } catch (e) { showToast(e.message, 'error'); }
}

// ——— Инициализация модалок ———
async function adminInitModals() {
    await ensureRefData();
    bindParamTypeEnumToggle('paramType', 'paramEnumId');
    bindParamTypeEnumToggle('editParamType', 'editParamEnumId');
    await setupEnumerationSelect('paramEnumId');
    await setupEnumerationSelect('editParamEnumId');
}

// ——— Валидация + обёртки CRUD ———
function validateCategoryForm(prefix = '') {
    const id = prefix ? `editCat` : 'cat';
    const rules = [
        () => V.text(prefix ? 'editCatName' : 'catName', 'Название'),
        () => V.nonNegative(prefix ? 'editCatSortOrder' : 'catSortOrder', 'Порядок', { required: false }),
    ];
    return runValidation(rules);
}

function validateSetForm(p) {
    const rules = [
        () => V.text(`${p}Name`, 'Название'),
        () => V.text(`${p}Catalog`, 'Каталожный номер'),
        () => V.year(`${p}Year`, 'Год'),
        () => V.nonNegative(`${p}Price`, 'Цена'),
        () => V.positiveInt(`${p}Parts`, 'Количество деталей'),
        () => V.requiredSelect(`${p}AgeId`, 'Возрастная категория'),
        () => V.requiredSelect(`${p}ThemeId`, 'Тематика'),
    ];
    return runValidation(rules);
}

function setCurrentYearMax(...ids) {
    const currentYear = new Date().getFullYear();
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.max = String(currentYear);
    });
}

function validatePartForm(p) {
    const rules = [
        () => V.text(`${p}Name`, 'Название'),
        () => V.requiredSelect(`${p}TypeId`, 'Тип детали'),
    ];
    return runValidation(rules);
}

function validateMinifigureForm(p) {
    const rules = [
        () => V.text(`${p}Name`, 'Название'),
        () => V.text(`${p}Character`, 'Персонаж'),
        () => V.text(`${p}Series`, 'Серия'),
        () => V.text(`${p}Code`, 'Уникальный код'),
    ];
    return runValidation(rules);
}

function validateAgeForm(p) {
    const rules = [
        () => V.text(`${p}Name`, 'Название'),
        () => V.age(`${p}Min`, 'Мин. возраст'),
        () => V.age(`${p}Max`, 'Макс. возраст'),
        () => V.ageRange(`${p}Min`, `${p}Max`),
    ];
    return runValidation(rules);
}

function validateParameterForm(p) {
    const rules = [
        () => V.text(`${p}Code`, 'Обозначение', { maxLen: 50 }),
        () => V.text(`${p}Name`, 'Полное наименование'),
    ];
    const type = getVal(`${p}Type`);
    if (type === 'ENUM') rules.push(() => V.requiredSelect(`${p}EnumId`, 'Перечисление'));
    return runValidation(rules);
}

function validateProductForm(p) {
    return runValidation([
        () => V.text(`${p}Name`, 'Наименование'),
        () => V.requiredSelect(`${p}ClassId`, 'Класс'),
    ]);
}

function validateHOTypeForm(p, excludeId = null) {
    const rules = [() => V.text(`${p}Name`, 'Название')];
    const parent = getVal(`${p}Parent`);
    if (parent && excludeId && parseInt(parent, 10) === excludeId) {
        rules.push(() => ({ fieldId: `${p}Parent`, message: 'Нельзя выбрать сам тип родителем' }));
    }
    return runValidation(rules);
}

function showAdminDynamicModal(title, bodyHtml, footerHtml = '') {
    const modal = document.createElement('div');
    modal.className = 'modal fade modal-app';
    modal.innerHTML = `<div class="modal-dialog modal-xl"><div class="modal-content">
        <div class="modal-header"><h5 class="modal-title">${escapeHtml(title)}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-footer">${footerHtml}<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div>
    </div></div>`;
    document.body.appendChild(modal);
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
    bootstrap.Modal.getOrCreateInstance(modal).show();
    return modal;
}

async function buildParamValueControl(param, fieldId, value = '') {
    const type = param.тип_параметра || param.тип;
    const enumId = param.перечисление_id;
    if (type === 'ENUM' && enumId) {
        const values = await apiRequest(`/enumerations/${enumId}/values`);
        let opts = '<option value="">— выберите —</option>';
        for (const v of values) {
            opts += `<option value="${v.id}"${String(value) === String(v.id) ? ' selected' : ''}>${escapeHtml(v.value)}</option>`;
        }
        return `<select class="form-select" id="${fieldId}">${opts}</select>`;
    }
    if (type === 'REAL' || type === 'INTEGER') {
        return `<input type="number" class="form-control" id="${fieldId}" step="${type === 'INTEGER' ? '1' : 'any'}" value="${escapeHtml(value ?? '')}">`;
    }
    if (type === 'DATETIME') {
        const dt = value ? String(value).replace(' ', 'T').slice(0, 16) : '';
        return `<input type="datetime-local" class="form-control" id="${fieldId}" value="${escapeHtml(dt)}">`;
    }
    return `<input type="text" class="form-control" id="${fieldId}" value="${escapeHtml(value ?? '')}">`;
}

function normalizeAdminValueByType(fieldId, type) {
    const raw = getVal(fieldId);
    if (raw === '') return null;
    if (type === 'INTEGER' || type === 'ENUM') return parseInt(raw, 10);
    if (type === 'REAL') return parseFloat(raw);
    if (type === 'DATETIME') return new Date(raw).toISOString();
    return raw;
}

let classParamDefinitions = [];

function selectedClassParamDefinition() {
    const id = parseInt(getVal('classParamParam'), 10);
    return classParamDefinitions.find(p => p.id === id) || null;
}

function renderClassParamConstraintFields() {
    const param = selectedClassParamDefinition();
    const box = document.getElementById('classParamConstraints');
    if (!box || !param) return;
    const type = String(param.тип_параметра || '').toUpperCase();
    const isNumber = type === 'REAL' || type === 'INTEGER';
    const defaultType = isNumber ? 'number' : (type === 'DATETIME' ? 'datetime-local' : 'text');
    const step = type === 'INTEGER' ? '1' : 'any';
    let html = '';
    if (isNumber) {
        html += `<div class="col-md-3"><input type="number" class="form-control" id="classParamMin" step="${step}" placeholder="Мин. значение"></div>
            <div class="col-md-3"><input type="number" class="form-control" id="classParamMax" step="${step}" placeholder="Макс. значение"></div>
            <div class="col-md-3"><input type="number" class="form-control" id="classParamDefault" step="${step}" placeholder="По умолчанию"></div>`;
    } else {
        html += `<input type="hidden" id="classParamMin"><input type="hidden" id="classParamMax">
            <div class="col-md-9"><input type="${defaultType}" class="form-control" id="classParamDefault" placeholder="Значение по умолчанию"></div>`;
    }
    html += `<div class="col-md-3 d-flex align-items-center"><label class="form-check mb-0"><input type="checkbox" class="form-check-input" id="classParamRequired"> Обязательный</label></div>`;
    box.innerHTML = html;
}

// Переопределение show*Modal
const _showCreateCategoryModal = typeof showCreateCategoryModal === 'function' ? showCreateCategoryModal : null;
async function showCreateCategoryModal() {
    await setupCategoryParentSelect('catParentId');
    ['catName', 'catParentId', 'catSortOrder'].forEach(clearFieldError);
    document.getElementById('catName').value = '';
    document.getElementById('catParentId').value = '';
    document.getElementById('catSortOrder').value = '0';
    openModal('createCategoryModal');
}

async function showCreateSetModal() {
    await fillSetSelects('set');
    ['setName', 'setCatalog', 'setYear', 'setPrice', 'setParts', 'setAgeId', 'setThemeId'].forEach(clearFieldError);
    setCurrentYearMax('setYear');
    document.getElementById('setName').value = '';
    document.getElementById('setCatalog').value = '';
    document.getElementById('setYear').value = '';
    document.getElementById('setPrice').value = '';
    document.getElementById('setParts').value = '';
    document.getElementById('setAgeId').value = '';
    document.getElementById('setThemeId').value = '';
    openModal('createSetModal');
}

async function showCreatePartModal() {
    await fillPartTypeSelect('part');
    ['partName', 'partTypeId'].forEach(clearFieldError);
    document.getElementById('partName').value = '';
    document.getElementById('partTypeId').value = '';
    openModal('createPartModal');
}

async function showCreateProductModal() {
    await setupClassSelect('productClassId');
    ['productName', 'productArticle', 'productClassId'].forEach(clearFieldError);
    document.getElementById('productName').value = '';
    document.getElementById('productArticle').value = '';
    document.getElementById('productClassId').value = '';
    const sel = document.getElementById('productClassId');
    if (sel) {
        sel.onchange = () => {
            const cid = parseInt(getVal('productClassId'), 10) || null;
            renderProductParamsForm('productParamsCreateArea', cid, null);
        };
    }
    await renderProductParamsForm('productParamsCreateArea', null, null);
    openModal('createProductModal');
}

async function showCreateHOTypeModal() {
    await preloadAdminRefs();
    await setupHoTypeParentSelect('hoTypeParent', adminCache.hoTypes);
    document.getElementById('hoTypeName').value = '';
    document.getElementById('hoTypeParent').value = '';
    openModal('createHOTypeModal');
}

async function showCreateHOOperationModal() {
    await preloadAdminRefs();
    const el = document.getElementById('hoOpTypeId');
    if (el) el.innerHTML = buildSelectOptions(adminCache.hoTypes, 'id', 'название');
    document.getElementById('hoOpNumber').value = '';
    document.getElementById('hoOpDate').value = '';
    openModal('createHOOperationModal');
}

async function showCreateParameterModal() {
    await setupEnumerationSelect('paramEnumId');
    bindParamTypeEnumToggle('paramType', 'paramEnumId');
    document.getElementById('paramCode').value = '';
    document.getElementById('paramName').value = '';
    document.getElementById('paramType').value = 'REAL';
    document.getElementById('paramUnit').value = '';
    document.getElementById('paramEnumId').value = '';
    openModal('createParameterModal');
}

async function showEditParameterModal(id) {
    try {
        const p = await apiRequest(`/parameters/${id}`);
        await setupEnumerationSelect('editParamEnumId');
        bindParamTypeEnumToggle('editParamType', 'editParamEnumId');
        document.getElementById('editParamId').value = p.id;
        document.getElementById('editParamCode').value = p.обозначение;
        document.getElementById('editParamName').value = p.полное_имя;
        document.getElementById('editParamType').value = p.тип_параметра;
        document.getElementById('editParamUnit').value = p.единица_измерения || '';
        document.getElementById('editParamEnumId').value = p.перечисление_id || '';
        document.getElementById('editParamType').dispatchEvent(new Event('change'));
        openModal('editParameterModal');
    } catch (e) { showToast(e.message, 'error'); }
}

async function showEditPartModal(id) {
    try {
        const p = await apiRequest(`/parts/${id}`);
        await fillPartTypeSelect('editPart');
        document.getElementById('editPartId').value = p.id;
        document.getElementById('editPartName').value = p.name;
        document.getElementById('editPartTypeId').value = p.part_type_id;
        openModal('editPartModal');
    } catch (e) { showToast(e.message, 'error'); }
}

async function showEditMinifigureModal(id) {
    try {
        const m = await apiRequest(`/minifigures/${id}`);
        document.getElementById('editMfId').value = m.id;
        document.getElementById('editMfName').value = m.name;
        document.getElementById('editMfCharacter').value = m.character;
        document.getElementById('editMfSeries').value = m.series;
        document.getElementById('editMfCode').value = m.unique_code;
        openModal('editMinifigureModal');
    } catch (e) { showToast(e.message, 'error'); }
}

async function showEditProductModal(id) {
    try {
        const p = await apiRequest(`/products/${id}`);
        await setupClassSelect('editProductClassId');
        document.getElementById('editProductId').value = p.id;
        document.getElementById('editProductName').value = p.наименование;
        document.getElementById('editProductArticle').value = p.артикул || '';
        document.getElementById('editProductClassId').value = p.класс_id;
        const sel = document.getElementById('editProductClassId');
        if (sel) {
            sel.onchange = () => {
                const cid = parseInt(getVal('editProductClassId'), 10) || null;
                const pid = parseInt(document.getElementById('editProductId').value, 10);
                renderProductParamsForm('productParamsEditArea', cid, pid);
            };
        }
        await renderProductParamsForm('productParamsEditArea', p.класс_id, p.id);
        openModal('editProductModal');
    } catch (e) { showToast(e.message, 'error'); }
}

async function showEditHOTypeModal(id, name, parent) {
    await preloadAdminRefs();
    await setupHoTypeParentSelect('editHOTypeParent', adminCache.hoTypes, parseInt(id, 10));
    document.getElementById('editHOTypeId').value = id;
    document.getElementById('editHOTypeName').value = name;
    document.getElementById('editHOTypeParent').value = parent || '';
    openModal('editHOTypeModal');
}

async function showEditHORoleModal(id, name, classId) {
    await setupClassSelect('editRoleClassId', '— не ограничено —');
    document.getElementById('editRoleId').value = id;
    document.getElementById('editRoleName').value = name;
    document.getElementById('editRoleClassId').value = classId || '';
    openModal('editHORoleModal');
}

async function showAddHORoleModal(typeId) {
    await setupClassSelect('newRoleClassId', '— не ограничено —');
    document.getElementById('currentHOTypeId').value = typeId;
    document.getElementById('newRoleName').value = '';
    document.getElementById('newRoleClassId').value = '';
    openModal('addHORoleModal');
}

// Обёртки create/update с валидацией
async function createCategory() {
    if (!validateCategoryForm()) return;
    const data = { name: getVal('catName'), sort_order: parseInt(getVal('catSortOrder') || '0', 10) };
    const pid = getVal('catParentId');
    if (pid) data.parent_id = parseInt(pid, 10);
    try {
        await apiRequest('/categories', 'POST', data);
        showToast('Категория создана');
        closeModal('createCategoryModal');
        loadCategories();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateCategory() {
    if (!validateCategoryForm('edit')) return;
    const id = document.getElementById('editCatId').value;
    try {
        await apiRequest(`/categories/${id}`, 'PUT', { name: getVal('editCatName'), sort_order: parseInt(getVal('editCatSortOrder') || '0', 10) });
        showToast('Категория обновлена');
        closeModal('editCategoryModal');
        loadCategories();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createSet() {
    if (!validateSetForm('set')) return;
    const data = {
        name: getVal('setName'), catalog_number: getVal('setCatalog'),
        year: parseInt(getVal('setYear'), 10), price: parseFloat(getVal('setPrice')),
        parts_count: parseInt(getVal('setParts'), 10),
        age_category_id: parseInt(getVal('setAgeId'), 10), theme_id: parseInt(getVal('setThemeId'), 10),
    };
    try {
        await apiRequest('/sets', 'POST', data);
        showToast('Набор создан');
        closeModal('createSetModal');
        loadSets();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateSet() {
    if (!validateSetForm('editSet')) return;
    const id = document.getElementById('editSetId').value;
    const data = {
        name: getVal('editSetName'), catalog_number: getVal('editSetCatalog'),
        year: parseInt(getVal('editSetYear'), 10), price: parseFloat(getVal('editSetPrice')),
        parts_count: parseInt(getVal('editSetParts'), 10),
        age_category_id: parseInt(getVal('editSetAgeId'), 10), theme_id: parseInt(getVal('editSetThemeId'), 10),
    };
    try {
        await apiRequest(`/sets/${id}`, 'PUT', data);
        showToast('Набор обновлён');
        closeModal('editSetModal');
        loadSets();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createPart() {
    if (!validatePartForm('part')) return;
    const data = {
        name: getVal('partName'), part_type_id: parseInt(getVal('partTypeId'), 10),
    };
    try {
        await apiRequest('/parts', 'POST', data);
        showToast('Деталь создана');
        closeModal('createPartModal');
        loadParts();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updatePart() {
    if (!validatePartForm('editPart')) return;
    const id = document.getElementById('editPartId').value;
    const data = {
        name: getVal('editPartName'), part_type_id: parseInt(getVal('editPartTypeId'), 10),
    };
    try {
        await apiRequest(`/parts/${id}`, 'PUT', data);
        showToast('Деталь обновлена');
        closeModal('editPartModal');
        loadParts();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateMinifigure() {
    if (!validateMinifigureForm('editMf')) return;
    const id = document.getElementById('editMfId').value;
    const data = {
        name: getVal('editMfName'), character: getVal('editMfCharacter'),
        series: getVal('editMfSeries'), unique_code: getVal('editMfCode'),
    };
    try {
        await apiRequest(`/minifigures/${id}`, 'PUT', data);
        showToast('Мини-фигурка обновлена');
        closeModal('editMinifigureModal');
        loadMinifigures();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createMinifigure() {
    if (!validateMinifigureForm('mf')) return;
    const data = {
        name: getVal('mfName'), character: getVal('mfCharacter'),
        series: getVal('mfSeries'), unique_code: getVal('mfCode'),
    };
    try {
        await apiRequest('/minifigures', 'POST', data);
        showToast('Мини-фигурка создана');
        closeModal('createMinifigureModal');
        loadMinifigures();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createAgeCategory() {
    if (!validateAgeForm('age')) return;
    const data = { name: getVal('ageName'), min_age: parseInt(getVal('ageMin'), 10), max_age: parseInt(getVal('ageMax'), 10) };
    try {
        await apiRequest('/age-categories', 'POST', data);
        showToast('Возрастная категория создана');
        closeModal('createAgeCategoryModal');
        loadAgeCategories();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateAgeCategory() {
    if (!validateAgeForm('editAge')) return;
    const id = document.getElementById('editAgeId').value;
    const data = { name: getVal('editAgeName'), min_age: parseInt(getVal('editAgeMin'), 10), max_age: parseInt(getVal('editAgeMax'), 10) };
    try {
        await apiRequest(`/age-categories/${id}`, 'PUT', data);
        showToast('Возрастная категория обновлена');
        closeModal('editAgeCategoryModal');
        loadAgeCategories();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createParameter() {
    if (!validateParameterForm('param')) return;
    const data = {
        обозначение: getVal('paramCode'), полное_имя: getVal('paramName'),
        тип_параметра: getVal('paramType'), единица_измерения: getVal('paramUnit') || null,
        перечисление_id: getVal('paramEnumId') ? parseInt(getVal('paramEnumId'), 10) : null,
    };
    try {
        await apiRequest('/parameters', 'POST', data);
        showToast('Параметр создан');
        closeModal('createParameterModal');
        loadParameters();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateParameter() {
    if (!validateParameterForm('editParam')) return;
    const id = document.getElementById('editParamId').value;
    const data = {
        обозначение: getVal('editParamCode'), полное_имя: getVal('editParamName'),
        тип_параметра: getVal('editParamType'), единица_измерения: getVal('editParamUnit') || null,
        перечисление_id: getVal('editParamEnumId') ? parseInt(getVal('editParamEnumId'), 10) : null,
    };
    try {
        await apiRequest(`/parameters/${id}`, 'PUT', data);
        showToast('Параметр обновлён');
        closeModal('editParameterModal');
        loadParameters();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createProduct() {
    if (!validateProductForm('product')) return;
    if (!validateProductParamsForm('productParamsCreateArea')) return;
    const data = {
        класс_id: parseInt(getVal('productClassId'), 10),
        наименование: getVal('productName'),
        артикул: getVal('productArticle') || null,
    };
    try {
        const res = await apiRequest('/products', 'POST', data);
        const productId = res.product_id;
        if (!productId) throw new Error('Сервер не вернул ID изделия');
        const pr = await saveProductParamsFromForm('productParamsCreateArea', productId);
        if (pr.errors.length) {
            showToast(`Изделие создано, но есть ошибки параметров: ${pr.errors.join('; ')}`, 'error');
        } else {
            showToast(`Изделие создано${pr.saved ? `, параметров: ${pr.saved}` : ''}`, 'success');
        }
        invalidateClassParamsCache();
        closeModal('createProductModal');
        applyAdminProductsFilter();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateProduct() {
    if (!validateProductForm('editProduct')) return;
    if (!validateProductParamsForm('productParamsEditArea')) return;
    const id = parseInt(document.getElementById('editProductId').value, 10);
    const data = {
        класс_id: parseInt(getVal('editProductClassId'), 10),
        наименование: getVal('editProductName'),
        артикул: getVal('editProductArticle') || null,
    };
    try {
        await apiRequest(`/products/${id}`, 'PUT', data);
        const pr = await saveProductParamsFromForm('productParamsEditArea', id);
        if (pr.errors.length) {
            showToast(`Сохранено с ошибками: ${pr.errors.join('; ')}`, 'error');
        } else {
            showToast(`Изделие обновлено${pr.saved || pr.deleted ? ` (параметры: +${pr.saved}, −${pr.deleted})` : ''}`, 'success');
        }
        invalidateClassParamsCache();
        closeModal('editProductModal');
        applyAdminProductsFilter();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createHOType() {
    const id = null;
    if (!validateHOTypeForm('hoType', id)) return;
    const data = {
        название: getVal('hoTypeName'),
        родительский_id: getVal('hoTypeParent') ? parseInt(getVal('hoTypeParent'), 10) : null,
    };
    try {
        await apiRequest('/ho-types', 'POST', data);
        showToast('Тип ХО создан');
        closeModal('createHOTypeModal');
        loadHOTypes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateHOType() {
    const id = parseInt(document.getElementById('editHOTypeId').value, 10);
    if (!validateHOTypeForm('editHOType', id)) return;
    const data = {
        название: getVal('editHOTypeName'),
        родительский_id: getVal('editHOTypeParent') ? parseInt(getVal('editHOTypeParent'), 10) : null,
    };
    try {
        await apiRequest(`/ho-types/${id}`, 'PUT', data);
        showToast('Тип ХО обновлён');
        closeModal('editHOTypeModal');
        loadHOTypes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateHORole() {
    if (!runValidation([() => V.text('editRoleName', 'Название роли')])) return;
    const id = document.getElementById('editRoleId').value;
    const data = {
        название: getVal('editRoleName'),
        допустимый_класс_СХД: getVal('editRoleClassId') ? parseInt(getVal('editRoleClassId'), 10) : null,
    };
    try {
        await apiRequest(`/ho-roles/${id}`, 'PUT', data);
        showToast('Роль обновлена');
        closeModal('editHORoleModal');
        loadHORoles();
    } catch (e) { showToast(e.message, 'error'); }
}

async function addHORole() {
    if (!runValidation([() => V.text('newRoleName', 'Название роли')])) return;
    const typeId = document.getElementById('currentHOTypeId').value;
    const data = {
        название: getVal('newRoleName'),
        допустимый_класс_СХД: getVal('newRoleClassId') ? parseInt(getVal('newRoleClassId'), 10) : null,
    };
    try {
        await apiRequest(`/ho-types/${typeId}/roles`, 'POST', data);
        showToast('Роль добавлена');
        closeModal('addHORoleModal');
        loadHOTypes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function loadClassifierTools() {
    showLoading();
    try {
        await loadCategoriesList();
        const opts = buildCategorySelectOptions(REF_CACHE.categories, '— выберите узел —');
        document.getElementById('content').innerHTML = `
            <div class="card">
                <div class="card-header"><i class="fas fa-screwdriver-wrench"></i> Сервис классификатора</div>
                <div class="card-body">
                    <div class="row g-3 mb-3">
                        <div class="col-md-6"><label class="form-label">Узел</label><select class="form-select" id="toolNodeId">${opts}</select></div>
                        <div class="col-md-3"><label class="form-label">Базовая ед. изм. (ID)</label><input type="number" class="form-control" id="toolBaseUnit" min="1"></div>
                        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-primary w-100" onclick="setClassifierBaseUnit()"><i class="fas fa-save"></i> Установить</button></div>
                    </div>
                    <div class="d-flex flex-wrap gap-2 mb-3">
                        <button class="btn btn-outline-primary" onclick="showCategoryInfo('descendants')"><i class="fas fa-sitemap"></i> Потомки</button>
                        <button class="btn btn-outline-primary" onclick="showCategoryInfo('ancestors')"><i class="fas fa-level-up-alt"></i> Родители</button>
                        <button class="btn btn-outline-primary" onclick="showCategoryInfo('terminals')"><i class="fas fa-file"></i> Терминальные</button>
                        <button class="btn btn-outline-warning" onclick="runCycleDiagnostics()"><i class="fas fa-project-diagram"></i> Циклы</button>
                        <button class="btn btn-outline-danger" onclick="cleanupPartsAnomalies()"><i class="fas fa-broom"></i> Очистить аномалии деталей</button>
                    </div>
                    <div class="border-top pt-3">
                        <h6>Создать подкатегорию по имени родителя</h6>
                        <div class="row g-2">
                            <div class="col-md-5"><input type="text" class="form-control" id="subcatParentName" placeholder="Имя родителя"></div>
                            <div class="col-md-5"><input type="text" class="form-control" id="subcatChildName" placeholder="Имя новой подкатегории"></div>
                            <div class="col-md-2"><button class="btn btn-success w-100" onclick="createSubcategoryByParentName()"><i class="fas fa-plus"></i> Создать</button></div>
                        </div>
                    </div>
                    <div class="border-top pt-3 mt-3">
                        <h6>Изменить порядок потомков</h6>
                        <div class="row g-2">
                            <div class="col-md-4"><select class="form-select" id="reorderParentId">${opts}</select></div>
                            <div class="col-md-6"><input type="text" class="form-control" id="reorderChildIds" placeholder="ID потомков через запятую: 12, 14, 13"></div>
                            <div class="col-md-2"><button class="btn btn-primary w-100" onclick="reorderCategoryChildren()"><i class="fas fa-sort"></i> Сохранить</button></div>
                        </div>
                    </div>
                    <div id="classifierToolsResult" class="mt-3"></div>
                </div>
            </div>`;
    } catch (e) { showError(e.message); }
}

async function setClassifierBaseUnit() {
    const nodeId = getVal('toolNodeId');
    const baseId = getVal('toolBaseUnit');
    if (!nodeId || !baseId) return showToast('Выберите узел и укажите ID единицы', 'error');
    try {
        await apiRequest(`/categories/${nodeId}/base-unit`, 'PUT', { base_ei_id: parseInt(baseId, 10) });
        showToast('Базовая единица установлена');
    } catch (e) { showToast(e.message, 'error'); }
}

async function showCategoryInfo(kind) {
    const nodeId = getVal('toolNodeId');
    if (!nodeId) return showToast('Выберите узел', 'error');
    const titleMap = { descendants: 'Потомки узла', ancestors: 'Родители узла', terminals: 'Терминальные классы' };
    try {
        const rows = await apiRequest(`/categories/${nodeId}/${kind}`);
        renderClassifierToolRows(titleMap[kind], rows);
    } catch (e) { showToast(e.message, 'error'); }
}

function renderClassifierToolRows(title, rows) {
    const box = document.getElementById('classifierToolsResult');
    if (!box) return;
    let html = `<h6>${escapeHtml(title)}</h6>`;
    if (!rows.length) {
        html += '<div class="alert alert-info small mb-0">Данных нет.</div>';
    } else {
        html += '<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr><th>ID</th><th>Название</th><th>Тип</th><th>Родитель</th><th>Уровень</th></tr></thead><tbody>';
        for (const r of rows) {
            html += `<tr><td>${r.id ?? r.node_id}</td><td>${escapeHtml(r.название || r.node_name || '')}</td><td>${escapeHtml(r.тип_элемента || '')}</td><td>${r.родительский_id ?? '—'}</td><td>${r.уровень ?? '—'}</td></tr>`;
        }
        html += '</tbody></table></div>';
    }
    box.innerHTML = html;
}

async function runCycleDiagnostics() {
    try {
        const rows = await apiRequest('/cycles');
        const box = document.getElementById('classifierToolsResult');
        if (!rows.length) {
            box.innerHTML = '<div class="alert alert-success small mb-0">Циклы не найдены.</div>';
            return;
        }
        let html = '<h6>Найденные циклы</h6><div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr><th>ID</th><th>Узел</th><th>Путь</th></tr></thead><tbody>';
        for (const r of rows) html += `<tr><td>${r.node_id}</td><td>${escapeHtml(r.node_name)}</td><td>${escapeHtml(r.path)}</td></tr>`;
        html += '</tbody></table></div>';
        box.innerHTML = html;
    } catch (e) { showToast(e.message, 'error'); }
}

async function cleanupPartsAnomalies() {
    if (!confirm('Запустить очистку аномалий деталей?')) return;
    try {
        const res = await apiRequest('/parts/cleanup-anomalies', 'POST');
        showToast(`Очистка завершена: удалено ${res.removed_count || 0}`);
    } catch (e) { showToast(e.message, 'error'); }
}

async function createSubcategoryByParentName() {
    const parent = getVal('subcatParentName');
    const child = getVal('subcatChildName');
    if (!parent || !child) return showToast('Укажите имя родителя и подкатегории', 'error');
    try {
        await apiRequest('/categories/subcategory', 'POST', { parent_name: parent, child_name: child });
        REF_CACHE.categories = null;
        showToast('Подкатегория создана');
        loadClassifierTools();
    } catch (e) { showToast(e.message, 'error'); }
}

async function reorderCategoryChildren() {
    const parentId = getVal('reorderParentId');
    const ids = (getVal('reorderChildIds') || '').split(',').map(x => parseInt(x.trim(), 10)).filter(Boolean);
    if (!parentId || !ids.length) return showToast('Укажите родителя и список ID потомков', 'error');
    try {
        await apiRequest(`/categories/${parentId}/reorder`, 'PUT', { ordered_child_ids: ids });
        showToast('Порядок потомков сохранён');
        loadTree();
    } catch (e) { showToast(e.message, 'error'); }
}

async function loadClassParametersAdmin() {
    showLoading();
    try {
        await Promise.all([loadCategoriesList(), preloadAdminRefs()]);
        classParamDefinitions = await apiRequest('/parameters');
        const classOpts = buildCategorySelectOptions(REF_CACHE.categories, '— выберите класс —');
        document.getElementById('content').innerHTML = `
            <div class="card">
                <div class="card-header"><i class="fas fa-link"></i> Параметры классов</div>
                <div class="card-body">
                    <div class="row g-2 mb-3">
                        <div class="col-md-5"><label class="form-label">Класс</label><select class="form-select" id="classParamClass" onchange="loadClassParametersTable()">${classOpts}</select></div>
                        <div class="col-md-5"><label class="form-label">Параметр</label><select class="form-select" id="classParamParam" onchange="renderClassParamConstraintFields()">${buildSelectOptions(classParamDefinitions, 'id', 'полное_имя')}</select></div>
                        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-success w-100" onclick="addParamToClassAdmin()"><i class="fas fa-plus"></i> Привязать</button></div>
                    </div>
                    <div class="row g-2 mb-3" id="classParamConstraints"></div>
                    <div class="alert alert-info small">Таблица показывает параметры выбранного класса вместе с унаследованными от родителей.</div>
                    <div id="classParamsResult"></div>
                </div>
            </div>`;
        renderClassParamConstraintFields();
    } catch (e) { showError(e.message); }
}

async function loadClassParametersTable() {
    const classId = getVal('classParamClass');
    const box = document.getElementById('classParamsResult');
    if (!box) return;
    if (!classId) {
        box.innerHTML = '<div class="empty-state">Выберите класс.</div>';
        return;
    }
    box.innerHTML = '<div class="spinner-border spinner-border-sm"></div>';
    try {
        const params = await apiRequest(`/classes/${classId}/parameters`);
        let html = '<div class="table-responsive"><table class="table table-bordered"><thead><tr><th>Код</th><th>Имя</th><th>Тип</th><th>Ограничения</th><th>Источник</th><th></th></tr></thead><tbody>';
        for (const p of params) {
            const own = String(p.класс_источник) === String(classId);
            html += `<tr><td><code>${escapeHtml(p.обозначение)}</code></td><td>${escapeHtml(p.полное_имя)}</td><td>${escapeHtml(p.тип_параметра)}</td><td>${p.мин_значение ?? '—'} … ${p.макс_значение ?? '—'}${p.обязательный ? ' · обяз.' : ''}</td><td>${own ? 'этот класс' : 'родитель ' + p.класс_источник}</td><td>${own ? `<button class="btn btn-sm btn-outline-danger" onclick="removeParamFromClassAdmin(${p.param_class_id})"><i class="fas fa-unlink"></i></button>` : ''}</td></tr>`;
        }
        html += params.length ? '</tbody></table></div>' : '<tr><td colspan="6" class="text-muted text-center">Параметры не привязаны</td></tr></tbody></table></div>';
        box.innerHTML = html;
    } catch (e) { box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`; }
}

async function addParamToClassAdmin() {
    const classId = getVal('classParamClass');
    const paramId = getVal('classParamParam');
    if (!classId || !paramId) return showToast('Выберите класс и параметр', 'error');
    const param = selectedClassParamDefinition();
    const type = String(param?.тип_параметра || '').toUpperCase();
    const numeric = type === 'REAL' || type === 'INTEGER';
    if (numeric) {
        const minVal = getVal('classParamMin');
        const maxVal = getVal('classParamMax');
        const defVal = getVal('classParamDefault');
        if (minVal && Number.isNaN(Number(minVal))) return showToast('Мин. значение должно быть числом', 'error');
        if (maxVal && Number.isNaN(Number(maxVal))) return showToast('Макс. значение должно быть числом', 'error');
        if (defVal && Number.isNaN(Number(defVal))) return showToast('Значение по умолчанию должно быть числом', 'error');
        if (minVal && maxVal && Number(minVal) > Number(maxVal)) return showToast('Мин. значение не может быть больше максимального', 'error');
    }
    const payload = {
        параметр_id: parseInt(paramId, 10),
        мин_значение: numeric && getVal('classParamMin') ? parseFloat(getVal('classParamMin')) : null,
        макс_значение: numeric && getVal('classParamMax') ? parseFloat(getVal('classParamMax')) : null,
        значение_по_умолчанию: getVal('classParamDefault') || null,
        обязательный: document.getElementById('classParamRequired')?.checked || false,
    };
    try {
        await apiRequest(`/classes/${classId}/parameters`, 'POST', payload);
        invalidateClassParamsCache();
        showToast('Параметр привязан к классу');
        loadClassParametersTable();
    } catch (e) { showToast(e.message, 'error'); }
}

async function removeParamFromClassAdmin(paramClassId) {
    if (!confirm('Отвязать параметр от класса?')) return;
    try {
        await apiRequest(`/classes/parameters/${paramClassId}`, 'DELETE');
        invalidateClassParamsCache();
        showToast('Параметр отвязан');
        loadClassParametersTable();
    } catch (e) { showToast(e.message, 'error'); }
}

// Таблицы: кнопки редактирования
const _loadMinifigures = loadMinifigures;
loadMinifigures = async function() {
    await _loadMinifigures();
    document.querySelectorAll('#content table tbody tr').forEach(tr => {
        const btnCell = tr.querySelector('.action-buttons');
        if (!btnCell || btnCell.querySelector('.btn-warning')) return;
        const id = tr.cells[0]?.textContent;
        const editBtn = `<button type="button" class="btn btn-sm btn-warning me-1" onclick="showEditMinifigureModal(${id})"><i class="fas fa-edit"></i></button>`;
        btnCell.innerHTML = editBtn + btnCell.innerHTML;
    });
};

let adminProductsFilterClass = '';

async function renderAdminProductsTable(products) {
    let rows = '';
    for (const p of products) {
        rows += `<tr><td>${p.id}</td><td>${escapeHtml(p.наименование)}</td><td><code>${escapeHtml(p.артикул || '—')}</code></td><td>${escapeHtml(p.класс_название || p.класс_id)}</td>
            <td class="action-buttons">
            <button type="button" class="btn btn-sm btn-warning me-1" onclick="showEditProductModal(${p.id})" title="Изменить и параметры"><i class="fas fa-edit"></i></button>
            <button type="button" class="btn btn-sm btn-info me-1" onclick="showProductParams(${p.id})" title="Просмотр параметров"><i class="fas fa-chart-line"></i></button>
            <button type="button" class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id})"><i class="fas fa-trash"></i></button></td></tr>`;
    }
    return rows;
}

async function applyAdminProductsFilter() {
    const tbody = document.querySelector('#adminProductsTable tbody');
    const countEl = document.getElementById('adminProductsCount');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></td></tr>`;
    try {
        const classId = getVal('adminProdClassFilter');
        const text = (getVal('adminProdTextFilter') || '').toLowerCase();
        adminProductsFilterClass = classId;
        let products;
        if (classId) {
            products = await apiRequest('/products/filter', 'POST', { class_ids: [parseInt(classId, 10)] });
        } else {
            products = await apiRequest('/products');
        }
        if (text) {
            products = products.filter(p =>
                (p.наименование || '').toLowerCase().includes(text)
                || (p.артикул || '').toLowerCase().includes(text)
            );
        }
        if (!products.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-muted text-center py-3">Изделия не найдены</td></tr>';
        } else {
            tbody.innerHTML = await renderAdminProductsTable(products);
        }
        if (countEl) {
            countEl.textContent = classId
                ? `Показано: ${products.length} (класс и подклассы)`
                : `Показано: ${products.length} — все классы`;
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-danger">${escapeHtml(e.message)}</td></tr>`;
    }
}

loadProducts = async function() {
    showLoading();
    try {
        await loadCategoriesList();
        const classOpts = buildCategorySelectOptions(REF_CACHE.categories, '— выберите класс —');
        document.getElementById('content').innerHTML = `
            <div class="card">
                <div class="card-header"><i class="fas fa-box"></i> Изделия (склад)
                    <div class="float-end">
                        <button class="btn btn-sm btn-success me-2" onclick="showCreateProductModal()"><i class="fas fa-plus"></i> Создать</button>
                        <button class="btn btn-sm btn-primary" onclick="applyAdminProductsFilter()"><i class="fas fa-sync-alt"></i> Обновить</button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="alert alert-info small">Сначала выберите <strong>класс</strong>, чтобы не просматривать весь склад. Параметры изделия задаются при создании/редактировании.</div>
                    <div class="row g-2 mb-3">
                        <div class="col-md-5"><label class="form-label">Класс изделия</label><select class="form-select" id="adminProdClassFilter">${classOpts}</select></div>
                        <div class="col-md-5"><label class="form-label">Название или артикул</label><input type="text" class="form-control" id="adminProdTextFilter" placeholder="Часть названия"></div>
                        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-primary w-100" onclick="applyAdminProductsFilter()"><i class="fas fa-search"></i> Найти</button></div>
                    </div>
                    <p class="small text-muted" id="adminProductsCount"></p>
                    <div class="table-responsive"><table class="table table-bordered" id="adminProductsTable"><thead><tr><th>ID</th><th>Наименование</th><th>Артикул</th><th>Класс</th><th>Действия</th></tr></thead><tbody></tbody></table></div>
                </div>
            </div>`;
        if (adminProductsFilterClass) {
            document.getElementById('adminProdClassFilter').value = adminProductsFilterClass;
        }
        await applyAdminProductsFilter();
    } catch (e) { showError(e.message); }
};

async function createTheme() {
    if (!runValidation([() => V.text('themeName', 'Название')])) return;
    const data = { name: getVal('themeName'), description: getVal('themeDesc') || '' };
    try {
        await apiRequest('/themes', 'POST', data);
        showToast('Тематика создана');
        closeModal('createThemeModal');
        loadThemes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateTheme() {
    if (!runValidation([() => V.text('editThemeName', 'Название')])) return;
    const id = document.getElementById('editThemeId').value;
    try {
        await apiRequest(`/themes/${id}`, 'PUT', { name: getVal('editThemeName'), description: getVal('editThemeDesc') || '' });
        showToast('Тематика обновлена');
        closeModal('editThemeModal');
        loadThemes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createPartType() {
    if (!runValidation([
        () => V.text('ptName', 'Название'),
        () => V.positiveInt('ptLevel', 'Уровень иерархии', { min: 1, max: 10 }),
    ])) return;
    try {
        await apiRequest('/part-types', 'POST', { name: getVal('ptName'), hierarchy_level: parseInt(getVal('ptLevel'), 10) });
        showToast('Тип детали создан');
        closeModal('createPartTypeModal');
        loadPartTypes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updatePartType() {
    if (!runValidation([
        () => V.text('editPartTypeName', 'Название'),
        () => V.positiveInt('editPartTypeLevel', 'Уровень иерархии', { min: 1, max: 10 }),
    ])) return;
    const id = document.getElementById('editPartTypeId').value;
    try {
        await apiRequest(`/part-types/${id}`, 'PUT', { name: getVal('editPartTypeName'), hierarchy_level: parseInt(getVal('editPartTypeLevel'), 10) });
        showToast('Тип детали обновлён');
        closeModal('editPartTypeModal');
        loadPartTypes();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createEnumeration() {
    if (!runValidation([() => V.text('enumName', 'Название')])) return;
    try {
        await apiRequest('/enumerations', 'POST', { name: getVal('enumName'), description: getVal('enumDesc') || null });
        showToast('Перечисление создано');
        closeModal('createEnumerationModal');
        loadEnumerations();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateEnumeration() {
    if (!runValidation([() => V.text('editEnumName', 'Название')])) return;
    const id = document.getElementById('editEnumId').value;
    try {
        await apiRequest(`/enumerations/${id}`, 'PUT', { name: getVal('editEnumName'), description: getVal('editEnumDesc') || null });
        showToast('Перечисление обновлено');
        closeModal('editEnumerationModal');
        loadEnumerations();
    } catch (e) { showToast(e.message, 'error'); }
}

async function addEnumValue() {
    if (!runValidation([() => V.text('newEnumValue', 'Значение')])) return;
    const enumId = document.getElementById('currentEnumId').value;
    const order = getVal('newEnumValueOrder');
    try {
        await apiRequest(`/enumerations/${enumId}/values`, 'POST', {
            value: getVal('newEnumValue'),
            sort_order: order ? parseInt(order, 10) : null,
        });
        showToast('Значение добавлено');
        closeModal('addEnumValueModal');
        loadEnumerations();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateEnumValue() {
    if (!runValidation([() => V.text('editEnumValue', 'Значение')])) return;
    const id = document.getElementById('editEnumValueId').value;
    try {
        await apiRequest(`/enum-values/${id}`, 'PUT', {
            value: getVal('editEnumValue'),
            sort_order: parseInt(getVal('editEnumValueOrder') || '0', 10),
        });
        showToast('Значение обновлено');
        closeModal('editEnumValueModal');
        loadEnumValuesAll();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createSubject() {
    if (!runValidation([() => V.text('subjectName', 'Наименование')])) return;
    try {
        await apiRequest('/subjects', 'POST', {
            наименование: getVal('subjectName'),
            инн: getVal('subjectInn') || null,
            контактное_лицо: getVal('subjectContact') || null,
            телефон: getVal('subjectPhone') || null,
        });
        showToast('Субъект создан');
        closeModal('createSubjectModal');
        loadSubjects();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateSubject() {
    if (!runValidation([() => V.text('editSubjectName', 'Наименование')])) return;
    const id = document.getElementById('editSubjectId').value;
    try {
        await apiRequest(`/subjects/${id}`, 'PUT', {
            наименование: getVal('editSubjectName'),
            инн: getVal('editSubjectInn') || null,
            контактное_лицо: getVal('editSubjectContact') || null,
            телефон: getVal('editSubjectPhone') || null,
        });
        showToast('Субъект обновлён');
        closeModal('editSubjectModal');
        loadSubjects();
    } catch (e) { showToast(e.message, 'error'); }
}

async function createHOOperation() {
    if (!runValidation([
        () => V.requiredSelect('hoOpTypeId', 'Тип операции'),
        () => V.text('hoOpNumber', 'Номер документа'),
    ])) return;
    const date = getVal('hoOpDate');
    try {
        await apiRequest('/ho-operations', 'POST', {
            тип_хо_id: parseInt(getVal('hoOpTypeId'), 10),
            номер_документа: getVal('hoOpNumber'),
            дата: date ? new Date(date).toISOString() : new Date().toISOString(),
        });
        showToast('Операция создана');
        closeModal('createHOOperationModal');
        loadHOOps();
    } catch (e) { showToast(e.message, 'error'); }
}

async function showEditSetModal(id) {
    try {
        const s = await apiRequest(`/sets/${id}`);
        await fillSetSelects('editSet');
        setCurrentYearMax('editSetYear');
        document.getElementById('editSetId').value = s.id;
        document.getElementById('editSetName').value = s.name;
        document.getElementById('editSetCatalog').value = s.catalog_number;
        document.getElementById('editSetYear').value = s.year;
        document.getElementById('editSetPrice').value = s.price;
        document.getElementById('editSetParts').value = s.parts_count;
        document.getElementById('editSetAgeId').value = s.age_category_id;
        document.getElementById('editSetThemeId').value = s.theme_id;
        openModal('editSetModal');
    } catch (e) { showToast(e.message, 'error'); }
}

loadSets = async function() {
    showLoading();
    try {
        await preloadAdminRefs();
        const themeOpts = '<option value="">— любая тематика —</option>'
            + buildSelectOptions(adminCache.themes, 'id', 'name');
        document.getElementById('content').innerHTML = `
            <div class="card">
                <div class="card-header"><i class="fas fa-cubes"></i> Наборы LEGO
                    <div class="float-end">
                        <button class="btn btn-sm btn-success me-2" onclick="showCreateSetModal()"><i class="fas fa-plus"></i> Создать</button>
                        <button class="btn btn-sm btn-primary" onclick="applyAdminSetsFilter()"><i class="fas fa-search"></i> Показать</button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row g-2 mb-3">
                        <div class="col-md-4"><label class="form-label">Тематика</label><select class="form-select" id="adminSetTheme">${themeOpts}</select></div>
                        <div class="col-md-4"><label class="form-label">Поиск</label><input type="text" class="form-control" id="adminSetText" placeholder="Название или каталог"></div>
                    </div>
                    <p class="small text-muted" id="adminSetsCount"></p>
                    <div class="table-responsive"><table class="table table-bordered" id="adminSetsTable"><thead><tr><th>ID</th><th>Название</th><th>Каталог</th><th>Год</th><th>Цена</th><th>Деталей</th><th>Действия</th></tr></thead><tbody></tbody></table></div>
                </div>
            </div>`;
        await applyAdminSetsFilter();
    } catch (e) { showError(e.message); }
};

async function applyAdminSetsFilter() {
    const tbody = document.querySelector('#adminSetsTable tbody');
    const countEl = document.getElementById('adminSetsCount');
    if (!tbody) return;
    try {
        let sets = await apiRequest('/sets');
        const themeId = getVal('adminSetTheme');
        const text = (getVal('adminSetText') || '').toLowerCase();
        if (themeId) sets = sets.filter(s => String(s.theme_id) === themeId);
        if (text) sets = sets.filter(s =>
            (s.name || '').toLowerCase().includes(text)
            || (s.catalog_number || '').toLowerCase().includes(text)
        );
        let rows = '';
        for (const set of sets) {
            rows += `<tr><td>${set.id}</td><td>${escapeHtml(set.name)}</td><td>${escapeHtml(set.catalog_number)}</td><td>${set.year}</td><td>$${set.price}</td><td>${set.parts_count}</td>
                <td class="action-buttons"><button class="btn btn-sm btn-info" onclick="showSetContents(${set.id})"><i class="fas fa-eye"></i></button>
                <button class="btn btn-sm btn-warning" onclick="showEditSetModal(${set.id})"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-danger" onclick="deleteSet(${set.id})"><i class="fas fa-trash"></i></button></td></tr>`;
        }
        tbody.innerHTML = rows || '<tr><td colspan="7" class="text-center text-muted">Наборы не найдены</td></tr>';
        if (countEl) countEl.textContent = `Показано наборов: ${sets.length}`;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-danger">${escapeHtml(e.message)}</td></tr>`;
    }
}

async function showSetContents(setId) {
    try {
        const [contents, products] = await Promise.all([
            apiRequest(`/sets/${setId}/contents`),
            apiRequest('/products'),
        ]);
        const productOpts = buildSelectOptions(products, 'id', 'наименование', '— выберите изделие —');
        let rows = '';
        for (const item of contents) {
            const sku = item.sku ? ` <code>${escapeHtml(item.sku)}</code>` : '';
            const actions = item.item_type === 'Изделие'
                ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteSetProductItem(${setId}, ${item.item_id})"><i class="fas fa-trash"></i></button>`
                : '';
            rows += `<tr><td>${escapeHtml(item.item_type)}</td><td>${escapeHtml(item.item_name)}${sku}</td><td>${item.quantity}</td><td>${actions}</td></tr>`;
        }
        const body = `
            <div class="table-responsive mb-3">
                <table class="table table-sm table-bordered">
                    <thead><tr><th>Тип</th><th>Наименование</th><th>Количество</th><th></th></tr></thead>
                    <tbody>${rows || '<tr><td colspan="4" class="text-center text-muted">Состав пуст</td></tr>'}</tbody>
                </table>
            </div>
            <div class="row g-2 align-items-end">
                <div class="col-md-8"><label class="form-label">Изделие</label><select class="form-select" id="setContentProductId">${productOpts}</select></div>
                <div class="col-md-2"><label class="form-label">Кол-во</label><input type="number" class="form-control" id="setContentQty" min="1" value="1"></div>
                <div class="col-md-2"><button class="btn btn-success w-100" onclick="addSetProductItem(${setId})"><i class="fas fa-plus"></i></button></div>
            </div>`;
        showAdminDynamicModal('Состав набора', body);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function addSetProductItem(setId) {
    const productId = parseInt(getVal('setContentProductId'), 10);
    const quantity = parseInt(getVal('setContentQty'), 10);
    if (!productId || !quantity || quantity < 1) return showToast('Выберите изделие и количество', 'error');
    try {
        await apiRequest(`/sets/${setId}/contents`, 'POST', { product_id: productId, quantity });
        showToast('Состав обновлён');
        bootstrap.Modal.getInstance(document.querySelector('.modal.show'))?.hide();
        showSetContents(setId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteSetProductItem(setId, productId) {
    if (!confirm('Удалить изделие из состава набора?')) return;
    try {
        await apiRequest(`/sets/${setId}/contents/${productId}`, 'DELETE');
        showToast('Позиция удалена');
        bootstrap.Modal.getInstance(document.querySelector('.modal.show'))?.hide();
        showSetContents(setId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

loadParts = async function() {
    showLoading();
    try {
        await preloadAdminRefs();
        const typeOpts = buildSelectOptions(adminCache.partTypes, 'id', 'name', '— любой тип —');
        document.getElementById('content').innerHTML = `
            <div class="card">
                <div class="card-header"><i class="fas fa-microchip"></i> Детали LEGO
                    <div class="float-end">
                        <button class="btn btn-sm btn-success me-2" onclick="showCreatePartModal()"><i class="fas fa-plus"></i> Создать</button>
                        <button class="btn btn-sm btn-primary" onclick="applyAdminPartsFilter()"><i class="fas fa-search"></i> Показать</button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row g-2 mb-3">
                        <div class="col-md-4"><label class="form-label">Тип</label><select class="form-select" id="adminPartType">${typeOpts}</select></div>
                        <div class="col-md-4"><label class="form-label">Название</label><input type="text" class="form-control" id="adminPartText" placeholder="Часть названия"></div>
                    </div>
                    <p class="small text-muted" id="adminPartsCount"></p>
                    <div class="table-responsive"><table class="table table-bordered" id="adminPartsTable"><thead><tr><th>ID</th><th>Название</th><th>Тип</th><th>Действия</th></tr></thead><tbody></tbody></table></div>
                </div>
            </div>`;
        await applyAdminPartsFilter();
    } catch (e) { showError(e.message); }
};

async function applyAdminPartsFilter() {
    const tbody = document.querySelector('#adminPartsTable tbody');
    const countEl = document.getElementById('adminPartsCount');
    if (!tbody) return;
    try {
        const body = {};
        const typeId = getVal('adminPartType');
        const text = getVal('adminPartText');
        if (typeId) body.part_type_id = parseInt(typeId, 10);
        if (text) body.name_contains = text;
        let parts = Object.keys(body).length
            ? await apiRequest('/parts/filter', 'POST', body)
            : await apiRequest('/parts');
        let rows = '';
        for (const part of parts) {
            rows += `<tr><td>${part.id}</td><td>${escapeHtml(part.name)}</td><td>${escapeHtml(part.type_name || '—')}</td>
                <td class="action-buttons"><button class="btn btn-sm btn-warning" onclick="showEditPartModal(${part.id})"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-danger" onclick="deletePart(${part.id})"><i class="fas fa-trash"></i></button></td></tr>`;
        }
        tbody.innerHTML = rows || '<tr><td colspan="4" class="text-center text-muted">Детали не найдены</td></tr>';
        if (countEl) countEl.textContent = `Показано деталей: ${parts.length}`;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-danger">${escapeHtml(e.message)}</td></tr>`;
    }
};

loadEnumValuesAll = async function() {
    showLoading();
    try {
        const enums = await apiRequest('/enumerations');
        let html = `<div class="card"><div class="card-header"><i class="fas fa-tasks"></i> Значения перечислений<div class="float-end"><button class="btn btn-sm btn-primary" onclick="loadEnumValuesAll()"><i class="fas fa-sync-alt"></i> Обновить</button></div></div><div class="card-body">`;
        for (const e of enums) {
            const values = await apiRequest(`/enumerations/${e.id}/values`);
            html += `<div class="card mb-3"><div class="card-body"><h5>${escapeHtml(e.name)} (ID: ${e.id})</h5>
                <div class="d-flex flex-wrap gap-2 mb-2">
                    <button class="btn btn-sm btn-success" onclick="showAddEnumValueModal(${e.id})"><i class="fas fa-plus"></i> Добавить</button>
                    <button class="btn btn-sm btn-outline-primary" onclick="reorderEnumByCurrentRows(${e.id})"><i class="fas fa-sort"></i> Сохранить порядок</button>
                </div>
                <div class="table-responsive"><table class="table table-sm"><thead><tr><th>ID</th><th>Значение</th><th>Порядок</th><th>Действия</th></tr></thead><tbody>`;
            for (const v of values) {
                html += `<tr><td>${v.id}</td><td>${escapeHtml(v.value)}</td><td><input type="number" class="form-control form-control-sm enum-order-input" data-enum-id="${e.id}" data-value-id="${v.id}" value="${v.sort_order}" min="0"></td><td class="action-buttons"><button class="btn btn-sm btn-warning me-1" onclick="showEditEnumValueModal(${v.id}, ${e.id}, '${escapeHtml(v.value).replace(/'/g, '&#39;')}', ${v.sort_order})"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteEnumValue(${v.id})"><i class="fas fa-trash"></i></button></td></tr>`;
            }
            html += `</tbody></table></div></div></div>`;
        }
        html += `</div></div>`;
        document.getElementById('content').innerHTML = html;
    } catch (e) { showError(e.message); }
};

async function reorderEnumByCurrentRows(enumId) {
    const inputs = [...document.querySelectorAll(`.enum-order-input[data-enum-id="${enumId}"]`)];
    const ordered = inputs
        .map(el => ({ id: parseInt(el.dataset.valueId, 10), order: parseInt(el.value || '0', 10) }))
        .sort((a, b) => a.order - b.order)
        .map(x => x.id);
    if (!ordered.length) return showToast('Нет значений для сортировки', 'info');
    try {
        await apiRequest(`/enumerations/${enumId}/values/reorder`, 'PUT', { ordered_ids: ordered });
        showToast('Порядок значений сохранён');
        loadEnumValuesAll();
    } catch (e) { showToast(e.message, 'error'); }
}

showEnumValues = async function(enumId) {
    try {
        const values = await apiRequest(`/enumerations/${enumId}/values`);
        let body = '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>ID</th><th>Значение</th><th>Порядок</th></tr></thead><tbody>';
        for (const v of values) body += `<tr><td>${v.id}</td><td>${escapeHtml(v.value)}</td><td>${v.sort_order}</td></tr>`;
        body += '</tbody></table></div>';
        showAdminDynamicModal('Значения перечисления', body, `<button class="btn btn-primary" onclick="bootstrap.Modal.getInstance(this.closest('.modal')).hide(); loadEnumValuesAll();"><i class="fas fa-sort"></i> Изменить порядок</button>`);
    } catch (e) { showToast(e.message, 'error'); }
};

async function showHOOpsDetails(opId) {
    try {
        const d = await apiRequest(`/ho-operations/${opId}`);
        const [subjects, products, roles, params] = await Promise.all([
            apiRequest('/subjects'),
            apiRequest('/products'),
            apiRequest(`/ho-types/${d.тип_хо_id}/roles`),
            apiRequest(`/ho-types/${d.тип_хо_id}/parameters`),
        ]);
        let body = `<p><strong>Тип:</strong> ${escapeHtml(d.тип_название || '—')} · <strong>Номер:</strong> ${escapeHtml(d.номер_документа || '')} · <strong>Сумма:</strong> ${formatPrice(d.сумма)}</p>`;
        body += '<div class="row g-3"><div class="col-lg-4"><h6>Роли</h6>';
        for (const role of roles) {
            const assigned = (d.роли || []).find(r => r.роль === role.название);
            body += `<div class="border rounded p-2 mb-2"><label class="form-label small">${escapeHtml(role.название)}</label>
                <select class="form-select form-select-sm ho-role-select" data-role-id="${role.id}">
                    <option value="">— не назначен —</option>${subjects.map(s => `<option value="${s.id}"${String(assigned?.субъект_id || '') === String(s.id) ? ' selected' : ''}>${escapeHtml(s.наименование)}</option>`).join('')}
                </select></div>`;
        }
        body += '</div><div class="col-lg-4"><h6>Параметры операции</h6>';
        for (const param of params) {
            const cur = (d.параметры || []).find(p => p.обозначение === param.обозначение);
            body += `<div class="form-field mb-2"><label class="form-label small">${escapeHtml(param.полное_имя)}${param.обязательный ? ' *' : ''}</label><div id="hoParamWrap_${param.hoparam_id}"></div></div>`;
        }
        body += '</div><div class="col-lg-4"><h6>Добавить позицию</h6><div class="form-field mb-2"><label class="form-label small">Изделие</label><select class="form-select form-select-sm" id="hoItemProduct"><option value="">— выберите —</option>';
        for (const p of products) body += `<option value="${p.id}">${escapeHtml(p.наименование)}${p.артикул ? ' · ' + escapeHtml(p.артикул) : ''}</option>`;
        body += `</select></div><div class="form-field mb-2"><label class="form-label small">Количество</label><input type="number" class="form-control form-control-sm" id="hoItemQty" step="any" min="0"></div>
            <div class="form-field mb-2"><label class="form-label small">Цена</label><input type="number" class="form-control form-control-sm" id="hoItemPrice" step="any" min="0"></div>
            <button class="btn btn-sm btn-success" onclick="addHoItemAdmin(${opId})"><i class="fas fa-plus"></i> Добавить позицию</button></div></div>`;
        body += '<hr><h6>Текущие позиции</h6><ul class="mb-0">';
        for (const item of d.позиции || []) body += `<li>${escapeHtml(item.изделие || '—')} — ${item.количество} x ${formatPrice(item.цена)} = ${formatPrice(item.сумма)}</li>`;
        body += '</ul>';
        const modal = showAdminDynamicModal('Детали операции', body, `<button class="btn btn-primary" onclick="saveHoDetailsAdmin(${opId})"><i class="fas fa-save"></i> Сохранить роли и параметры</button>`);
        for (const param of params) {
            const cur = (d.параметры || []).find(p => p.обозначение === param.обозначение);
            const wrap = modal.querySelector(`#hoParamWrap_${param.hoparam_id}`);
            if (wrap) wrap.innerHTML = await buildParamValueControl(param, `hoParam_${param.hoparam_id}`, cur?.значение ?? '');
        }
    } catch (e) { showToast(e.message, 'error'); }
}

async function saveHoDetailsAdmin(opId) {
    try {
        const modal = document.querySelector('.modal.show');
        for (const sel of modal.querySelectorAll('.ho-role-select')) {
            if (sel.value) {
                await apiRequest(`/ho-operations/${opId}/actors`, 'PUT', {
                    роль_хо_id: parseInt(sel.dataset.roleId, 10),
                    субъект_хо_id: parseInt(sel.value, 10),
                });
            }
        }
        for (const el of modal.querySelectorAll('[id^="hoParam_"]')) {
            const hpId = parseInt(el.id.replace('hoParam_', ''), 10);
            const paramType = el.tagName === 'SELECT' ? 'ENUM' : (el.type === 'number' ? 'REAL' : (el.type === 'datetime-local' ? 'DATETIME' : 'STRING'));
            const value = normalizeAdminValueByType(el.id, paramType);
            if (value !== null) await apiRequest(`/ho-operations/${opId}/values`, 'POST', { параметр_хо_id: hpId, value });
        }
        showToast('Операция обновлена');
        bootstrap.Modal.getInstance(modal)?.hide();
        loadHOOps();
    } catch (e) { showToast(e.message, 'error'); }
}

async function addHoItemAdmin(opId) {
    if (!getVal('hoItemProduct') || !getVal('hoItemQty') || !getVal('hoItemPrice')) {
        return showToast('Выберите изделие, количество и цену', 'error');
    }
    try {
        await apiRequest(`/ho-operations/${opId}/items`, 'POST', {
            изделие_id: parseInt(getVal('hoItemProduct'), 10),
            количество: parseFloat(getVal('hoItemQty')),
            цена: parseFloat(getVal('hoItemPrice')),
        });
        showToast('Позиция добавлена');
        const modal = document.querySelector('.modal.show');
        bootstrap.Modal.getInstance(modal)?.hide();
        showHOOpsDetails(opId);
    } catch (e) { showToast(e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => {
    adminInitModals();
});
