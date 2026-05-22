/** Интерфейс пользователя — просмотр и фильтрация справочника */
let cacheThemes = [];
let cacheAgeCategories = [];
let cachePartTypes = [];
let cacheParameters = [];
let selectedClassId = null;

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
            <div class="card-panel">
                <div class="card-panel-header">Быстрый доступ</div>
                <div class="card-panel-body d-flex flex-wrap gap-2">
                    <button class="btn-app btn-app-primary" onclick="navigateUser(null, loadSets)"><i class="fas fa-filter"></i> Наборы с фильтрами</button>
                    <button class="btn-app btn-app-outline" onclick="navigateUser(null, loadClassifier)"><i class="fas fa-tree"></i> Классификатор</button>
                    <button class="btn-app btn-app-outline" onclick="navigateUser(null, loadProductsFilter)"><i class="fas fa-box"></i> Изделия по параметрам</button>
                </div>
            </div>`;
    } catch (e) { showError(e.message); }
}

async function loadClassifier() {
    setActiveNav(document.querySelector('[data-page="classifier"]'));
    showLoading();
    try {
        const trees = await apiRequest('/categories/tree?include_products=true');
        window.selectTreeNode = (id, name) => {
            selectedClassId = id;
            showToast(`Выбран класс: ${name}. Перейдите в «Наборы» или «Изделия» для фильтрации.`, 'info');
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
    const themeOpts = buildSelectOptions(cacheThemes, 'id', 'name');
    const ageOpts = buildSelectOptions(cacheAgeCategories, 'id', 'name');
    return `
        <div class="filter-panel">
            <div class="filter-title"><i class="fas fa-filter"></i> Фильтры наборов</div>
            <div class="filter-grid">
                <div><label>Тематика</label><select id="fTheme">${themeOpts}</select></div>
                <div><label>Возраст (лет)</label><input type="number" id="fAge" min="0" max="99" placeholder="Напр. 8"></div>
                <div><label>Год от</label><input type="number" id="fYearMin" placeholder="2010"></div>
                <div><label>Год до</label><input type="number" id="fYearMax" placeholder="2024"></div>
                <div><label>Цена от ($)</label><input type="number" id="fPriceMin" step="0.01"></div>
                <div><label>Цена до ($)</label><input type="number" id="fPriceMax" step="0.01"></div>
                <div><label>Поиск по названию</label><input type="text" id="fSetText" placeholder="Название или каталог"></div>
            </div>
            <div class="filter-actions">
                <button class="btn-app btn-app-primary" onclick="applySetsFilters()"><i class="fas fa-search"></i> Применить</button>
                <button class="btn-app btn-app-secondary" onclick="resetSetsFilters()"><i class="fas fa-undo"></i> Сбросить</button>
            </div>
        </div>
        <div id="setsResults"></div>`;
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
        const partTypeOpts = buildSelectOptions(cachePartTypes, 'id', 'name');
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Детали</h1><p class="subtitle">Поиск по типу, цвету и названию</p></div>
            <div class="filter-panel">
                <div class="filter-title"><i class="fas fa-filter"></i> Фильтры</div>
                <div class="filter-grid">
                    <div><label>Тип детали</label><select id="fPartType">${partTypeOpts}</select></div>
                    <div><label>Цвет</label><input type="text" id="fPartColor" placeholder="Красный"></div>
                    <div><label>Поиск</label><input type="text" id="fPartText" placeholder="Название"></div>
                </div>
                <div class="filter-actions">
                    <button class="btn-app btn-app-primary" onclick="applyPartsFilters()"><i class="fas fa-search"></i> Применить</button>
                    <button class="btn-app btn-app-secondary" onclick="document.getElementById('fPartType').value='';document.getElementById('fPartColor').value='';document.getElementById('fPartText').value='';applyPartsFilters();"><i class="fas fa-undo"></i> Сбросить</button>
                </div>
            </div>
            <div id="partsResults"></div>`;
        await applyPartsFilters();
    } catch (e) { showError(e.message); }
}

async function applyPartsFilters() {
    const resultsEl = document.getElementById('partsResults');
    resultsEl.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    try {
        const typeSel = document.getElementById('fPartType');
        const typeName = typeSel?.selectedOptions[0]?.text;
        let parts;
        if (typeSel?.value && typeName !== '— выберите —') {
            parts = await apiRequest(`/search/part-type?part_type=${encodeURIComponent(typeName)}`);
            parts = parts.map(p => ({
                id: null,
                name: p.part_name,
                color: p.color,
                size: p.size,
                weight: p.weight,
                type_name: p.type_name,
            }));
        } else {
            parts = await apiRequest('/parts');
        }
        const color = (document.getElementById('fPartColor')?.value || '').toLowerCase();
        const text = (document.getElementById('fPartText')?.value || '').toLowerCase();
        parts = parts.filter(p => {
            if (color && !(p.color || '').toLowerCase().includes(color)) return false;
            if (text && !(p.name || '').toLowerCase().includes(text)) return false;
            return true;
        });
        if (!parts.length) {
            resultsEl.innerHTML = `<div class="empty-state"><i class="fas fa-inbox d-block"></i><p>Детали не найдены</p></div>`;
            return;
        }
        let html = `<p class="results-count">Найдено: <strong>${parts.length}</strong></p><div class="table-responsive card-panel"><table class="data-table"><thead><tr><th>Название</th><th>Цвет</th><th>Размер</th><th>Вес</th><th>Тип</th></tr></thead><tbody>`;
        for (const p of parts) {
            html += `<tr><td>${escapeHtml(p.name)}</td><td>${escapeHtml(p.color)}</td><td>${escapeHtml(p.size)}</td><td>${p.weight ?? '—'}</td><td>${escapeHtml(p.type_name || p.part_type_id || '—')}</td></tr>`;
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
                <div class="filter-grid"><div><label>Поиск</label><input type="text" id="fMfText" placeholder="Персонаж, серия, код" oninput="filterMinifiguresTable()"></div></div>
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
        if (!cacheParameters.length) await preloadReferences();
        const paramOpts = cacheParameters.map(p =>
            `<option value="${escapeHtml(p.обозначение)}">${escapeHtml(p.полное_имя)} (${p.тип_параметра})</option>`
        ).join('');
        document.getElementById('content').innerHTML = `
            <div class="page-header"><h1>Изделия</h1><p class="subtitle">Фильтрация по классу и параметрам</p></div>
            <div class="filter-panel">
                <div class="filter-title"><i class="fas fa-sliders-h"></i> Параметры фильтра</div>
                <div class="filter-grid">
                    <div><label>ID класса (из дерева)</label><input type="number" id="fProdClass" value="${selectedClassId || ''}" placeholder="ID узла классификатора"></div>
                    <div><label>Параметр</label><select id="fProdParam"><option value="">—</option>${paramOpts}</select></div>
                    <div><label>Оператор</label><select id="fProdOp"><option value="=">=</option><option value=">">&gt;</option><option value="<">&lt;</option><option value="between">диапазон</option></select></div>
                    <div><label>Значение</label><input type="text" id="fProdVal" placeholder="Число или текст"></div>
                    <div><label>Мин (диапазон)</label><input type="number" id="fProdMin" step="any"></div>
                    <div><label>Макс (диапазон)</label><input type="number" id="fProdMax" step="any"></div>
                </div>
                <div class="filter-actions">
                    <button class="btn-app btn-app-primary" onclick="applyProductsFilter()"><i class="fas fa-search"></i> Найти</button>
                </div>
            </div>
            <div id="productsResults"></div>`;
    } catch (e) { showError(e.message); }
}

async function applyProductsFilter() {
    const resultsEl = document.getElementById('productsResults');
    resultsEl.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    try {
        const classId = document.getElementById('fProdClass')?.value;
        const paramCode = document.getElementById('fProdParam')?.value;
        const op = document.getElementById('fProdOp')?.value;
        const val = document.getElementById('fProdVal')?.value;
        const min = document.getElementById('fProdMin')?.value;
        const max = document.getElementById('fProdMax')?.value;

        const body = {};
        if (classId) body.class_ids = [parseInt(classId, 10)];
        if (paramCode) {
            const pf = { param_code: paramCode, operator: op };
            if (op === 'between') {
                pf.min = min ? parseFloat(min) : undefined;
                pf.max = max ? parseFloat(max) : undefined;
            } else if (val !== '') {
                const num = Number(val);
                pf.value = Number.isNaN(num) ? val : num;
            }
            body.param_filters = [pf];
        }

        let products;
        if (body.class_ids || body.param_filters) {
            products = await apiRequest('/products/filter', 'POST', body);
        } else {
            products = await apiRequest('/products');
        }
        if (!products.length) {
            resultsEl.innerHTML = `<div class="empty-state"><p>Изделия не найдены</p></div>`;
            return;
        }
        let html = `<p class="results-count">Найдено: <strong>${products.length}</strong></p><div class="table-responsive card-panel"><table class="data-table"><thead><tr><th>Наименование</th><th>Артикул</th><th>Класс</th><th></th></tr></thead><tbody>`;
        for (const p of products) {
            html += `<tr><td>${escapeHtml(p.наименование)}</td><td><code>${escapeHtml(p.артикул || '—')}</code></td><td>${escapeHtml(p.класс_название || p.класс_id)}</td>
                <td><button class="btn-app btn-app-sm btn-app-outline" onclick="showProductParamsUser(${p.id})"><i class="fas fa-list"></i></button></td></tr>`;
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
                    <div><label>Тип операции</label><select id="fHoType">${typeOpts}</select></div>
                    <div><label>Дата от</label><input type="date" id="fHoDateFrom"></div>
                    <div><label>Дата до</label><input type="date" id="fHoDateTo"></div>
                    <div><label>Сумма от</label><input type="number" id="fHoSumMin" step="0.01"></div>
                    <div><label>Сумма до</label><input type="number" id="fHoSumMax" step="0.01"></div>
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
