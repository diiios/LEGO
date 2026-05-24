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

function validatePartForm(p) {
    const rules = [
        () => V.text(`${p}Name`, 'Название'),
        () => V.requiredSelect(`${p}Color`, 'Цвет'),
        () => V.text(`${p}Size`, 'Размер'),
        () => V.nonNegative(`${p}Weight`, 'Вес'),
        () => {
            const err = V.nonNegative(`${p}Weight`, 'Вес');
            if (err) return err;
            const w = parseFloat(getVal(`${p}Weight`));
            if (w > 500) return { fieldId: `${p}Weight`, message: 'Вес детали: не более 500 г (элемент LEGO)' };
            return null;
        },
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
    await setupColorSelect('partColor');
    await fillPartTypeSelect('part');
    ['partName', 'partColor', 'partSize', 'partWeight', 'partTypeId'].forEach(clearFieldError);
    document.getElementById('partName').value = '';
    document.getElementById('partColor').value = '';
    document.getElementById('partSize').value = '';
    document.getElementById('partWeight').value = '';
    document.getElementById('partTypeId').value = '';
    openModal('createPartModal');
}

async function showCreateProductModal() {
    await setupClassSelect('productClassId');
    ['productName', 'productArticle', 'productClassId'].forEach(clearFieldError);
    document.getElementById('productName').value = '';
    document.getElementById('productArticle').value = '';
    document.getElementById('productClassId').value = '';
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
        await setupColorSelect('editPartColor');
        await fillPartTypeSelect('editPart');
        document.getElementById('editPartId').value = p.id;
        document.getElementById('editPartName').value = p.name;
        document.getElementById('editPartColor').value = p.color;
        document.getElementById('editPartSize').value = p.size;
        document.getElementById('editPartWeight').value = p.weight;
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
        name: getVal('partName'), color: getVal('partColor'), size: getVal('partSize'),
        weight: parseFloat(getVal('partWeight')), part_type_id: parseInt(getVal('partTypeId'), 10),
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
        name: getVal('editPartName'), color: getVal('editPartColor'), size: getVal('editPartSize'),
        weight: parseFloat(getVal('editPartWeight')), part_type_id: parseInt(getVal('editPartTypeId'), 10),
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
    const data = {
        класс_id: parseInt(getVal('productClassId'), 10),
        наименование: getVal('productName'),
        артикул: getVal('productArticle') || null,
    };
    try {
        await apiRequest('/products', 'POST', data);
        showToast('Изделие создано');
        closeModal('createProductModal');
        loadProducts();
    } catch (e) { showToast(e.message, 'error'); }
}

async function updateProduct() {
    if (!validateProductForm('editProduct')) return;
    const id = document.getElementById('editProductId').value;
    const data = {
        класс_id: parseInt(getVal('editProductClassId'), 10),
        наименование: getVal('editProductName'),
        артикул: getVal('editProductArticle') || null,
    };
    try {
        await apiRequest(`/products/${id}`, 'PUT', data);
        showToast('Изделие обновлено');
        closeModal('editProductModal');
        loadProducts();
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

// Таблицы: кнопки редактирования
const _loadParts = loadParts;
loadParts = async function() {
    await _loadParts();
    const tbody = document.querySelector('#content table tbody');
    if (!tbody) return;
    tbody.querySelectorAll('tr').forEach((tr, i) => {
        const btnCell = tr.querySelector('.action-buttons');
        if (!btnCell || btnCell.querySelector('.btn-warning')) return;
        const id = tr.cells[0]?.textContent;
        if (!id) return;
        const editBtn = `<button type="button" class="btn btn-sm btn-warning me-1" onclick="showEditPartModal(${id})" title="Изменить"><i class="fas fa-edit"></i></button>`;
        btnCell.innerHTML = editBtn + btnCell.innerHTML;
    });
};

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

const _loadProducts = loadProducts;
loadProducts = async function() {
    await _loadProducts();
    document.querySelectorAll('#content table tbody tr').forEach(tr => {
        const btnCell = tr.querySelector('.action-buttons');
        if (!btnCell || btnCell.querySelector('.btn-warning')) return;
        const id = tr.cells[0]?.textContent;
        const editBtn = `<button type="button" class="btn btn-sm btn-warning me-1" onclick="showEditProductModal(${id})" title="Изменить"><i class="fas fa-edit"></i></button>`;
        btnCell.innerHTML = editBtn + btnCell.innerHTML;
    });
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

document.addEventListener('DOMContentLoaded', () => {
    adminInitModals();
});
