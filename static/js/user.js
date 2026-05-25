/** Интерфейс пользователя — просмотр и фильтрация справочника */
let cacheThemes = [];
let cacheAgeCategories = [];
let cachePartTypes = [];
let cacheParameters = [];
/** Параметры, привязанные к выбранному классу изделия (для фильтра) */
let cacheClassParams = [];
let selectedClassId = null;
/** @type {Array<{param_code:string, operator:string, value?:any, min?:number, max?:number, _label?:string}>} */
let productParamFilters = [];

document.addEventListener('DOMContentLoaded', () => {
    initSidebarToggle();
    initGlobalSearch(onGlobalSearch);
    loadHome();
    preloadReferences();
});

async function preloadReferences() {
    try {
        [cacheThemes, cacheAgeCategories, cachePartTypes, cacheParameters] = await Promise.all([
            apiRequest('/themes'),
            apiRequest('/age-categories'),
            apiRequest('/part-types'),
            apiRequest('/parameters'),
        ]);
        await loadColorOptions();
        await loadCategoriesList();
    } catch (_) { /* справочники подгрузятся при открытии разделов */ }
}

async function onGlobalSearch(q) {
    const setsLink = document.querySelector('[data-page="sets"]');
    if (setsLink) setActiveNav(setsLink);
    await loadSets();
    const textEl = document.getElementById('fSetText');
    if (textEl) textEl.value = q || '';
    applySetsFilters();
}

function navigateUser(ev, fn) {
    if (ev?.preventDefault) ev.preventDefault();
    if (ev?.currentTarget) setActiveNav(ev.currentTarget);
    fn();
}

async function loadHome() {
    setActiveNav(document.querySelector('[data-page="home"]'));
    showLoading();
    try {
        const [sets, parts, themes] = await Promise.all([
            apiRequest('/sets'),
            apiRequest('/parts'),
            apiRequest('/themes'),
        ]);
        document.getElementById('content').innerHTML = `
            <div class="page-header">
                <h1>Справочник LEGO</h1>
                <p class="subtitle">Просмотр каталога наборов, деталей и классификатора. Используйте фильтры в разделах меню.</p>
            </div>
            <div class="catalog-grid mb-4">
                <div class="catalog-card"><h3><i class="fas fa-cubes text-primary"></i> ${sets.length}</h3><p class="meta">наборов в каталоге</p></div>
                <div class="catalog-card"><h3><i class="fas fa-microchip text-primary"></i> ${parts.length}</h3><p class="meta">деталей</p></div>
                <div class="catalog-card"><h3><i class="fas fa-tags text-primary"></i> ${themes.length}</h3><p class="meta">тематик</p></div>
            </div>
            ${entityInfoHtml('compare')}
            <div class="card-panel">
                <div class="card-panel-header">Быстрый доступ</div>
                <div class="card-panel-body d-flex flex-wrap gap-2">
                    <button class="btn-app btn-app-primary" onclick="navigateUser(null, loadSets)"><i class="fas fa-filter"></i> Наборы</button>
                    <button class="btn-app btn-app-outline" onclick="navigateUser(null, loadParts)"><i class="fas fa-microchip"></i> Детали</button>
                    <button class="btn-app btn-app-outline" onclick="navigateUser(null, loadClassifier)"><i class="fas fa-tree"></i> Классификатор</button>
                    <button class="btn-app btn-app-outline" onclick="navigateUser(null, loadProductsFilter)"><i class="fas fa-box"></i> Изделия (склад)</button>
                </div>
            </div>`;
    } catch (e) { showError(e.message); }
}

async function loadClassifier() {
    setActiveNav(document.querySelector('[data-page="classifier"]'));
    showLoading();
    try {
        const trees = await apiRequest('/categories/tree');
        window.selectTreeNode = (id, name) => {
            selectedClassId = id;
            const classEl = document.getElementById('fProdClass');
            if (classEl) classEl.value = String(id);
            showToast(`Выбран класс: ${name}. Используйте раздел «Изделия» для поиска.`, 'info');
        };
        let treeHtml = '';
        for (const root of trees) treeHtml += renderTreeReadonly(root, 0, true);
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Классификатор</h1><p class="subtitle">Иерархия категорий. Нажмите на узел, чтобы использовать его в фильтрах.</p></div>
            <div class="card-panel"><div class="card-panel-header"><i class="fas fa-tree"></i> Дерево</div>
            <div class="card-panel-body">${treeHtml || '<div class="empty-state">Нет данных</div>'}</div></div>`;
    } catch (e) { showError(e.message); }
}

function setsFilterHtml() {
    const themeOpts = buildSelectOptions(cacheThemes, 'id', 'name', '— любая тематика —');
    return `
        <div class="filter-panel">
            <div class="filter-title"><i class="fas fa-filter"></i> Фильтры наборов</div>
            <div class="filter-grid">
                <div class="form-field"><label class="form-label" for="fTheme">Тематика</label><select class="form-select" id="fTheme">${themeOpts}</select></div>
                <div class="form-field"><label class="form-label" for="fAge">Возраст ребёнка (лет)</label><input type="number" class="form-control" id="fAge" min="0" max="99" placeholder="Напр. 8"></div>
                <div class="form-field"><label class="form-label" for="fYearMin">Год выпуска от</label><input type="number" class="form-control" id="fYearMin" min="1950" placeholder="2010"></div>
                <div class="form-field"><label class="form-label" for="fYearMax">Год выпуска до</label><input type="number" class="form-control" id="fYearMax" min="1950" placeholder="2024"></div>
                <div class="form-field"><label class="form-label" for="fPriceMin">Цена от ($)</label><input type="number" class="form-control" id="fPriceMin" step="0.01" min="0"></div>
                <div class="form-field"><label class="form-label" for="fPriceMax">Цена до ($)</label><input type="number" class="form-control" id="fPriceMax" step="0.01" min="0"></div>
                <div class="form-field"><label class="form-label" for="fSetText">Поиск по названию</label><input type="text" class="form-control" id="fSetText" placeholder="Название или каталожный номер"></div>
            </div>
            <div class="filter-actions">
                <button type="button" class="btn-app btn-app-primary" onclick="applySetsFilters()"><i class="fas fa-search"></i> Применить</button>
                <button type="button" class="btn-app btn-app-secondary" onclick="resetSetsFilters()"><i class="fas fa-undo"></i> Сбросить</button>
            </div>
        </div>
        <div id="setsResults"></div>`;
}

function validateSetsFilters() {
    return validateFilterPanel(
        ['fAge', 'fYearMin', 'fYearMax', 'fPriceMin', 'fPriceMax'],
        [
            () => {
                const age = getVal('fAge');
                if (!age) return null;
                return V.age('fAge', 'Возраст');
            },
            () => {
                const yMin = getVal('fYearMin');
                const yMax = getVal('fYearMax');
                const errs = [];
                if (yMin) {
                    const e = V.year('fYearMin', 'Год от', { required: false });
                    if (e) errs.push(e);
                }
                if (yMax) {
                    const e = V.year('fYearMax', 'Год до', { required: false });
                    if (e) errs.push(e);
                }
                if (yMin && yMax && !errs.length && parseInt(yMin, 10) > parseInt(yMax, 10)) {
                    errs.push({ fieldId: 'fYearMax', message: 'Год «до» не может быть меньше года «от»' });
                }
                return errs;
            },
            () => V.rangeMinMax('fPriceMin', 'fPriceMax', ['Цена от', 'Цена до']),
        ]
    );
}

async function loadSets() {
    setActiveNav(document.querySelector('[data-page="sets"]'));
    showLoading();
    try {
        if (!cacheThemes.length) await preloadReferences();
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Наборы LEGO</h1><p class="subtitle">Фильтрация по тематике, возрасту, году и цене</p></div>
            ${setsFilterHtml()}`;
        await applySetsFilters();
    } catch (e) { showError(e.message); }
}

async function applySetsFilters() {
    if (!validateSetsFilters()) return;

    const themeSel = document.getElementById('fTheme');
    const themeName = themeSel?.selectedOptions[0]?.text;
    const age = document.getElementById('fAge')?.value;
    const clientFilters = {
        yearMin: document.getElementById('fYearMin')?.value,
        yearMax: document.getElementById('fYearMax')?.value,
        priceMin: document.getElementById('fPriceMin')?.value,
        priceMax: document.getElementById('fPriceMax')?.value,
        text: (document.getElementById('fSetText')?.value || '').toLowerCase(),
    };

    const resultsEl = document.getElementById('setsResults');
    if (resultsEl) resultsEl.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;

    try {
        let sets = [];
        if (themeSel?.value && themeName && themeName !== '— выберите —') {
            sets = await apiRequest(`/search/theme?theme=${encodeURIComponent(themeName)}`);
            sets = sets.map(s => ({
                id: null,
                name: s.set_name,
                catalog_number: s.catalog_number,
                year: s.year,
                price: s.price,
                parts_count: null,
                theme_name: s.theme_name,
            }));
        } else if (age) {
            const byAge = await apiRequest(`/search/age?age=${encodeURIComponent(age)}`);
            sets = byAge.map(s => ({
                name: s.set_name,
                catalog_number: s.catalog_number,
                year: null,
                price: s.price,
                parts_count: null,
                min_age: s.min_age,
                max_age: s.max_age,
            }));
        } else {
            sets = await apiRequest('/sets');
        }
        sets = filterSetsClient(clientFilters, sets);
        renderSetsResults(sets);
    } catch (e) {
        if (resultsEl) resultsEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

function filterSetsClient(filters, sets) {
    return sets.filter(s => {
        if (filters.text) {
            const hay = `${s.name || ''} ${s.catalog_number || ''}`.toLowerCase();
            if (!hay.includes(filters.text)) return false;
        }
        if (filters.yearMin && s.year != null && s.year < parseInt(filters.yearMin, 10)) return false;
        if (filters.yearMax && s.year != null && s.year > parseInt(filters.yearMax, 10)) return false;
        if (filters.priceMin && s.price != null && s.price < parseFloat(filters.priceMin)) return false;
        if (filters.priceMax && s.price != null && s.price > parseFloat(filters.priceMax)) return false;
        return true;
    });
}

function resetSetsFilters() {
    ['fTheme', 'fAge', 'fYearMin', 'fYearMax', 'fPriceMin', 'fPriceMax', 'fSetText'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    applySetsFilters();
}

function renderSetsResults(sets) {
    const el = document.getElementById('setsResults');
    if (!el) return;
    if (!sets.length) {
        el.innerHTML = `<div class="empty-state"><i class="fas fa-inbox d-block"></i><p>Ничего не найдено. Измените фильтры.</p></div>`;
        return;
    }
    let cards = `<p class="results-count">Найдено: <strong>${sets.length}</strong></p><div class="catalog-grid">`;
    for (const s of sets) {
        const id = s.id || '—';
        cards += `<div class="catalog-card">
            <h3>${escapeHtml(s.name)}</h3>
            <p class="meta">Каталог: <code>${escapeHtml(s.catalog_number || '—')}</code></p>
            <p class="meta">Год: ${s.year ?? '—'} · Деталей: ${s.parts_count ?? '—'}</p>
            ${s.theme_name ? `<p class="meta">Тематика: ${escapeHtml(s.theme_name)}</p>` : ''}
            <p class="price">${formatPrice(s.price)}</p>
            ${s.id ? `<button class="btn-app btn-app-sm btn-app-outline mt-2" onclick="showSetDetails(${s.id})"><i class="fas fa-eye"></i> Состав</button>` : ''}
        </div>`;
    }
    cards += `</div>`;
    el.innerHTML = cards;
}

async function showSetDetails(setId) {
    try {
        const contents = await apiRequest(`/sets/${setId}/contents`);
        let body = '<ul class="list-group">';
        for (const i of contents) {
            body += `<li class="list-group-item d-flex justify-content-between"><span>${escapeHtml(i.item_name)}</span><span class="badge bg-secondary">${i.quantity} шт.</span></li>`;
        }
        body += '</ul>';
        showDynamicModal('Состав набора', body);
    } catch (e) { showToast(e.message, 'error'); }
}

async function loadParts() {
    setActiveNav(document.querySelector('[data-page="parts"]'));
    showLoading();
    try {
        if (!cachePartTypes.length) await preloadReferences();
        try {
            const cleanup = await apiRequest('/parts/cleanup-anomalies', 'POST');
            if (cleanup.removed_count > 0) {
                showToast(`Удалены ошибочные записи: ${cleanup.removed_names.join(', ')}`, 'info');
            }
        } catch (_) { /* очистка необязательна */ }
        const partTypeOpts = buildSelectOptions(cachePartTypes, 'id', 'name', '— любой тип —');
        const colorOpts = buildColorSelectOptions(true);
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Детали LEGO</h1><p class="subtitle">Поиск конструктивных элементов для наборов — не путать с товарами в «Изделиях»</p></div>
            ${entityInfoHtml('part')}
            <div class="filter-panel">
                <div class="filter-title"><i class="fas fa-filter"></i> Простой поиск по полям детали</div>
                <div class="filter-grid">
                    <div class="form-field"><label class="form-label" for="fPartType">Тип детали</label><select class="form-select" id="fPartType">${partTypeOpts}</select></div>
                    <div class="form-field"><label class="form-label" for="fPartColor">Цвет</label><select class="form-select" id="fPartColor">${colorOpts}</select></div>
                    <div class="form-field"><label class="form-label" for="fPartText">Название содержит</label><input type="text" class="form-control" id="fPartText" placeholder="Часть названия"></div>
                </div>
                <div class="filter-actions">
                    <button type="button" class="btn-app btn-app-primary" onclick="applyPartsFilters()"><i class="fas fa-search"></i> Применить</button>
                    <button type="button" class="btn-app btn-app-secondary" onclick="resetPartsFilters()"><i class="fas fa-undo"></i> Сбросить</button>
                </div>
            </div>
            <div id="partsResults"></div>`;
        await applyPartsFilters();
    } catch (e) { showError(e.message); }
}

function resetPartsFilters() {
    ['fPartType', 'fPartColor', 'fPartText'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    ['fPartType', 'fPartColor', 'fPartText'].forEach(clearFieldError);
    applyPartsFilters();
}

async function applyPartsFilters() {
    const resultsEl = document.getElementById('partsResults');
    resultsEl.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    try {
        const body = {};
        const typeId = getVal('fPartType');
        const colorVal = getVal('fPartColor');
        const text = getVal('fPartText');
        if (typeId) body.part_type_id = parseInt(typeId, 10);
        if (colorVal) body.color = colorVal;
        if (text) body.name_contains = text;

        let parts;
        if (body.part_type_id && !body.color && !body.name_contains) {
            const selectedType = document.getElementById('fPartType')?.selectedOptions[0]?.text || '';
            const byType = await apiRequest(`/search/part-type?part_type=${encodeURIComponent(selectedType)}`);
            parts = byType.map(p => ({
                name: p.part_name,
                color: p.color,
                size: p.size,
                weight: p.weight,
                type_name: p.type_name,
            }));
        } else if (body.part_type_id || body.color || body.name_contains) {
            parts = await apiRequest('/parts/filter', 'POST', body);
        } else {
            parts = await apiRequest('/parts');
        }
        if (!parts.length) {
            resultsEl.innerHTML = `<div class="empty-state"><i class="fas fa-inbox d-block"></i><p>Детали не найдены</p></div>`;
            return;
        }
        let html = `<p class="results-count">Найдено: <strong>${parts.length}</strong> · элементы для наборов</p><div class="table-responsive card-panel"><table class="data-table"><thead><tr><th>Название</th><th>Цвет</th><th>Размер</th><th>Вес, г</th><th>Тип детали</th></tr></thead><tbody>`;
        for (const p of parts) {
            html += `<tr><td>${escapeHtml(p.name)}</td><td>${escapeHtml(p.color)}</td><td>${escapeHtml(p.size)}</td><td>${p.weight ?? '—'}</td><td>${escapeHtml(p.type_name || '—')}</td></tr>`;
        }
        html += `</tbody></table></div>`;
        resultsEl.innerHTML = html;
    } catch (e) {
        resultsEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function loadMinifigures() {
    setActiveNav(document.querySelector('[data-page="minifigures"]'));
    showLoading();
    try {
        const mfs = await apiRequest('/minifigures');
        const textFilter = `
            <div class="filter-panel mb-3">
                <div class="filter-grid"><div class="form-field"><label class="form-label" for="fMfText">Поиск</label><input type="text" class="form-control" id="fMfText" placeholder="Персонаж, серия, код" oninput="filterMinifiguresTable()"></div></div>
            </div>`;
        let rows = '';
        for (const mf of mfs) {
            rows += `<tr data-search="${escapeHtml(`${mf.name} ${mf.character} ${mf.series} ${mf.unique_code}`.toLowerCase())}">
                <td>${escapeHtml(mf.name)}</td><td>${escapeHtml(mf.character)}</td><td>${escapeHtml(mf.series)}</td><td><code>${escapeHtml(mf.unique_code)}</code></td></tr>`;
        }
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Мини-фигурки</h1><p class="subtitle">Каталог фигурок</p></div>
            ${textFilter}
            <div class="card-panel"><div class="card-panel-body table-responsive">
            <table class="data-table" id="mfTable"><thead><tr><th>Название</th><th>Персонаж</th><th>Серия</th><th>Код</th></tr></thead><tbody>${rows}</tbody></table>
            </div></div>`;
    } catch (e) { showError(e.message); }
}

function filterMinifiguresTable() {
    const q = (document.getElementById('fMfText')?.value || '').toLowerCase();
    document.querySelectorAll('#mfTable tbody tr').forEach(tr => {
        tr.style.display = !q || tr.dataset.search?.includes(q) ? '' : 'none';
    });
}

async function loadProductsFilter() {
    setActiveNav(document.querySelector('[data-page="products"]'));
    showLoading();
    try {
        const cats = REF_CACHE.categories || await loadCategoriesList();
        const classOpts = buildCategorySelectOptions(cats, '— выберите класс —');
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Изделия (склад)</h1><p class="subtitle">Товары с артикулом и настраиваемыми параметрами — для учёта и продажи</p></div>
            ${entityInfoHtml('product')}
            <div class="filter-panel">
                <div class="filter-title"><i class="fas fa-sliders-h"></i> Поиск по классу и параметрам из справочника</div>
                <div class="filter-grid">
                    <div class="form-field"><label class="form-label" for="fProdClass">Класс изделия *</label><select class="form-select" id="fProdClass" onchange="onUserProductClassChange()">${classOpts}</select>
                    <div class="form-hint">Обязательно для поиска. Узел из «Классификатора» подставится сюда. Параметры фильтра — только для выбранного класса.</div></div>
                </div>
                <div class="filter-condition-card" id="productParamFilterSection">
                    <div class="condition-title">Параметры изделия</div>
                    <p class="form-hint mb-2">Список параметров зависит от класса (не весь справочник). Добавьте условия — изделие должно соответствовать <strong>всем</strong> сразу.</p>
                    <div id="productFiltersList" class="product-filters-list mb-3"></div>
                    <div class="filter-builder-box">
                        <div class="filter-builder-title">Новое условие</div>
                        <div class="filter-grid">
                            <div class="form-field"><label class="form-label" for="fProdParam">Параметр</label><select class="form-select" id="fProdParam" onchange="onProductParamChange()"><option value="">— сначала выберите класс —</option></select></div>
                        </div>
                        <div id="fProdValueArea"></div>
                        <button type="button" class="btn-app btn-app-outline mt-2" onclick="addProductParamFilter()"><i class="fas fa-plus"></i> Добавить условие</button>
                    </div>
                </div>
                <div class="filter-actions">
                    <button type="button" class="btn-app btn-app-primary" onclick="applyProductsFilter()"><i class="fas fa-search"></i> Найти изделия</button>
                    <button type="button" class="btn-app btn-app-secondary" onclick="resetProductsFilter()"><i class="fas fa-undo"></i> Сбросить всё</button>
                </div>
            </div>
            <div id="productsResults"><div class="empty-state"><p>Выберите класс изделия и нажмите «Найти изделия».</p></div></div>`;
        const classEl = document.getElementById('fProdClass');
        if (classEl && selectedClassId) {
            classEl.value = String(selectedClassId);
            await onUserProductClassChange();
        } else {
            productParamFilters = [];
            renderProductFiltersList();
        }
    } catch (e) { showError(e.message); }
}

async function onUserProductClassChange() {
    const classId = getVal('fProdClass');
    const sel = document.getElementById('fProdParam');
    const section = document.getElementById('productParamFilterSection');
    productParamFilters = [];
    renderProductFiltersList();
    document.getElementById('fProdValueArea').innerHTML = '';

    if (!classId) {
        cacheClassParams = [];
        if (sel) sel.innerHTML = '<option value="">— сначала выберите класс —</option>';
        if (section) section.style.opacity = '0.5';
        return;
    }
    if (section) section.style.opacity = '1';
    try {
        cacheClassParams = await apiRequest(`/classes/${classId}/parameters`);
        let opts = '<option value="">— выберите параметр —</option>';
        for (const p of cacheClassParams) {
            opts += `<option value="${escapeHtml(p.обозначение)}" data-type="${p.тип_параметра}" data-enum="${p.перечисление_id || ''}">${escapeHtml(p.полное_имя)}${p.единица_измерения ? ' (' + escapeHtml(p.единица_измерения) + ')' : ''}</option>`;
        }
        if (sel) sel.innerHTML = opts;
        if (!cacheClassParams.length) {
            showToast('У этого класса нет привязанных параметров', 'info');
        }
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function getParamMetaByCode(code) {
    return cacheClassParams.find(p => p.обозначение === code)
        || cacheParameters.find(p => p.обозначение === code);
}

function formatProductFilterLabel(pf) {
    if (pf._label) return pf._label;
    const meta = getParamMetaByCode(pf.param_code);
    const name = meta?.полное_имя || pf.param_code;
    if (pf.operator === 'between') return `${name}: от ${pf.min} до ${pf.max}`;
    if (pf.operator === '>') return `${name}: не меньше ${pf._displayValue ?? pf.value}`;
    if (pf.operator === '<') return `${name}: не больше ${pf._displayValue ?? pf.value}`;
    return `${name}: ${pf._displayValue ?? pf.value}`;
}

function renderProductFiltersList() {
    const el = document.getElementById('productFiltersList');
    if (!el) return;
    if (!productParamFilters.length) {
        el.innerHTML = '<p class="text-muted small mb-0">Условия по параметрам не заданы — будут показаны все изделия выбранного класса.</p>';
        return;
    }
    let html = '';
    productParamFilters.forEach((pf, idx) => {
        html += `<div class="product-filter-chip">
            <span><i class="fas fa-filter"></i> ${escapeHtml(formatProductFilterLabel(pf))}</span>
            <button type="button" class="btn-app btn-app-sm btn-app-danger" title="Удалить" onclick="removeProductParamFilter(${idx})"><i class="fas fa-times"></i></button>
        </div>`;
    });
    el.innerHTML = html;
}

function removeProductParamFilter(index) {
    productParamFilters.splice(index, 1);
    renderProductFiltersList();
}

async function describeEnumValue(enumId, valueId) {
    try {
        const values = await apiRequest(`/enumerations/${enumId}/values`);
        const v = values.find(x => x.id === valueId);
        return v?.value || String(valueId);
    } catch (_) {
        return String(valueId);
    }
}

async function buildPfFromBuilder() {
    const paramCode = getVal('fProdParam');
    if (!paramCode) return null;

    const opt = document.getElementById('fProdParam')?.selectedOptions[0];
    const type = opt?.dataset?.type;
    const enumId = opt?.dataset?.enum;
    const meta = getParamMetaByCode(paramCode);
    const pf = { param_code: paramCode };
    let displayValue = '';

    if (type === 'ENUM' && enumId) {
        const valId = parseInt(getVal('fProdEnumVal'), 10);
        pf.operator = '=';
        pf.value = valId;
        displayValue = await describeEnumValue(enumId, valId);
    } else if (type === 'REAL' || type === 'INTEGER') {
        const cond = getVal('fProdCond');
        if (cond === 'range') {
            pf.operator = 'between';
            pf.min = parseFloat(getVal('fProdMin'));
            pf.max = parseFloat(getVal('fProdMax'));
            displayValue = `${pf.min} … ${pf.max}`;
        } else {
            const num = parseFloat(getVal('fProdVal'));
            if (cond === 'gte') {
                pf.operator = '>';
                pf.value = type === 'INTEGER' ? num - 1 : num - 1e-6;
                displayValue = `≥ ${num}`;
            } else if (cond === 'lte') {
                pf.operator = '<';
                pf.value = type === 'INTEGER' ? num + 1 : num + 1e-6;
                displayValue = `≤ ${num}`;
            } else {
                pf.operator = '=';
                pf.value = num;
                displayValue = String(num);
            }
        }
    } else {
        pf.operator = '=';
        pf.value = getVal('fProdStrVal');
        displayValue = pf.value;
    }

    const unit = meta?.единица_измерения ? ` ${meta.единица_измерения}` : '';
    pf._displayValue = displayValue + unit;
    pf._label = formatProductFilterLabel(pf);
    return pf;
}

function validateCurrentProductCondition() {
    const paramCode = getVal('fProdParam');
    if (!paramCode) {
        setFieldError('fProdParam', 'Выберите параметр');
        showToast('Выберите параметр для условия', 'error');
        return false;
    }
    clearFieldError('fProdParam');

    const opt = document.getElementById('fProdParam')?.selectedOptions[0];
    const type = opt?.dataset?.type;
    const rules = [];

    if (type === 'ENUM') {
        rules.push(() => V.requiredSelect('fProdEnumVal', 'Значение'));
    } else if (type === 'REAL' || type === 'INTEGER') {
        const cond = getVal('fProdCond');
        if (cond === 'range') {
            rules.push(() => V.rangeMinMax('fProdMin', 'fProdMax', ['От', 'До']));
        } else {
            rules.push(() => V.nonNegative('fProdVal', 'Значение'));
        }
    } else {
        rules.push(() => V.text('fProdStrVal', 'Значение'));
    }

    return validateFilterPanel(['fProdEnumVal', 'fProdVal', 'fProdMin', 'fProdMax', 'fProdStrVal'], rules);
}

async function addProductParamFilter() {
    if (!validateCurrentProductCondition()) return;

    const pf = await buildPfFromBuilder();
    if (!pf) return;

    const duplicate = productParamFilters.some(
        f => f.param_code === pf.param_code && f.operator === pf.operator
            && f.value === pf.value && f.min === pf.min && f.max === pf.max
    );
    if (duplicate) {
        showToast('Такое условие уже добавлено', 'info');
        return;
    }

    productParamFilters.push(pf);
    renderProductFiltersList();

    document.getElementById('fProdParam').value = '';
    onProductParamChange();
    showToast('Условие добавлено', 'success');
}

async function onProductParamChange() {
    const sel = document.getElementById('fProdParam');
    const area = document.getElementById('fProdValueArea');
    if (!sel || !area) return;
    area.innerHTML = '';
    const code = sel.value;
    if (!code) return;

    const opt = sel.selectedOptions[0];
    const type = opt?.dataset?.type || 'STRING';
    const enumId = opt?.dataset?.enum;

    if (type === 'ENUM' && enumId) {
        const values = await apiRequest(`/enumerations/${enumId}/values`);
        let opts = '<option value="">— выберите значение —</option>';
        for (const v of values) opts += `<option value="${v.id}">${escapeHtml(v.value)}</option>`;
        area.innerHTML = `<div class="form-field mt-2"><label class="form-label" for="fProdEnumVal">Значение</label><select class="form-select" id="fProdEnumVal">${opts}</select></div>`;
    } else if (type === 'REAL' || type === 'INTEGER') {
        area.innerHTML = `
            <div class="form-field mt-2"><label class="form-label" for="fProdCond">Условие</label>
            <select class="form-select" id="fProdCond" onchange="onProductNumCondChange()">
                <option value="gte">Не меньше</option>
                <option value="lte">Не больше</option>
                <option value="eq">Равно</option>
                <option value="range">В диапазоне</option>
            </select></div>
            <div id="fProdNumFields" class="filter-grid mt-2"></div>`;
        onProductNumCondChange();
    } else {
        area.innerHTML = `<div class="form-field mt-2"><label class="form-label" for="fProdStrVal">Текст значения</label>
            <input type="text" class="form-control" id="fProdStrVal" placeholder="Точное совпадение"></div>`;
    }
}

function onProductNumCondChange() {
    const cond = getVal('fProdCond') || 'gte';
    const box = document.getElementById('fProdNumFields');
    if (!box) return;
    if (cond === 'range') {
        box.innerHTML = `
            <div class="form-field"><label class="form-label" for="fProdMin">От</label><input type="number" class="form-control" id="fProdMin" step="any" min="0"></div>
            <div class="form-field"><label class="form-label" for="fProdMax">До</label><input type="number" class="form-control" id="fProdMax" step="any" min="0"></div>`;
    } else {
        box.innerHTML = `<div class="form-field"><label class="form-label" for="fProdVal">Значение</label><input type="number" class="form-control" id="fProdVal" step="any" min="0"></div>`;
    }
}

function resetProductsFilter() {
    const classEl = document.getElementById('fProdClass');
    if (classEl) classEl.value = '';
    productParamFilters = [];
    cacheClassParams = [];
    renderProductFiltersList();
    onUserProductClassChange();
    clearFormErrors(document.getElementById('content'));
    document.getElementById('productsResults').innerHTML = '<div class="empty-state"><p>Выберите класс изделия и нажмите «Найти изделия».</p></div>';
}

function buildProductFilterPayload() {
    const body = {};
    const classId = getVal('fProdClass');
    if (classId) body.class_ids = [parseInt(classId, 10)];

    if (productParamFilters.length) {
        body.param_filters = productParamFilters.map(({ param_code, operator, value, min, max }) => {
            const pf = { param_code, operator };
            if (value !== undefined) pf.value = value;
            if (min !== undefined) pf.min = min;
            if (max !== undefined) pf.max = max;
            return pf;
        });
    }
    return body;
}

async function applyProductsFilter() {
    const classId = getVal('fProdClass');
    if (!classId) {
        setFieldError('fProdClass', 'Выберите класс изделия');
        showToast('Укажите класс — так проще ориентироваться в каталоге', 'info');
        return;
    }
    clearFieldError('fProdClass');

    const pendingCode = getVal('fProdParam');
    if (pendingCode && !validateCurrentProductCondition()) return;

    const resultsEl = document.getElementById('productsResults');
    resultsEl.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    try {
        const body = buildProductFilterPayload();
        let products = await apiRequest('/products/filter', 'POST', body);
        if (!products.length) {
            resultsEl.innerHTML = `<div class="empty-state"><p>Изделия не найдены. Измените условия.</p></div>`;
            return;
        }
        const condCount = productParamFilters.length;
        let html = `<p class="results-count">Найдено: <strong>${products.length}</strong>`;
        if (condCount) html += ` · условий по параметрам: <strong>${condCount}</strong> (все должны выполняться)`;
        html += `</p><div class="table-responsive card-panel"><table class="data-table"><thead><tr><th>Наименование</th><th>Артикул</th><th>Класс</th><th></th></tr></thead><tbody>`;
        for (const p of products) {
            html += `<tr><td>${escapeHtml(p.наименование)}</td><td><code>${escapeHtml(p.артикул || '—')}</code></td><td>${escapeHtml(p.класс_название || p.класс_id)}</td>
                <td><button type="button" class="btn-app btn-app-sm btn-app-outline" onclick="showProductParamsUser(${p.id})"><i class="fas fa-list"></i> Параметры</button></td></tr>`;
        }
        html += `</tbody></table></div>`;
        resultsEl.innerHTML = html;
    } catch (e) {
        resultsEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function showProductParamsUser(id) {
    try {
        const p = await apiRequest(`/products/${id}/values`);
        let body = '<table class="data-table"><thead><tr><th>Параметр</th><th>Значение</th></tr></thead><tbody>';
        for (const row of p) body += `<tr><td>${escapeHtml(row.полное_имя || row.обозначение)}</td><td>${row.значение ?? '—'}</td></tr>`;
        body += '</tbody></table>';
        showDynamicModal('Параметры изделия', body);
    } catch (e) { showToast(e.message, 'error'); }
}

async function loadOperationsView() {
    setActiveNav(document.querySelector('[data-page="operations"]'));
    showLoading();
    try {
        const hoTypes = await apiRequest('/ho-types');
        const typeOpts = buildSelectOptions(hoTypes, 'id', 'название');
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Хозяйственные операции</h1><p class="subtitle">Просмотр и фильтрация документов</p></div>
            <div class="filter-panel">
                <div class="filter-grid">
                    <div class="form-field"><label class="form-label" for="fHoType">Тип операции</label><select class="form-select" id="fHoType">${typeOpts}</select></div>
                    <div class="form-field"><label class="form-label" for="fHoDateFrom">Дата от</label><input type="date" class="form-control" id="fHoDateFrom"></div>
                    <div class="form-field"><label class="form-label" for="fHoDateTo">Дата до</label><input type="date" class="form-control" id="fHoDateTo"></div>
                    <div class="form-field"><label class="form-label" for="fHoSumMin">Сумма от ($)</label><input type="number" class="form-control" id="fHoSumMin" step="0.01" min="0"></div>
                    <div class="form-field"><label class="form-label" for="fHoSumMax">Сумма до ($)</label><input type="number" class="form-control" id="fHoSumMax" step="0.01" min="0"></div>
                </div>
                <div class="filter-actions">
                    <button class="btn-app btn-app-primary" onclick="applyHoFilter()"><i class="fas fa-search"></i> Применить</button>
                </div>
            </div>
            <div id="hoResults"></div>`;
        await applyHoFilter();
    } catch (e) { showError(e.message); }
}

async function applyHoFilter() {
    if (!validateFilterPanel(['fHoSumMin', 'fHoSumMax'], [
        () => V.rangeMinMax('fHoSumMin', 'fHoSumMax', ['Сумма от', 'Сумма до']),
    ])) return;

    const el = document.getElementById('hoResults');
    el.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    try {
        const body = {};
        const typeId = document.getElementById('fHoType')?.value;
        if (typeId) body.тип_хо_id = parseInt(typeId, 10);
        const df = document.getElementById('fHoDateFrom')?.value;
        const dt = document.getElementById('fHoDateTo')?.value;
        if (df) body.дата_от = new Date(df).toISOString();
        if (dt) body.дата_до = new Date(dt + 'T23:59:59').toISOString();
        const smin = document.getElementById('fHoSumMin')?.value;
        const smax = document.getElementById('fHoSumMax')?.value;
        if (smin) body.сумма_мин = parseFloat(smin);
        if (smax) body.сумма_макс = parseFloat(smax);

        const ops = Object.keys(body).length
            ? await apiRequest('/ho-operations/filter', 'POST', body)
            : await apiRequest('/ho-operations');

        if (!ops.length) {
            el.innerHTML = `<div class="empty-state"><p>Операции не найдены</p></div>`;
            return;
        }
        let html = `<p class="results-count">Найдено: <strong>${ops.length}</strong></p><div class="table-responsive card-panel"><table class="data-table"><thead><tr><th>Номер</th><th>Дата</th><th>Сумма</th><th></th></tr></thead><tbody>`;
        for (const o of ops) {
            const num = o.номер_документа || o.номер;
            html += `<tr><td><code>${escapeHtml(num)}</code></td><td>${formatDate(o.дата)}</td><td>${formatPrice(o.сумма)}</td>
                <td><button class="btn-app btn-app-sm btn-app-outline" onclick="showHoDetailsUser(${o.id})"><i class="fas fa-eye"></i></button></td></tr>`;
        }
        html += `</tbody></table></div>`;
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function showHoDetailsUser(opId) {
    try {
        const d = await apiRequest(`/ho-operations/${opId}`);
        let body = `<p><strong>Номер:</strong> ${escapeHtml(d.номер_документа)}</p><p><strong>Сумма:</strong> ${formatPrice(d.сумма)}</p>`;
        body += '<h6>Роли</h6><ul>';
        for (const r of d.роли || []) body += `<li>${escapeHtml(r.роль)}: ${escapeHtml(r.субъект || '—')}</li>`;
        body += '</ul><h6>Позиции</h6><ul>';
        for (const i of d.позиции || []) body += `<li>${escapeHtml(i.изделие)} — ${i.количество} × ${formatPrice(i.цена)}</li>`;
        body += '</ul>';
        showDynamicModal('Операция', body);
    } catch (e) { showToast(e.message, 'error'); }
}

function showDynamicModal(title, bodyHtml) {
    const modal = document.createElement('div');
    modal.className = 'modal fade modal-app';
    modal.innerHTML = `<div class="modal-dialog modal-lg"><div class="modal-content">
        <div class="modal-header"><h5 class="modal-title">${escapeHtml(title)}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-footer"><button class="btn-app btn-app-secondary" data-bs-dismiss="modal">Закрыть</button></div>
    </div></div>`;
    document.body.appendChild(modal);
    const inst = new bootstrap.Modal(modal);
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
    inst.show();
}
