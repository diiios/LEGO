/** Справочники и подстановка выпадающих списков в формах */

const REF_CACHE = {
    colors: null,
    categories: null,
    enumerations: null,
};

async function loadEnumerationsList() {
    if (REF_CACHE.enumerations) return REF_CACHE.enumerations;
    REF_CACHE.enumerations = await apiRequest('/enumerations');
    return REF_CACHE.enumerations;
}

async function loadColorOptions() {
    if (REF_CACHE.colors) return REF_CACHE.colors;
    const enums = await loadEnumerationsList();
    const colorEnum = enums.find(e => e.name === 'Цвет') || enums.find(e => e.name === 'Цвет детали');
    if (!colorEnum) {
        REF_CACHE.colors = [];
        return REF_CACHE.colors;
    }
    const values = await apiRequest(`/enumerations/${colorEnum.id}/values`);
    REF_CACHE.colors = values.map(v => ({ id: v.id, name: v.value }));
    return REF_CACHE.colors;
}

async function loadCategoriesList() {
    if (REF_CACHE.categories) return REF_CACHE.categories;
    REF_CACHE.categories = await apiRequest('/categories');
    return REF_CACHE.categories;
}

function buildColorSelectOptions(includeEmpty = true) {
    const colors = REF_CACHE.colors || [];
    let html = includeEmpty ? '<option value="">— любой цвет —</option>' : '<option value="">— выберите цвет —</option>';
    for (const c of colors) {
        html += `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`;
    }
    return html;
}

function buildCategorySelectOptions(categories, placeholder = '— без родителя —', excludeId = null) {
    let html = `<option value="">${placeholder}</option>`;
    for (const c of categories) {
        if (excludeId != null && c.id === excludeId) continue;
        html += `<option value="${c.id}">${escapeHtml(c.name)} (${c.node_type}, ID: ${c.id})</option>`;
    }
    return html;
}

function buildHoTypeSelectOptions(types, placeholder = '— корневой тип —', excludeId = null) {
    let html = `<option value="">${placeholder}</option>`;
    for (const t of types) {
        if (excludeId != null && t.id === excludeId) continue;
        const parent = t.родительский_id ? `, родитель: ${t.родительский_id}` : '';
        html += `<option value="${t.id}">${escapeHtml(t.название)} (ID: ${t.id}${parent})</option>`;
    }
    return html;
}

function buildEnumerationSelectOptions(enums, placeholder = '— не используется —') {
    let html = `<option value="">${placeholder}</option>`;
    for (const e of enums) {
        html += `<option value="${e.id}">${escapeHtml(e.name)}${e.description ? ' — ' + escapeHtml(e.description) : ''}</option>`;
    }
    return html;
}

async function ensureRefData() {
    await Promise.all([loadColorOptions(), loadCategoriesList(), loadEnumerationsList()]);
}

async function replaceWithSelect(fieldId, optionsHtml, className = 'form-select') {
    const el = document.getElementById(fieldId);
    if (!el) return;
    const val = el.value;
    const wrap = getFieldWrap(el);
    const label = wrap?.querySelector('.form-label')?.textContent || '';
    el.outerHTML = `<select class="${className}" id="${fieldId}">${optionsHtml}</select>`;
    const newEl = document.getElementById(fieldId);
    if (newEl && val) newEl.value = val;
}

async function setupColorSelect(fieldId, required = true) {
    await loadColorOptions();
    const ph = required ? '— выберите цвет —' : '— любой цвет —';
    await replaceWithSelect(fieldId, buildColorSelectOptions(!required));
}

async function setupCategoryParentSelect(fieldId, excludeId = null) {
    const cats = await loadCategoriesList();
    await replaceWithSelect(fieldId, buildCategorySelectOptions(cats, '— корневой уровень —', excludeId));
}

async function setupHoTypeParentSelect(fieldId, hoTypes, excludeId = null) {
    await replaceWithSelect(fieldId, buildHoTypeSelectOptions(hoTypes, '— корневой тип (без родителя) —', excludeId));
}

async function setupClassSelect(fieldId, placeholder = '— выберите класс —') {
    const cats = await loadCategoriesList();
    await replaceWithSelect(fieldId, buildCategorySelectOptions(cats, placeholder));
}

async function setupEnumerationSelect(fieldId) {
    const enums = await loadEnumerationsList();
    await replaceWithSelect(fieldId, buildEnumerationSelectOptions(enums, '— не привязано (только для типа «Перечисление») —'));
}

function bindLiveValidation(fieldId, validatorFn) {
    const el = document.getElementById(fieldId);
    if (!el || el.dataset.valBound) return;
    el.dataset.valBound = '1';
    const run = () => {
        clearFieldError(fieldId);
        const err = validatorFn();
        if (err) setFieldError(fieldId, err.message);
    };
    el.addEventListener('blur', run);
    el.addEventListener('input', () => {
        if (el.classList.contains('field-invalid')) run();
    });
}

function bindParamTypeEnumToggle(typeFieldId, enumFieldId) {
    const typeEl = document.getElementById(typeFieldId);
    const enumWrap = document.getElementById(enumFieldId)?.closest('.form-field');
    if (!typeEl || !enumWrap) return;
    const sync = () => {
        const isEnum = typeEl.value === 'ENUM';
        enumWrap.style.display = isEnum ? '' : 'none';
        if (!isEnum) clearFieldError(enumFieldId);
    };
    typeEl.addEventListener('change', sync);
    sync();
}
