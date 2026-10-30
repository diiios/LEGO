/**
 * Задание 6. Маршрутная технология изготовления изделий.
 * Технологические маршруты (Изделие-Операция), нормы расхода и времени, FIND_TM, SUM_MR, TR_TO,
 * калькуляция себестоимости, типовые ТП (паттерн «Приспособленец»), справочники ГРЦ и инструмента.
 * Общий модуль для администратора (редактирование) и пользователя (просмотр и расчёты).
 * Использует вспомогательные функции bom.js (bomModal, bomNum, bomKindBadge, bomFieldError ...).
 */
const TM_READONLY = document.body.dataset.role !== 'admin';

let tmState = {
    refs: null, products: [], selectedId: null, tab: 'route', search: '', kind: '', qty: 1000,
    typicalId: null, pendingId: null,
};

const TM_TABS = [
    ['route', 'fa-route', 'Маршрут'],
    ['find', 'fa-sitemap', 'Полный маршрут (FIND_TM)'],
    ['materials', 'fa-boxes-stacked', 'Материалы (SUM_MR)'],
    ['labor', 'fa-users-gear', 'Трудовые ресурсы (TR_TO)'],
    ['cost', 'fa-coins', 'Себестоимость'],
];

function tmMoney(v) {
    return v == null ? '—' : Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function tmOpNo(n) { return String(n).padStart(3, '0'); }

function tmQuote(s) { return escapeHtml(s || '').replace(/'/g, "\\'"); }

async function tmLoadRefs(force = false) {
    if (force || !tmState.refs) tmState.refs = await apiRequest('/tm/references');
    tmState.products = await apiRequest('/tm/products');
    if (typeof bomState !== 'undefined' && !bomState.units.length) bomState.units = await apiRequest('/bom/units');
}

function tmOptions(list, selected, empty = '—', label = x => x.name) {
    return `<option value="">${escapeHtml(empty)}</option>` + (list || []).map(x =>
        `<option value="${x.id}" ${x.id === selected ? 'selected' : ''}>${escapeHtml(label(x))}</option>`).join('');
}

function tmVal(id) {
    const v = document.getElementById(id)?.value;
    return v === '' || v == null ? null : Number(v);
}

function tmNonNegative(id, label, required = false) {
    const raw = (document.getElementById(id)?.value || '').replace(',', '.').trim();
    if (!raw) { if (required) { bomFieldError(id, `${label}: обязательное поле`); return undefined; } return 0; }
    const v = Number(raw);
    if (!isFinite(v)) { bomFieldError(id, `${label}: введите число`); return undefined; }
    if (v < 0) { bomFieldError(id, `${label}: не может быть отрицательным`); return undefined; }
    return v;
}

function tmNavigate(fn) {
    if (typeof bomNavigate === 'function') bomNavigate(fn); else fn();
}

function tmOpenProduct(id, tab = 'route') {
    tmState.pendingId = id;
    tmState.tab = tab;
    tmNavigate(loadTmRoutes);
}

/* ================================== Технологические маршруты ================================== */
async function loadTmRoutes() {
    showLoading();
    try {
        await tmLoadRefs();
        const kinds = Object.keys(BOM_KIND_TITLES);
        document.getElementById('content').innerHTML = `
        <div class="page-header">
            <h1><i class="fas fa-route"></i> Технологические маршруты</h1>
            <p class="subtitle">${TM_READONLY
                ? 'Маршрутная технология изготовления изделий: операции, нормы расхода и времени, анализ технологичности и себестоимость'
                : 'Описание маршрутной технологии: операции, ГРЦ, профессии, нормы расхода материалов и времени, типовые ТП'}</p>
        </div>
        <div class="row g-3">
            <div class="col-xxl-3 col-lg-4">
                <div class="card-panel bom-list-panel">
                    <div class="card-panel-header"><span><i class="fas fa-list"></i> Справочник изделий</span><span class="text-muted small" id="tmListCount"></span></div>
                    <div class="card-panel-body">
                        <div class="d-flex gap-2 mb-2">
                            <input type="search" class="form-control form-control-sm" id="tmSearch" placeholder="Наименование или артикул" value="${escapeHtml(tmState.search)}">
                            <select class="form-select form-select-sm" id="tmKind" style="max-width:170px">
                                <option value="">Все типы</option>
                                ${kinds.map(k => `<option value="${k}" ${tmState.kind === k ? 'selected' : ''}>${BOM_KIND_TITLES[k]}</option>`).join('')}
                            </select>
                        </div>
                        <div class="bom-product-list" id="tmProductList"></div>
                    </div>
                </div>
            </div>
            <div class="col-xxl-9 col-lg-8"><div id="tmDetail"></div></div>
        </div>`;
        document.getElementById('tmSearch').addEventListener('input', e => { tmState.search = e.target.value; tmRenderList(); });
        document.getElementById('tmKind').addEventListener('change', e => { tmState.kind = e.target.value; tmRenderList(); });
        tmRenderList();
        const target = tmState.pendingId || tmState.selectedId
            || (tmState.products.find(p => p.артикул === 'SET-75257') || tmState.products[0] || {}).id;
        tmState.pendingId = null;
        if (target) await tmSelectProduct(target);
    } catch (e) { showError(e.message); }
}

function tmRenderList() {
    const el = document.getElementById('tmProductList');
    if (!el) return;
    const q = tmState.search.toLowerCase();
    const list = tmState.products.filter(p => (!tmState.kind || p.тип_изделия === tmState.kind)
        && (!q || `${p.наименование} ${p.артикул || ''}`.toLowerCase().includes(q)));
    document.getElementById('tmListCount').textContent = `${list.length} из ${tmState.products.length}`;
    if (!list.length) { el.innerHTML = `<div class="empty-state py-4"><i class="fas fa-search"></i><p>Ничего не найдено</p></div>`; return; }
    el.innerHTML = list.map(p => `
        <button class="bom-product-item ${p.id === tmState.selectedId ? 'active' : ''}" onclick="tmSelectProduct(${p.id})">
            <span class="bom-product-icon" style="color:${BOM_KIND_COLORS[p.тип_изделия] || '#616161'}"><i class="fas ${BOM_KIND_ICONS[p.тип_изделия] || 'fa-cube'}"></i></span>
            <span class="bom-product-text">
                <span class="bom-product-name">${escapeHtml(p.наименование)}</span>
                <span class="bom-product-meta">${escapeHtml(p.артикул || 'без артикула')} · ${BOM_KIND_TITLES[p.тип_изделия] || p.тип_изделия}</span>
            </span>
            <span class="bom-product-flags">
                ${p.закупка ? '<span class="badge tm-badge-buy" title="Позиция закупки">закупка</span>'
                    : p.операций ? `<span class="badge bg-light text-dark border" title="Операций в маршруте">${p.операций} оп.</span>`
                    : '<span class="badge bg-danger-subtle text-danger" title="Маршрут не описан">нет</span>'}
                ${p.типовых ? '<span class="badge tm-badge-typ" title="Используется типовой ТП">ТТП</span>' : ''}
            </span>
        </button>`).join('');
}

async function tmSelectProduct(id, tab) {
    tmState.selectedId = id;
    if (tab) tmState.tab = tab;
    tmRenderList();
    const box = document.getElementById('tmDetail');
    if (!box) return;
    box.innerHTML = `<div class="card-panel"><div class="loading-state"><div class="spinner"></div><p>Загрузка...</p></div></div>`;
    try {
        const r = await apiRequest(`/tm/products/${id}/route`);
        const p = r.product;
        const purchase = r.operations.length && r.operations.every(o => o.закупка);
        const noCalc = purchase || !r.operations.length;
        if (noCalc && tmState.tab !== 'route') tmState.tab = 'route';
        const actions = TM_READONLY ? '' : `
            <div class="bom-actions">
                ${p.тип_изделия !== 'МАТЕРИАЛ' && !purchase ? `<button class="btn btn-sm btn-success" onclick="tmShowOperationModal(${p.id}, 'ТЕХ')"><i class="fas fa-plus"></i> Операция</button>` : ''}
                ${!r.operations.length && ['МАТЕРИАЛ', 'КОМПЛЕКТУЮЩЕЕ'].includes(p.тип_изделия) ? `<button class="btn btn-sm btn-outline-info" onclick="tmShowOperationModal(${p.id}, 'ЗАКУПКА')"><i class="fas fa-cart-shopping"></i> Позиция закупки</button>` : ''}
                ${p.позиций_спецификации && r.operations.some(o => !o.закупка) ? `<button class="btn btn-sm btn-outline-primary" onclick="tmShowBuildModal(${p.id})" title="Компоненты спецификации (задание 5) становятся входными ресурсами операции"><i class="fas fa-wand-magic-sparkles"></i> Входные ресурсы по спецификации</button>` : ''}
            </div>`;
        box.innerHTML = `
        <div class="card-panel">
            <div class="bom-head">
                <div>
                    <div class="bom-title">${escapeHtml(p.наименование)}</div>
                    <div class="bom-subtitle">
                        <span><i class="fas fa-barcode"></i> ${escapeHtml(p.артикул || '—')}</span>
                        ${bomKindBadge(p.тип_изделия)}
                        <span><i class="fas fa-folder"></i> ${escapeHtml(p.класс || '—')}</span>
                        <span><i class="fas fa-ruler"></i> ЕИ: ${escapeHtml(p.ед_изм || '—')}</span>
                        <span><i class="fas fa-list-ol"></i> позиций спецификации: ${p.позиций_спецификации}</span>
                    </div>
                </div>
                ${actions}
            </div>
            ${r.used_by.length ? `<div class="bom-mods-line"><span class="text-muted">Входной ресурс для:</span>
                ${r.used_by.map(u => `<a href="#" class="bom-chip" onclick="event.preventDefault(); tmSelectProduct(${u.id}, 'route')"><i class="fas fa-arrow-right"></i> ${escapeHtml(u.наименование)}</a>`).join('')}</div>` : ''}
            <ul class="nav nav-tabs bom-tabs px-3">
                ${TM_TABS.map(([k, ic, t]) => `<li class="nav-item"><a href="#" class="nav-link ${tmState.tab === k ? 'active' : ''} ${noCalc && k !== 'route' ? 'disabled' : ''}" onclick="event.preventDefault(); tmSelectProduct(${p.id}, '${k}')"><i class="fas ${ic}"></i> ${t}</a></li>`).join('')}
            </ul>
            <div class="card-panel-body" id="tmTabBody"></div>
        </div>`;
        const body = document.getElementById('tmTabBody');
        if (tmState.tab === 'route') body.innerHTML = tmRouteHtml(r);
        else if (tmState.tab === 'find') body.innerHTML = await tmFindHtml(p);
        else { body.innerHTML = tmQtyFormHtml(); await tmRunCalc(); }
    } catch (e) { box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`; }
}

/* ----- Вкладка «Маршрут»: Изделия-Операции изделия ----- */
function tmRouteHtml(r) {
    const p = r.product;
    if (!r.operations.length) {
        const hint = ['МАТЕРИАЛ', 'КОМПЛЕКТУЮЩЕЕ'].includes(p.тип_изделия)
            ? 'Для покупного изделия создайте позицию закупки с ценой.'
            : 'Добавьте операции изготовления; результат каждой операции — изделие в новом состоянии.';
        return `<div class="empty-state py-4"><i class="fas fa-route"></i><p>Маршрут не описан. ${TM_READONLY ? '' : hint}</p></div>`;
    }
    let html = `<div class="tm-route">`;
    for (const o of r.operations) {
        if (o.закупка) {
            html += `<div class="tm-op tm-op-buy">
                <div class="tm-op-head">
                    <span class="tm-op-no"><i class="fas fa-cart-shopping"></i></span>
                    <div class="tm-op-title"><b>Позиция закупки</b> — изделие поступает от поставщика готовым
                        <div class="tm-op-meta"><span>Цена: <b>${tmMoney(o.цена)}</b> руб. за ${escapeHtml(o.ед_изм || 'ЕИ')}</span>${o.примечание ? `<span>${escapeHtml(o.примечание)}</span>` : ''}</div></div>
                    ${TM_READONLY ? '' : `<div class="tm-op-actions">
                        <button class="btn btn-sm btn-outline-primary" title="Изменить цену" onclick='tmShowOperationModal(${p.id}, "ЗАКУПКА", ${JSON.stringify(o).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button>
                        <button class="btn btn-sm btn-outline-danger" title="Удалить" onclick="tmDeleteOperation(${o.id})"><i class="fas fa-trash"></i></button></div>`}
                </div></div>`;
            continue;
        }
        const typ = !!o.типовой_тп_id;
        html += `<div class="tm-op">
            <div class="tm-op-head">
                <span class="tm-op-no">${tmOpNo(o.номер)}</span>
                <div class="tm-op-title"><b>${escapeHtml(o.наименование)}</b>
                    <span class="text-muted">· ${escapeHtml(o.класс_то || 'класс ТО не задан')}</span>
                    ${typ ? `<a href="#" class="tm-typ-chip" onclick="event.preventDefault(); tmOpenTypical(${o.типовой_тп_id})"><i class="fas fa-feather"></i> ${escapeHtml(o.типовой_тп)}</a>` : ''}
                    <div class="tm-op-meta">
                        ${typ ? `<span>Тпз = <b>${bomNum(o.тпз_итого, 3)}</b> мин</span><span>Тшт = <b>${bomNum(o.тшт_итого, 4)}</b> мин (по типовому ТП)</span>`
                              : `<span><i class="fas fa-industry"></i> ${escapeHtml(o.грц || 'ГРЦ —')}</span>
                                 <span><i class="fas fa-user-gear"></i> ${escapeHtml(o.профессия || 'профессия —')}${o.квалификация ? ', ' + escapeHtml(o.квалификация) : ''}</span>
                                 <span>Тпз = <b>${bomNum(o.тпз, 3)}</b> мин</span><span>Тшт = <b>${bomNum(o.тшт, 4)}</b> мин</span>`}
                    </div>
                </div>
                ${TM_READONLY ? '' : `<div class="tm-op-actions">
                    <button class="btn btn-sm btn-outline-success" title="Добавить входной ресурс" onclick="tmShowInputModal(${o.id}, ${p.id})"><i class="fas fa-right-to-bracket"></i></button>
                    <button class="btn btn-sm btn-outline-secondary" title="Назначить инструмент / оснастку" onclick="tmShowToolLinkModal(${o.id})"><i class="fas fa-screwdriver-wrench"></i></button>
                    <button class="btn btn-sm btn-outline-info" title="${typ ? 'Изменить параметры типового ТП' : 'Применить типовой ТП'}" onclick="tmShowApplyTypicalModal(${o.id}, ${o.типовой_тп_id || 'null'})"><i class="fas fa-feather"></i></button>
                    <button class="btn btn-sm btn-outline-primary" title="Изменить операцию" onclick='tmShowOperationModal(${p.id}, "ТЕХ", ${JSON.stringify({ ...o, inputs: [], типовые_операции: [], типовые_ресурсы: [], tools: [], параметры: [] }).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-outline-danger" title="Удалить операцию" onclick="tmDeleteOperation(${o.id})"><i class="fas fa-trash"></i></button></div>`}
            </div>`;
        if (typ) {
            html += `<div class="tm-sub"><div class="tm-sub-title"><i class="fas fa-feather"></i> Типовой ТП: значения параметров (внешнее состояние)
                    ${o.параметры.map(x => `<span class="tm-param">${escapeHtml(x.обозначение)} = <b>${bomNum(x.значение)}</b> ${escapeHtml(x.ед_изм || '')}</span>`).join('')}
                    ${TM_READONLY ? '' : `<button class="btn btn-link btn-sm p-0 ms-2" onclick="tmRemoveTypical(${o.id})">отвязать</button>`}</div>
                <table class="data-table tm-mini"><thead><tr><th>№</th><th>Типовая операция</th><th>ГРЦ</th><th>Профессия, разряд</th><th class="text-end">Тпз, мин</th><th class="text-end">Тшт, мин</th></tr></thead><tbody>
                ${o.типовые_операции.map(t => `<tr><td>${tmOpNo(t.номер)}</td><td>${escapeHtml(t.наименование)}</td><td>${escapeHtml(t.грц || '—')}</td><td>${escapeHtml(t.профессия || '—')}${t.квалификация ? ', ' + escapeHtml(t.квалификация) : ''}</td><td class="text-end">${bomNum(t.тпз, 3)}</td><td class="text-end">${bomNum(t.тшт, 5)}</td></tr>`).join('')}
                </tbody></table></div>`;
        }
        const inputs = [...o.inputs.map(i => ({ ...i, typ: false })),
            ...(o.типовые_ресурсы || []).map(i => ({ изделие_id: i.изделие_id, изделие: i.изделие, норма: i.норма, для_количества: 1, ед_изм: i.ед_изм, источник: 'ТИПОВОЙ_ТП', typ: true }))];
        if (inputs.length) {
            html += `<div class="tm-sub"><div class="tm-sub-title"><i class="fas fa-right-to-bracket"></i> Входные ресурсы (нормы расхода на операцию)</div>
                <table class="data-table tm-mini"><thead><tr><th>Входная изделие-операция</th><th class="text-end">Норма</th><th class="text-end">Для кол-ва</th><th>ЕИ</th><th class="text-end">На 1 шт.</th><th>Источник</th>${TM_READONLY ? '' : '<th></th>'}</tr></thead><tbody>
                ${inputs.map(i => `<tr><td><a href="#" onclick="event.preventDefault(); tmSelectProduct(${i.изделие_id}, 'route')">${escapeHtml(i.изделие)}</a>
                        <span class="bom-sku">${escapeHtml(i.после_операции ? 'после ' + i.после_операции : '')}</span></td>
                    <td class="text-end">${bomNum(i.норма)}</td><td class="text-end">${bomNum(i.для_количества)}</td><td>${escapeHtml(i.ед_изм || '—')}</td>
                    <td class="text-end fw-semibold">${bomNum(i.норма / i.для_количества)}</td>
                    <td>${tmSourceBadge(i.источник)}</td>
                    ${TM_READONLY ? '' : `<td class="actions">${i.typ ? '<span class="small text-muted">из ТТП</span>' : `
                        <button class="btn btn-sm btn-outline-primary" title="Изменить норму" onclick='tmShowInputEditModal(${JSON.stringify(i).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button>
                        <button class="btn btn-sm btn-outline-danger" title="Удалить" onclick="tmDeleteInput(${i.id})"><i class="fas fa-trash"></i></button>`}</td>`}</tr>`).join('')}
                </tbody></table></div>`;
        }
        if (o.tools.length) {
            html += `<div class="tm-sub"><div class="tm-sub-title"><i class="fas fa-screwdriver-wrench"></i> Инструмент и оснастка</div>
                <div class="d-flex flex-wrap gap-2">${o.tools.map(t => `<span class="tm-tool ${t.вид === 'ОСНАСТКА' ? 'tm-tool-fix' : ''}"><i class="fas ${t.вид === 'ОСНАСТКА' ? 'fa-cubes' : 'fa-screwdriver'}"></i>
                    ${escapeHtml(t.обозначение)} ${escapeHtml(t.наименование)}${t.количество > 1 ? ' × ' + t.количество : ''}
                    ${TM_READONLY ? '' : `<button class="btn-close btn-close-sm" title="Снять" onclick="tmDeleteToolLink(${t.id})"></button>`}</span>`).join('')}</div></div>`;
        }
        html += `</div>`;
    }
    return html + `</div>`;
}

function tmSourceBadge(s) {
    const m = { 'СПЕЦИФИКАЦИЯ': ['bg-primary', 'спецификация'], 'ТИПОВОЙ_ТП': ['tm-badge-typ', 'типовой ТП'], 'ВРУЧНУЮ': ['bg-secondary', 'вручную'] };
    const [c, t] = m[s] || ['bg-light text-dark', s];
    return `<span class="badge ${c}">${t}</span>`;
}

/* ----- Вкладка «Полный маршрут» (FIND_TM) ----- */
async function tmFindHtml(p) {
    const f = await apiRequest(`/tm/products/${p.id}/find`);
    if (!f.rows.length) return `<div class="empty-state py-4"><i class="fas fa-sitemap"></i><p>Маршрут не описан</p></div>`;
    const missing = f.rows.filter(r => r.вид === 'ТЕХ' && !r.типовой_тп && !r.грц);
    let html = `<div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
        <div class="text-muted small">Изделий-операций: <b>${f.строк}</b> · глубина: <b>${f.глубина}</b> ·
            материалы на 1 шт.: <b>${tmMoney(f.материалы_руб_на_ед)}</b> руб. · Тшт на 1 шт.: <b>${bomNum(f.труд_мин_на_ед, 3)}</b> мин</div>
        <div><button class="btn btn-sm btn-outline-secondary" onclick="tmTreeToggleAll(false)"><i class="fas fa-compress"></i> Свернуть</button>
        <button class="btn btn-sm btn-outline-secondary" onclick="tmTreeToggleAll(true)"><i class="fas fa-expand"></i> Развернуть</button></div>
    </div>
    ${missing.length ? `<div class="alert alert-warning py-2 small"><i class="fas fa-triangle-exclamation"></i> Анализ технологичности: у ${missing.length} операций не назначен ГРЦ — они не попадут в расчёт загрузки оборудования.</div>` : ''}
    <div class="table-responsive"><table class="data-table bom-tree-table tm-find-table"><thead><tr>
        <th>Изделие → операция</th><th>ГРЦ</th><th>Профессия, разряд</th><th class="text-end">Тпз</th><th class="text-end">Тшт</th><th class="text-end">Кол-во на 1 изд.</th><th>ЕИ</th></tr></thead><tbody>`;
    const keys = f.rows.map(r => r.путь.join('.') + ':' + r.операция_id);
    f.rows.forEach((r, idx) => {
        const key = keys[idx];
        const hasChildren = f.rows.some(x => x.родитель_операция_id === r.операция_id && x.путь.slice(0, -1).join('.') === r.путь.join('.'));
        const parentKey = r.родитель_операция_id ? r.путь.slice(0, -1).join('.') + ':' + r.родитель_операция_id : '';
        const buy = r.вид === 'ЗАКУПКА';
        html += `<tr data-key="${key}" data-parent="${parentKey}" data-level="${r.уровень}" class="${buy ? 'tm-row-buy' : ''}">
            <td style="padding-left:${0.6 + (r.уровень - 1) * 1.4}rem">
                ${hasChildren ? `<span class="bom-tree-toggle" onclick="tmTreeToggle(this)">▼</span>` : '<span class="bom-tree-leaf">•</span>'}
                <span class="bom-level">${r.уровень}</span>
                <a href="#" onclick="event.preventDefault(); tmSelectProduct(${r.изделие_id}, 'route')">${escapeHtml(r.изделие)}</a>
                → ${buy ? '<span class="badge tm-badge-buy">закупка</span> ' + tmMoney(r.цена) + ' руб.' : `<b title="${escapeHtml(r.класс_то || '')}">${tmOpNo(r.номер)}</b> ${escapeHtml(r.наименование)}`}
                ${r.типовой_тп ? `<span class="badge tm-badge-typ ms-1" title="${escapeHtml(r.типовой_тп)}">ТТП</span>` : ''}
            </td>
            <td title="${escapeHtml(r.грц || '')}">${escapeHtml(buy ? '—' : (r.типовой_тп ? 'по ТТП' : ((r.грц || '—').split(' ')[0])))}</td>
            <td>${escapeHtml(buy ? '—' : (r.типовой_тп ? 'по ТТП' : ((r.профессия || '—') + (r.квалификация ? ', ' + r.квалификация : ''))))}</td>
            <td class="text-end">${buy ? '' : bomNum(r.тпз, 2)}</td>
            <td class="text-end">${buy ? '' : bomNum(r.тшт_итого, 4)}</td>
            <td class="text-end fw-semibold">${bomNum(r.количество)}</td>
            <td>${escapeHtml(r.ед_изм || '—')}</td></tr>`;
    });
    return html + `</tbody></table></div>`;
}

function tmTreeToggle(el) {
    const row = el.closest('tr');
    const collapse = el.textContent === '▼';
    el.textContent = collapse ? '▶' : '▼';
    const rows = Array.from(document.querySelectorAll('.tm-find-table tbody tr'));
    const hide = new Set([row.dataset.key]);
    rows.forEach(tr => {
        if (hide.has(tr.dataset.parent)) {
            hide.add(tr.dataset.key);
            tr.style.display = collapse ? 'none' : '';
            const t = tr.querySelector('.bom-tree-toggle');
            if (t && !collapse) t.textContent = '▼';
        }
    });
}

function tmTreeToggleAll(expand) {
    document.querySelectorAll('.tm-find-table tbody tr').forEach(tr => {
        const t = tr.querySelector('.bom-tree-toggle');
        if (t) t.textContent = expand ? '▼' : '▶';
        tr.style.display = expand || tr.dataset.level === '1' ? '' : 'none';
    });
}

/* ----- Расчёты: SUM_MR, TR_TO, калькуляция ----- */
function tmQtyFormHtml() {
    const titles = { materials: 'Сводные нормы материальных ресурсов (SUM_MR)', labor: 'Потребность в трудовых ресурсах (TR_TO) и загрузка ГРЦ', cost: 'Калькуляция себестоимости' };
    return `<div class="bom-calc-form row g-2 align-items-end mb-3">
        <div class="col-sm-6"><div class="fw-semibold">${titles[tmState.tab]}</div><div class="small text-muted">Расчёт выполняется хранимыми функциями PostgreSQL на основе FIND_TM</div></div>
        <div class="col-sm-3 form-field"><label class="form-label" for="tmQty">Количество изделий *</label>
            <input type="number" class="form-control" id="tmQty" value="${tmState.qty}" min="1" step="1"></div>
        <div class="col-sm-3"><button class="btn btn-primary w-100" onclick="tmRunCalc()"><i class="fas fa-calculator"></i> Рассчитать</button></div>
    </div><div id="tmCalcResult"></div>`;
}

async function tmRunCalc() {
    const q = bomPositiveNumber('tmQty', 'Количество');
    if (q == null) return;
    tmState.qty = q;
    const out = document.getElementById('tmCalcResult');
    out.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    const id = tmState.selectedId;
    try {
        if (tmState.tab === 'materials') {
            const r = await apiRequest(`/tm/products/${id}/materials?quantity=${q}`);
            if (!r.items.length) { out.innerHTML = `<div class="empty-state py-4"><i class="fas fa-boxes-stacked"></i><p>В маршруте нет позиций закупки</p></div>`; return; }
            out.innerHTML = `<div class="table-responsive"><table class="data-table bom-calc-table"><thead><tr><th>Материальный ресурс</th><th>Тип</th><th class="text-end">Норма на 1 изделие</th><th class="text-end">Сводная норма</th><th>ЕИ</th><th class="text-end">Цена, руб.</th><th class="text-end">Стоимость, руб.</th><th class="text-end">Вхождений</th></tr></thead><tbody>
                ${r.items.map(i => `<tr><td><a href="#" onclick="event.preventDefault(); tmSelectProduct(${i.изделие_id}, 'route')">${escapeHtml(i.изделие)}</a><div class="small text-muted">${escapeHtml(i.артикул || '')}</div></td>
                    <td>${bomKindBadge(i.тип_изделия)}</td><td class="text-end">${bomNum(i.норма_на_единицу)}</td><td class="text-end fw-bold">${bomNum(i.количество, 3)}</td>
                    <td>${escapeHtml(i.ед_изм || '—')}</td><td class="text-end">${tmMoney(i.цена)}</td><td class="text-end">${tmMoney(i.стоимость)}</td><td class="text-end">${i.вхождений}</td></tr>`).join('')}
                </tbody><tfoot><tr><td colspan="6" class="text-end fw-bold">Итого материальные затраты:</td><td class="text-end fw-bold">${tmMoney(r.итого)}</td><td></td></tr></tfoot></table></div>`;
        } else if (tmState.tab === 'labor') {
            const r = await apiRequest(`/tm/products/${id}/labor?quantity=${q}`);
            out.innerHTML = `<div class="tm-sub-title mb-1"><i class="fas fa-users-gear"></i> Трудовые ресурсы по профессиям и квалификации</div>
                <div class="table-responsive"><table class="data-table bom-calc-table"><thead><tr><th>Профессия</th><th>Квалификация</th><th class="text-end">Операций</th><th class="text-end">Трудоёмкость, нормо-ч</th><th class="text-end">Ставка, руб/ч</th><th class="text-end">Оплата труда, руб.</th></tr></thead><tbody>
                ${r.items.map(i => `<tr><td>${escapeHtml(i.профессия)}</td><td>${escapeHtml(i.квалификация)}</td><td class="text-end">${i.операций}</td><td class="text-end fw-bold">${bomNum(i.трудоемкость_ч, 2)}</td><td class="text-end">${tmMoney(i.ставка)}</td><td class="text-end">${tmMoney(i.стоимость)}</td></tr>`).join('')}
                </tbody><tfoot><tr><td colspan="3" class="text-end fw-bold">Итого:</td><td class="text-end fw-bold">${bomNum(r.итого_ч, 2)}</td><td></td><td class="text-end fw-bold">${tmMoney(r.итого_руб)}</td></tr></tfoot></table></div>
                <div class="tm-sub-title mt-3 mb-1"><i class="fas fa-industry"></i> Загрузка оборудования (ГРЦ)</div>
                <div class="table-responsive"><table class="data-table bom-calc-table"><thead><tr><th>ГРЦ</th><th class="text-end">Операций</th><th class="text-end">Машино-часы</th><th class="text-end">Смен (8 ч × ед. обор.)</th><th class="text-end">Ставка, руб/маш-ч</th><th class="text-end">Затраты, руб.</th></tr></thead><tbody>
                ${r.грц.map(g => `<tr><td>${escapeHtml(g.грц)}</td><td class="text-end">${g.операций}</td><td class="text-end fw-bold">${bomNum(g.машино_часы, 2)}</td><td class="text-end">${g.фонд_ч_в_смену ? bomNum(g.машино_часы / g.фонд_ч_в_смену, 2) : '—'}</td><td class="text-end">${tmMoney(g.ставка)}</td><td class="text-end">${tmMoney(g.стоимость)}</td></tr>`).join('')}
                </tbody></table></div>`;
        } else {
            const r = await apiRequest(`/tm/products/${id}/cost?quantity=${q}`);
            const total = r.items.find(i => i.статья.startsWith('Итого'))?.сумма || 0;
            out.innerHTML = `<div class="row g-3"><div class="col-lg-7"><table class="data-table bom-calc-table"><thead><tr><th>Статья затрат</th><th class="text-end">Сумма на ${bomNum(q)} шт., руб.</th><th class="text-end">На 1 шт., руб.</th><th class="text-end">Доля</th></tr></thead><tbody>
                ${r.items.map(i => { const t = i.статья.startsWith('Итого'); return `<tr class="${t ? 'tm-total' : ''}"><td>${escapeHtml(i.статья)}</td><td class="text-end">${tmMoney(i.сумма)}</td><td class="text-end">${tmMoney(i.на_единицу)}</td><td class="text-end">${t ? '100 %' : (total ? bomNum(i.сумма / total * 100, 1) + ' %' : '—')}</td></tr>`; }).join('')}
                </tbody></table></div>
                <div class="col-lg-5"><div class="tm-cost-bars">${r.items.filter(i => !i.статья.startsWith('Итого')).map((i, k) => `
                    <div class="tm-cost-bar"><div class="d-flex justify-content-between small"><span>${escapeHtml(i.статья)}</span><b>${total ? bomNum(i.сумма / total * 100, 1) : 0} %</b></div>
                    <div class="tm-bar"><span class="tm-bar-fill tm-bar-${k}" style="width:${total ? i.сумма / total * 100 : 0}%"></span></div></div>`).join('')}
                    <div class="small text-muted mt-2">Себестоимость = материалы (SUM_MR × цена) + оплата труда (TR_TO × ставка разряда) + работа оборудования (машино-часы ГРЦ × ставка).</div>
                </div></div></div>`;
        }
    } catch (e) { out.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(e.message)}</div>`; }
}

/* ============================== Модальные окна маршрута (администратор) ============================== */
function tmShowOperationModal(productId, kind, op = null) {
    const R = tmState.refs;
    const edit = !!op;
    const buy = kind === 'ЗАКУПКА';
    const typ = !!op?.типовой_тп_id;
    const title = buy ? (edit ? 'Позиция закупки' : 'Новая позиция закупки') : (edit ? `Операция ${tmOpNo(op.номер)}` : 'Новая операция тех-маршрута');
    let body;
    if (buy) {
        body = `<div class="alert alert-light border small"><i class="fas fa-info-circle text-primary"></i> Позиция закупки — подкласс Изделия-Операции: изделие поступает готовым, у него нет входных ресурсов и норм времени.</div>
        <div class="row g-3">
            <div class="col-md-6 form-field"><label class="form-label" for="tmPrice">Цена закупки, руб. *</label><input type="number" class="form-control" id="tmPrice" min="0" step="any" value="${op?.цена ?? ''}"></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmUnit">За единицу</label><select class="form-select" id="tmUnit">${bomUnitOptions(op?.ед_изм_id)}</select></div>
            <div class="col-12 form-field"><label class="form-label" for="tmNote">Примечание (поставщик, условия)</label><input type="text" class="form-control" id="tmNote" value="${escapeHtml(op?.примечание || '')}"></div>
        </div>`;
    } else {
        body = `<div class="row g-3">
            <div class="col-md-3 form-field"><label class="form-label" for="tmNum">Номер</label><input type="number" class="form-control" id="tmNum" min="1" step="1" value="${op?.номер ?? ''}" placeholder="авто"></div>
            <div class="col-md-9 form-field"><label class="form-label" for="tmName">Наименование (состояние изделия после операции) *</label><input type="text" class="form-control" id="tmName" maxlength="200" value="${escapeHtml(op?.наименование || '')}" placeholder="напр. «Деталь отлита»"></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmCls">Класс технологической операции *</label><select class="form-select" id="tmCls">${tmOptions(R.operation_classes, op?.класс_то_id, '— выберите —')}</select></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmGrc">ГРЦ (оборудование)</label><select class="form-select" id="tmGrc" ${typ ? 'disabled' : ''}>${tmOptions(R.work_centers, op?.грц_id)}</select></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmProf">Профессия</label><select class="form-select" id="tmProf" ${typ ? 'disabled' : ''}>${tmOptions(R.professions, op?.профессия_id)}</select></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmQual">Квалификация</label><select class="form-select" id="tmQual" ${typ ? 'disabled' : ''}>${tmOptions(R.qualifications, op?.квалификация_id, '—', q => `${q.name} (${q.ставка} руб/ч)`)}</select></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmTpz">Тпз, мин на партию</label><input type="number" class="form-control" id="tmTpz" min="0" step="any" value="${op?.тпз ?? 0}" ${typ ? 'disabled' : ''}></div>
            <div class="col-md-6 form-field"><label class="form-label" for="tmTsht">Тшт, мин на 1 шт.</label><input type="number" class="form-control" id="tmTsht" min="0" step="any" value="${op?.тшт ?? 0}" ${typ ? 'disabled' : ''}></div>
            ${typ ? '<div class="col-12 small text-muted"><i class="fas fa-feather"></i> Нормы времени, ГРЦ и профессии задаются типовым ТП.</div>' : ''}
            <div class="col-12 form-field"><label class="form-label" for="tmNote">Примечание</label><input type="text" class="form-control" id="tmNote" value="${escapeHtml(op?.примечание || '')}"></div>
        </div>`;
    }
    bomModal(title, body, `<button class="btn btn-primary" onclick="tmSaveOperation(this, ${productId}, '${kind}', ${edit ? op.id : 'null'})"><i class="fas fa-save"></i> Сохранить</button>`);
}

async function tmSaveOperation(btn, productId, kind, opId) {
    let payload;
    if (kind === 'ЗАКУПКА') {
        const price = tmNonNegative('tmPrice', 'Цена', true);
        if (price === undefined) return;
        payload = { вид: kind, наименование: 'Закупка', цена: price, ед_изм_id: tmVal('tmUnit'), примечание: document.getElementById('tmNote').value.trim() || null };
    } else {
        const name = document.getElementById('tmName').value.trim();
        if (!name) { bomFieldError('tmName', 'Укажите наименование'); return; }
        const num = tmVal('tmNum');
        if (num != null && (!Number.isInteger(num) || num <= 0)) { bomFieldError('tmNum', 'Номер — целое положительное число'); return; }
        if (!tmVal('tmCls')) { bomFieldError('tmCls', 'Выберите класс операции'); return; }
        const tpz = tmNonNegative('tmTpz', 'Тпз'), tsht = tmNonNegative('tmTsht', 'Тшт');
        if (tpz === undefined || tsht === undefined) return;
        payload = { вид: kind, номер: num, наименование: name, класс_то_id: tmVal('tmCls'), грц_id: tmVal('tmGrc'),
            профессия_id: tmVal('tmProf'), квалификация_id: tmVal('tmQual'), тпз: tpz, тшт: tsht,
            примечание: document.getElementById('tmNote').value.trim() || null };
    }
    try {
        const r = opId ? await apiRequest(`/tm/operations/${opId}`, 'PUT', payload)
                       : await apiRequest(`/tm/products/${productId}/operations`, 'POST', payload);
        showToast(r.message || 'Сохранено');
        bomCloseModal(btn);
        await tmRefresh();
    } catch (e) { showToast(e.message, 'error'); }
}

async function tmRefresh() {
    tmState.products = await apiRequest('/tm/products');
    await tmSelectProduct(tmState.selectedId, 'route');
}

async function tmDeleteOperation(opId) {
    if (!confirm('Удалить изделие-операцию вместе с её входными ресурсами и назначенным инструментом?')) return;
    try { const r = await apiRequest(`/tm/operations/${opId}`, 'DELETE'); showToast(r.message || 'Удалено'); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

function tmShowInputModal(opId, productId) {
    const list = tmState.products.filter(p => p.id !== productId && p.операций);
    const kinds = Object.keys(BOM_KIND_TITLES);
    const options = kinds.map(k => {
        const g = list.filter(p => p.тип_изделия === k);
        return g.length ? `<optgroup label="${BOM_KIND_TITLES[k]}">${g.map(p => `<option value="${p.id}">${escapeHtml(p.наименование)} (${escapeHtml(p.артикул || '—')})</option>`).join('')}</optgroup>` : '';
    }).join('');
    const body = `<div class="alert alert-light border small"><i class="fas fa-info-circle text-primary"></i>
            Позиция входного ресурса: для выполнения операции требуется изделие-компонент в состоянии «после операции N» в количестве <b>норма / для количества</b> на 1 шт. результата.</div>
        <div class="row g-3">
            <div class="col-12 form-field"><label class="form-label" for="tmInProd">Изделие-компонент *</label><select class="form-select" id="tmInProd"><option value="">— выберите —</option>${options}</select>
                <div class="form-hint">Показаны изделия, для которых описан маршрут или позиция закупки</div></div>
            <div class="col-12 form-field"><label class="form-label" for="tmInOp">После операции *</label><select class="form-select" id="tmInOp" disabled><option value="">—</option></select></div>
            <div class="col-md-4 form-field"><label class="form-label" for="tmInQty">Норма *</label><input type="number" class="form-control" id="tmInQty" min="0" step="any"></div>
            <div class="col-md-4 form-field"><label class="form-label" for="tmInPer">Для количества *</label><input type="number" class="form-control" id="tmInPer" min="0" step="any" value="1"></div>
            <div class="col-md-4 form-field"><label class="form-label" for="tmInUnit">ЕИ</label><select class="form-select" id="tmInUnit">${bomUnitOptions(null)}</select></div>
        </div>`;
    const m = bomModal('Входной ресурс операции', body, `<button class="btn btn-primary" onclick="tmSaveInput(this, ${opId})"><i class="fas fa-save"></i> Добавить</button>`);
    m.querySelector('#tmInProd').addEventListener('change', async e => {
        const sel = m.querySelector('#tmInOp');
        sel.disabled = true;
        if (!e.target.value) return;
        const r = await apiRequest(`/tm/products/${e.target.value}/route`);
        sel.innerHTML = r.operations.map((o, i) => `<option value="${o.id}" ${i === r.operations.length - 1 ? 'selected' : ''}>${o.закупка ? 'Закупка' : tmOpNo(o.номер) + ' ' + escapeHtml(o.наименование)}</option>`).join('');
        sel.disabled = false;
        const last = r.operations[r.operations.length - 1];
        if (last?.ед_изм_id) m.querySelector('#tmInUnit').value = last.ед_изм_id;
    });
}

async function tmSaveInput(btn, opId) {
    const inOp = tmVal('tmInOp');
    if (!tmVal('tmInProd')) { bomFieldError('tmInProd', 'Выберите изделие'); return; }
    if (!inOp) { bomFieldError('tmInOp', 'Выберите операцию'); return; }
    const q = bomPositiveNumber('tmInQty', 'Норма'), per = bomPositiveNumber('tmInPer', 'Для количества');
    if (q == null || per == null) return;
    try {
        const r = await apiRequest(`/tm/operations/${opId}/inputs`, 'POST', { вход_id: inOp, норма: q, для_количества: per, ед_изм_id: tmVal('tmInUnit') });
        showToast(r.message); bomCloseModal(btn); await tmRefresh();
    } catch (e) { showToast(e.message, 'error'); }
}

function tmShowInputEditModal(i) {
    const body = `<p class="mb-3">Компонент: <b>${escapeHtml(i.изделие)}</b> (${escapeHtml(i.после_операции || '')})</p><div class="row g-3">
        <div class="col-md-4 form-field"><label class="form-label" for="tmInQty">Норма *</label><input type="number" class="form-control" id="tmInQty" step="any" value="${i.норма}"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tmInPer">Для количества *</label><input type="number" class="form-control" id="tmInPer" step="any" value="${i.для_количества}"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tmInUnit">ЕИ</label><select class="form-select" id="tmInUnit">${bomUnitOptions(i.ед_изм_id)}</select></div></div>`;
    bomModal('Норма расхода', body, `<button class="btn btn-primary" onclick="tmUpdateInput(this, ${i.id})"><i class="fas fa-save"></i> Сохранить</button>`, '');
}

async function tmUpdateInput(btn, id) {
    const q = bomPositiveNumber('tmInQty', 'Норма'), per = bomPositiveNumber('tmInPer', 'Для количества');
    if (q == null || per == null) return;
    try { const r = await apiRequest(`/tm/inputs/${id}`, 'PUT', { норма: q, для_количества: per, ед_изм_id: tmVal('tmInUnit') }); showToast(r.message); bomCloseModal(btn); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

async function tmDeleteInput(id) {
    if (!confirm('Удалить входной ресурс операции?')) return;
    try { const r = await apiRequest(`/tm/inputs/${id}`, 'DELETE'); showToast(r.message || 'Удалено'); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

function tmShowToolLinkModal(opId) {
    const body = `<div class="row g-3"><div class="col-md-9 form-field"><label class="form-label" for="tmTool">Инструмент / оснастка *</label>
        <select class="form-select" id="tmTool">${tmOptions(tmState.refs.tools, null, '— выберите —', t => `${t.name} [${t.вид.toLowerCase()}]`)}</select></div>
        <div class="col-md-3 form-field"><label class="form-label" for="tmToolQty">Кол-во</label><input type="number" class="form-control" id="tmToolQty" value="1" min="1" step="1"></div></div>`;
    bomModal('Назначить инструмент / оснастку', body, `<button class="btn btn-primary" onclick="tmSaveToolLink(this, ${opId})"><i class="fas fa-save"></i> Назначить</button>`, '');
}

async function tmSaveToolLink(btn, opId) {
    const t = tmVal('tmTool'), q = tmVal('tmToolQty');
    if (!t) { bomFieldError('tmTool', 'Выберите инструмент'); return; }
    if (!q || q < 1 || !Number.isInteger(q)) { bomFieldError('tmToolQty', 'Целое число ≥ 1'); return; }
    try { const r = await apiRequest(`/tm/operations/${opId}/tools`, 'POST', { инструмент_id: t, количество: q }); showToast(r.message); bomCloseModal(btn); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

async function tmDeleteToolLink(id) {
    try { await apiRequest(`/tm/operation-tools/${id}`, 'DELETE'); showToast('Инструмент снят с операции'); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

async function tmShowApplyTypicalModal(opId, currentTp) {
    const body = `<div class="alert alert-light border small"><i class="fas fa-feather text-info"></i>
            Типовой ТП хранится в единственном экземпляре (паттерн «Приспособленец»); операция хранит только ссылку на него и значения параметров.</div>
        <div class="form-field mb-3"><label class="form-label" for="tmTp">Типовой ТП *</label><select class="form-select" id="tmTp">${tmOptions(tmState.refs.typical, currentTp, '— выберите —')}</select></div>
        <div id="tmTpParams"></div><div id="tmTpPreview"></div>`;
    const m = bomModal('Применение типового ТП', body, `<button class="btn btn-primary" onclick="tmApplyTypical(this, ${opId})"><i class="fas fa-check"></i> Применить</button>`);
    let current = {};
    if (currentTp) {
        const r = await apiRequest(`/tm/products/${tmState.selectedId}/route`);
        const op = r.operations.find(o => o.id === opId);
        (op?.параметры || []).forEach(p => { current[p.id] = p.значение; });
    }
    const load = async () => {
        const id = tmVal('tmTp');
        const box = m.querySelector('#tmTpParams');
        m.querySelector('#tmTpPreview').innerHTML = '';
        if (!id) { box.innerHTML = ''; return; }
        const t = await apiRequest(`/tm/typical/${id}`);
        box.innerHTML = `<div class="row g-3">${t.params.map(p => `<div class="col-md-6 form-field"><label class="form-label" for="tmTpv${p.id}">${escapeHtml(p.обозначение)} — ${escapeHtml(p.наименование)}, ${escapeHtml(p.ед_изм || '')}</label>
            <input type="number" class="form-control tm-tpv" data-id="${p.id}" id="tmTpv${p.id}" step="any" value="${current[p.id] ?? p.по_умолчанию ?? ''}">
            <div class="form-hint">допустимо ${p.мин ?? '−∞'} … ${p.макс ?? '+∞'}</div></div>`).join('')}</div>
            <button class="btn btn-sm btn-outline-secondary mt-2" type="button" id="tmTpCalc"><i class="fas fa-calculator"></i> Рассчитать нормы</button>`;
        m.querySelector('#tmTpCalc').addEventListener('click', () => tmPreviewTypical(id, m.querySelector('#tmTpPreview')));
    };
    m.querySelector('#tmTp').addEventListener('change', load);
    if (currentTp) load();
}

function tmCollectParamValues() {
    const vals = {};
    let ok = true;
    document.querySelectorAll('.tm-tpv').forEach(el => {
        const raw = el.value.replace(',', '.').trim();
        if (!raw || !isFinite(Number(raw))) { bomFieldError(el.id, 'Введите число'); ok = false; return; }
        vals[el.dataset.id] = Number(raw);
    });
    return ok ? vals : null;
}

async function tmPreviewTypical(tpId, box) {
    const vals = tmCollectParamValues();
    if (!vals) return;
    try {
        const r = await apiRequest(`/tm/typical/${tpId}/preview`, 'POST', { значения: vals });
        box.innerHTML = `<table class="data-table tm-mini mt-3"><thead><tr><th>Типовая операция</th><th class="text-end">Тпз</th><th class="text-end">Тшт</th></tr></thead><tbody>
            ${r.operations.map(o => `<tr><td>${tmOpNo(o.номер)} ${escapeHtml(o.наименование)}</td><td class="text-end">${bomNum(o.тпз, 3)}</td><td class="text-end">${bomNum(o.тшт, 5)}</td></tr>`).join('')}
            <tr class="tm-total"><td>Итого Тшт</td><td></td><td class="text-end">${bomNum(r.тшт_итого, 5)}</td></tr>
            ${r.resources.map(x => `<tr><td colspan="2"><i class="fas fa-flask text-muted"></i> ${escapeHtml(x.изделие)}</td><td class="text-end">${bomNum(x.норма, 7)} ${escapeHtml(x.ед_изм || '')}</td></tr>`).join('')}
            </tbody></table>`;
    } catch (e) { box.innerHTML = `<div class="alert alert-danger mt-3 mb-0">${escapeHtml(e.message)}</div>`; }
}

async function tmApplyTypical(btn, opId) {
    const tp = tmVal('tmTp');
    if (!tp) { bomFieldError('tmTp', 'Выберите типовой ТП'); return; }
    const vals = tmCollectParamValues();
    if (!vals) return;
    try { const r = await apiRequest(`/tm/operations/${opId}/typical`, 'POST', { тп_id: tp, значения: vals }); showToast(r.message); bomCloseModal(btn); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

async function tmRemoveTypical(opId) {
    if (!confirm('Отвязать типовой ТП? Рассчитанные нормы времени будут сохранены в операции как собственные.')) return;
    try { const r = await apiRequest(`/tm/operations/${opId}/typical`, 'DELETE'); showToast(r.message || 'Готово'); await tmRefresh(); }
    catch (e) { showToast(e.message, 'error'); }
}

async function tmShowBuildModal(productId) {
    const r = await apiRequest(`/tm/products/${productId}/route`);
    const ops = r.operations.filter(o => !o.закупка);
    const body = `<p>Компоненты действующей спецификации изделия (задание 5, с учётом модификаций) будут назначены входными ресурсами выбранной операции.
        Нормы расхода берутся из спецификации; для покупных компонентов без маршрута автоматически создаётся позиция закупки.</p>
        <div class="form-field"><label class="form-label" for="tmBuildOp">Операция-получатель</label><select class="form-select" id="tmBuildOp">
        ${ops.map(o => `<option value="${o.id}">${tmOpNo(o.номер)} ${escapeHtml(o.наименование)}</option>`).join('')}</select></div><div id="tmBuildResult" class="mt-3"></div>`;
    bomModal('Входные ресурсы по спецификации', body, `<button class="btn btn-primary" onclick="tmBuildFromBom(this, ${productId})"><i class="fas fa-wand-magic-sparkles"></i> Сформировать</button>`);
}

async function tmBuildFromBom(btn, productId) {
    try {
        const r = await apiRequest(`/tm/products/${productId}/build-from-bom?operation_id=${tmVal('tmBuildOp')}`, 'POST');
        document.getElementById('tmBuildResult').innerHTML = `<div class="alert alert-success small mb-0"><b>${escapeHtml(r.message)}</b>
            ${r.добавлено.length ? `<div>Добавлено: ${r.добавлено.map(escapeHtml).join(', ')}</div>` : ''}
            ${r.обновлено.length ? `<div>Обновлено: ${r.обновлено.map(escapeHtml).join(', ')}</div>` : ''}
            ${r.пропущено.length ? `<div class="text-muted">Пропущено: ${r.пропущено.map(escapeHtml).join('; ')}</div>` : ''}</div>`;
        btn.disabled = true;
        tmState.products = await apiRequest('/tm/products');
        tmSelectProduct(productId, 'route');
    } catch (e) { showToast(e.message, 'error'); }
}

/* ================================== Типовые ТП (Flyweight) ================================== */
function tmOpenTypical(id) {
    tmState.typicalId = id;
    tmNavigate(loadTmTypical);
}

async function loadTmTypical() {
    showLoading();
    try {
        await tmLoadRefs(true);
        const [list, stats] = await Promise.all([apiRequest('/tm/typical'), apiRequest('/tm/typical/stats')]);
        if (!tmState.typicalId || !list.some(t => t.id === tmState.typicalId)) tmState.typicalId = list[0]?.id || null;
        document.getElementById('content').innerHTML = `
        <div class="page-header">
            <h1><i class="fas fa-feather"></i> Типовые технологические процессы</h1>
            <p class="subtitle">Паттерн «Приспособленец»: нормы типового ТП (внутреннее состояние) хранятся один раз и разделяются всеми операциями; у операции хранятся только значения параметров (внешнее состояние)</p>
        </div>
        <div class="tm-stats">
            <div class="tm-stat"><span>${stats.типовых_тп}</span>типовых ТП</div>
            <div class="tm-stat"><span>${stats.применений}</span>операций используют ТТП</div>
            <div class="tm-stat"><span>${stats.строк_норм_хранится}</span>строк норм хранится</div>
            <div class="tm-stat tm-stat-muted"><span>${stats.строк_без_приспособленца}</span>строк было бы без «Приспособленца»</div>
            <div class="tm-stat"><span>${stats.значений_параметров}</span>значений параметров</div>
            <div class="tm-stat"><span>${stats.объектов_в_пуле}</span>объектов в пуле фабрики</div>
        </div>
        <div class="row g-3">
            <div class="col-xxl-3 col-lg-4"><div class="card-panel">
                <div class="card-panel-header"><span><i class="fas fa-list"></i> Типовые ТП</span>
                    ${TM_READONLY ? '' : `<button class="btn btn-sm btn-success" onclick="tmShowTypicalModal()"><i class="fas fa-plus"></i></button>`}</div>
                <div class="card-panel-body"><div class="bom-product-list">
                ${list.map(t => `<button class="bom-product-item ${t.id === tmState.typicalId ? 'active' : ''}" onclick="tmState.typicalId=${t.id}; loadTmTypical()">
                    <span class="bom-product-icon text-info"><i class="fas fa-feather"></i></span>
                    <span class="bom-product-text"><span class="bom-product-name">${escapeHtml(t.обозначение)} ${escapeHtml(t.наименование)}</span>
                    <span class="bom-product-meta">${t.операций} оп. · ${t.параметров} пар. · ${t.ресурсов} рес.</span></span>
                    <span class="bom-product-flags"><span class="badge bg-light text-dark border" title="Применений">${t.применений}</span></span></button>`).join('') || '<div class="empty-state py-4"><p>Нет типовых ТП</p></div>'}
                </div></div></div></div>
            <div class="col-xxl-9 col-lg-8"><div id="tmTypDetail"></div></div>
        </div>`;
        if (tmState.typicalId) await tmRenderTypical(tmState.typicalId);
    } catch (e) { showError(e.message); }
}

async function tmRenderTypical(id) {
    const box = document.getElementById('tmTypDetail');
    const t = await apiRequest(`/tm/typical/${id}`);
    const del = (kind, itemId) => TM_READONLY ? '' : `<td class="actions"><button class="btn btn-sm btn-outline-danger" onclick="tmDeleteTypicalItem('${kind}', ${itemId})"><i class="fas fa-trash"></i></button></td>`;
    const formula = (b, k, p, unit) => k ? `${bomNum(b, 6)} + ${bomNum(k, 6)} × ${escapeHtml(p || '?')}` : bomNum(b, 6);
    box.innerHTML = `<div class="card-panel">
        <div class="bom-head"><div><div class="bom-title">${escapeHtml(t.обозначение)} ${escapeHtml(t.наименование)}</div>
            <div class="bom-subtitle"><span><i class="fas fa-tag"></i> ${escapeHtml(t.класс_то || '—')}</span><span>${escapeHtml(t.описание || '')}</span></div></div>
            ${TM_READONLY ? '' : `<div class="bom-actions">
                <button class="btn btn-sm btn-outline-primary" onclick='tmShowTypicalModal(${JSON.stringify({ id: t.id, обозначение: t.обозначение, наименование: t.наименование, класс_то_id: t.класс_то_id, описание: t.описание }).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i> Изменить</button>
                <button class="btn btn-sm btn-outline-danger" onclick="tmDeleteTypical(${t.id})"><i class="fas fa-trash"></i> Удалить</button></div>`}
        </div>
        <div class="card-panel-body">
            <div class="tm-sub-title"><i class="fas fa-sliders-h"></i> Параметры ТПП ${TM_READONLY ? '' : `<button class="btn btn-link btn-sm p-0 ms-2" onclick="tmShowTypicalParamModal(${t.id})">+ добавить</button>`}</div>
            <table class="data-table tm-mini mb-3"><thead><tr><th>Обозначение</th><th>Наименование</th><th>ЕИ</th><th class="text-end">Мин</th><th class="text-end">Макс</th><th class="text-end">По умолчанию</th>${TM_READONLY ? '' : '<th></th>'}</tr></thead><tbody>
            ${t.params.map(p => `<tr><td><b>${escapeHtml(p.обозначение)}</b></td><td>${escapeHtml(p.наименование)}</td><td>${escapeHtml(p.ед_изм || '—')}</td><td class="text-end">${bomNum(p.мин)}</td><td class="text-end">${bomNum(p.макс)}</td><td class="text-end">${bomNum(p.по_умолчанию)}</td>${del('param', p.id)}</tr>`).join('')}
            </tbody></table>
            <div class="tm-sub-title"><i class="fas fa-list-ol"></i> Типовые операции: Тшт = база + коэф × параметр ${TM_READONLY ? '' : `<button class="btn btn-link btn-sm p-0 ms-2" onclick="tmShowTypicalOpModal(${t.id})">+ добавить</button>`}</div>
            <table class="data-table tm-mini mb-3"><thead><tr><th>№</th><th>Операция</th><th>Класс ТО</th><th>ГРЦ</th><th>Профессия, разряд</th><th class="text-end">Тпз, мин</th><th>Тшт, мин</th>${TM_READONLY ? '' : '<th></th>'}</tr></thead><tbody>
            ${t.operations.map(o => `<tr><td>${tmOpNo(o.номер)}</td><td>${escapeHtml(o.наименование)}</td><td>${escapeHtml(o.класс_то || '—')}</td><td>${escapeHtml(o.грц || '—')}</td><td>${escapeHtml(o.профессия || '—')}${o.квалификация ? ', ' + escapeHtml(o.квалификация) : ''}</td><td class="text-end">${bomNum(o.тпз)}</td><td class="text-nowrap">${formula(o.тшт_база, o.тшт_коэф, o.параметр)}</td>${del('operation', o.id)}</tr>`).join('')}
            </tbody></table>
            <div class="tm-sub-title"><i class="fas fa-flask"></i> Материальные ресурсы: Н = база + коэф × параметр (на 1 шт.) ${TM_READONLY ? '' : `<button class="btn btn-link btn-sm p-0 ms-2" onclick="tmShowTypicalResModal(${t.id})">+ добавить</button>`}</div>
            <table class="data-table tm-mini mb-3"><thead><tr><th>Материал</th><th>Норма</th><th>ЕИ</th>${TM_READONLY ? '' : '<th></th>'}</tr></thead><tbody>
            ${t.resources.map(r => `<tr><td>${escapeHtml(r.изделие)} <span class="bom-sku">${escapeHtml(r.артикул || '')}</span></td><td>${formula(r.норма_база, r.норма_коэф, r.параметр)}</td><td>${escapeHtml(r.ед_изм || '—')}</td>${del('resource', r.id)}</tr>`).join('') || '<tr><td colspan="4" class="text-muted">нет</td></tr>'}
            </tbody></table>
            <div class="tm-sub-title"><i class="fas fa-link"></i> Применение: операции, разделяющие этот типовой ТП (${t.uses.length})</div>
            <div class="table-responsive"><table class="data-table tm-mini"><thead><tr><th>Изделие</th><th>Операция</th><th>Значения параметров (внешнее состояние)</th></tr></thead><tbody>
            ${t.uses.map(u => `<tr><td><a href="#" onclick="event.preventDefault(); tmOpenProduct(${u.изделие_id})">${escapeHtml(u.изделие)}</a> <span class="bom-sku">${escapeHtml(u.артикул || '')}</span></td><td>${tmOpNo(u.номер)} ${escapeHtml(u.операция)}</td>
                <td>${Object.entries(u.значения).map(([k, v]) => `<span class="tm-param">${escapeHtml(k)} = <b>${bomNum(v)}</b></span>`).join('')}</td></tr>`).join('') || '<tr><td colspan="3" class="text-muted">Типовой ТП пока не применён</td></tr>'}
            </tbody></table></div>
        </div></div>`;
}

function tmShowTypicalModal(t = null) {
    const body = `<div class="row g-3">
        <div class="col-md-4 form-field"><label class="form-label" for="tpCode">Обозначение *</label><input class="form-control" id="tpCode" maxlength="30" value="${escapeHtml(t?.обозначение || '')}"></div>
        <div class="col-md-8 form-field"><label class="form-label" for="tpName">Наименование *</label><input class="form-control" id="tpName" maxlength="200" value="${escapeHtml(t?.наименование || '')}"></div>
        <div class="col-12 form-field"><label class="form-label" for="tpCls">Класс ТО</label><select class="form-select" id="tpCls">${tmOptions(tmState.refs.operation_classes, t?.класс_то_id)}</select></div>
        <div class="col-12 form-field"><label class="form-label" for="tpDescr">Описание</label><textarea class="form-control" id="tpDescr" rows="2">${escapeHtml(t?.описание || '')}</textarea></div></div>`;
    bomModal(t ? 'Типовой ТП' : 'Новый типовой ТП', body, `<button class="btn btn-primary" onclick="tmSaveTypical(this, ${t?.id || 'null'})"><i class="fas fa-save"></i> Сохранить</button>`);
}

async function tmSaveTypical(btn, id) {
    const code = document.getElementById('tpCode').value.trim(), name = document.getElementById('tpName').value.trim();
    if (!code) { bomFieldError('tpCode', 'Обязательное поле'); return; }
    if (!name) { bomFieldError('tpName', 'Обязательное поле'); return; }
    const payload = { обозначение: code, наименование: name, класс_то_id: tmVal('tpCls'), описание: document.getElementById('tpDescr').value.trim() || null };
    try {
        const r = id ? await apiRequest(`/tm/typical/${id}`, 'PUT', payload) : await apiRequest('/tm/typical', 'POST', payload);
        showToast(r.message); bomCloseModal(btn); tmState.typicalId = r.id || id; loadTmTypical();
    } catch (e) { showToast(e.message, 'error'); }
}

async function tmDeleteTypical(id) {
    if (!confirm('Удалить типовой ТП со всеми параметрами, операциями и ресурсами?')) return;
    try { await apiRequest(`/tm/typical/${id}`, 'DELETE'); showToast('Типовой ТП удалён'); tmState.typicalId = null; loadTmTypical(); }
    catch (e) { showToast(e.message, 'error'); }
}

async function tmDeleteTypicalItem(kind, id) {
    if (!confirm('Удалить элемент типового ТП? Изменятся нормы во всех операциях, где он применён.')) return;
    try { await apiRequest(`/tm/typical-items/${kind}/${id}`, 'DELETE'); showToast('Удалено'); loadTmTypical(); }
    catch (e) { showToast(e.message, 'error'); }
}

function tmShowTypicalParamModal(tpId) {
    const body = `<div class="row g-3">
        <div class="col-md-4 form-field"><label class="form-label" for="tppCode">Обозначение *</label><input class="form-control" id="tppCode" maxlength="20" placeholder="m"></div>
        <div class="col-md-5 form-field"><label class="form-label" for="tppName">Наименование *</label><input class="form-control" id="tppName" maxlength="100" placeholder="Масса отливки"></div>
        <div class="col-md-3 form-field"><label class="form-label" for="tppUnit">ЕИ</label><input class="form-control" id="tppUnit" maxlength="20" placeholder="г"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tppMin">Мин</label><input type="number" class="form-control" id="tppMin" step="any"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tppMax">Макс</label><input type="number" class="form-control" id="tppMax" step="any"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tppDef">По умолчанию</label><input type="number" class="form-control" id="tppDef" step="any"></div></div>`;
    bomModal('Параметр ТПП', body, `<button class="btn btn-primary" onclick="tmSaveTypicalParam(this, ${tpId})"><i class="fas fa-save"></i> Добавить</button>`, '');
}

async function tmSaveTypicalParam(btn, tpId) {
    const code = document.getElementById('tppCode').value.trim(), name = document.getElementById('tppName').value.trim();
    if (!code) { bomFieldError('tppCode', 'Обязательное поле'); return; }
    if (!name) { bomFieldError('tppName', 'Обязательное поле'); return; }
    const mn = tmVal('tppMin'), mx = tmVal('tppMax'), df = tmVal('tppDef');
    if (mn != null && mx != null && mn > mx) { bomFieldError('tppMax', 'Макс меньше мин'); return; }
    try {
        const r = await apiRequest(`/tm/typical/${tpId}/params`, 'POST', { обозначение: code, наименование: name, ед_изм: document.getElementById('tppUnit').value.trim() || null, мин: mn, макс: mx, по_умолчанию: df });
        showToast(r.message); bomCloseModal(btn); loadTmTypical();
    } catch (e) { showToast(e.message, 'error'); }
}

async function tmShowTypicalOpModal(tpId) {
    const t = await apiRequest(`/tm/typical/${tpId}`);
    const R = tmState.refs;
    const body = `<div class="row g-3">
        <div class="col-md-3 form-field"><label class="form-label" for="tpoNum">Номер</label><input type="number" class="form-control" id="tpoNum" placeholder="авто"></div>
        <div class="col-md-9 form-field"><label class="form-label" for="tpoName">Наименование *</label><input class="form-control" id="tpoName" maxlength="200"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="tpoCls">Класс ТО</label><select class="form-select" id="tpoCls">${tmOptions(R.operation_classes, null)}</select></div>
        <div class="col-md-6 form-field"><label class="form-label" for="tpoGrc">ГРЦ</label><select class="form-select" id="tpoGrc">${tmOptions(R.work_centers, null)}</select></div>
        <div class="col-md-6 form-field"><label class="form-label" for="tpoProf">Профессия</label><select class="form-select" id="tpoProf">${tmOptions(R.professions, null)}</select></div>
        <div class="col-md-6 form-field"><label class="form-label" for="tpoQual">Квалификация</label><select class="form-select" id="tpoQual">${tmOptions(R.qualifications, null)}</select></div>
        <div class="col-md-3 form-field"><label class="form-label" for="tpoTpz">Тпз</label><input type="number" class="form-control" id="tpoTpz" step="any" value="0"></div>
        <div class="col-md-3 form-field"><label class="form-label" for="tpoBase">Тшт база</label><input type="number" class="form-control" id="tpoBase" step="any" value="0"></div>
        <div class="col-md-3 form-field"><label class="form-label" for="tpoCoef">Тшт коэф</label><input type="number" class="form-control" id="tpoCoef" step="any" value="0"></div>
        <div class="col-md-3 form-field"><label class="form-label" for="tpoParam">× параметр</label><select class="form-select" id="tpoParam">${tmOptions(t.params.map(p => ({ id: p.id, name: p.обозначение })), null)}</select></div></div>`;
    bomModal('Типовая операция', body, `<button class="btn btn-primary" onclick="tmSaveTypicalOp(this, ${tpId})"><i class="fas fa-save"></i> Добавить</button>`);
}

async function tmSaveTypicalOp(btn, tpId) {
    const name = document.getElementById('tpoName').value.trim();
    if (!name) { bomFieldError('tpoName', 'Обязательное поле'); return; }
    const tpz = tmNonNegative('tpoTpz', 'Тпз'), b = tmNonNegative('tpoBase', 'База'), k = tmNonNegative('tpoCoef', 'Коэффициент');
    if ([tpz, b, k].includes(undefined)) return;
    if (k && !tmVal('tpoParam')) { bomFieldError('tpoParam', 'Укажите параметр для коэффициента'); return; }
    try {
        const r = await apiRequest(`/tm/typical/${tpId}/operations`, 'POST', { номер: tmVal('tpoNum'), наименование: name, класс_то_id: tmVal('tpoCls'), грц_id: tmVal('tpoGrc'),
            профессия_id: tmVal('tpoProf'), квалификация_id: tmVal('tpoQual'), тпз: tpz, тшт_база: b, тшт_коэф: k, параметр_id: tmVal('tpoParam') });
        showToast(r.message); bomCloseModal(btn); loadTmTypical();
    } catch (e) { showToast(e.message, 'error'); }
}

async function tmShowTypicalResModal(tpId) {
    const t = await apiRequest(`/tm/typical/${tpId}`);
    const mats = tmState.products.filter(p => ['МАТЕРИАЛ', 'КОМПЛЕКТУЮЩЕЕ'].includes(p.тип_изделия));
    const body = `<div class="row g-3">
        <div class="col-12 form-field"><label class="form-label" for="tprProd">Материал / комплектующее *</label><select class="form-select" id="tprProd">${tmOptions(mats, null, '— выберите —', p => `${p.наименование} (${p.ед_изм || '—'})`)}</select></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tprBase">Норма база</label><input type="number" class="form-control" id="tprBase" step="any" value="0"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tprCoef">Норма коэф</label><input type="number" class="form-control" id="tprCoef" step="any" value="0"></div>
        <div class="col-md-4 form-field"><label class="form-label" for="tprParam">× параметр</label><select class="form-select" id="tprParam">${tmOptions(t.params.map(p => ({ id: p.id, name: p.обозначение })), null)}</select></div></div>`;
    bomModal('Материальный ресурс типового ТП', body, `<button class="btn btn-primary" onclick="tmSaveTypicalRes(this, ${tpId})"><i class="fas fa-save"></i> Добавить</button>`, '');
}

async function tmSaveTypicalRes(btn, tpId) {
    if (!tmVal('tprProd')) { bomFieldError('tprProd', 'Выберите материал'); return; }
    const b = tmNonNegative('tprBase', 'База'), k = tmNonNegative('tprCoef', 'Коэффициент');
    if (b === undefined || k === undefined) return;
    if (!b && !k) { bomFieldError('tprBase', 'Задайте базу или коэффициент'); return; }
    try {
        const r = await apiRequest(`/tm/typical/${tpId}/resources`, 'POST', { изделие_id: tmVal('tprProd'), норма_база: b, норма_коэф: k, параметр_id: tmVal('tprParam') });
        showToast(r.message); bomCloseModal(btn); loadTmTypical();
    } catch (e) { showToast(e.message, 'error'); }
}

/* ================================== ГРЦ ================================== */
async function loadTmWorkCenters() {
    showLoading();
    try {
        await tmLoadRefs(true);
        const list = await apiRequest('/tm/work-centers');
        document.getElementById('content').innerHTML = `
        <div class="page-header"><h1><i class="fas fa-industry"></i> Групповые рабочие центры (ГРЦ)</h1>
            <p class="subtitle">Группы однотипного оборудования, на которых выполняются технологические операции; ставка машино-часа используется в калькуляции</p></div>
        <div class="card-panel"><div class="card-panel-header"><span><i class="fas fa-list"></i> ГРЦ: ${list.length}</span>
            ${TM_READONLY ? '' : `<button class="btn btn-sm btn-success" onclick="tmShowWorkCenterModal()"><i class="fas fa-plus"></i> Добавить ГРЦ</button>`}</div>
        <div class="card-panel-body"><div class="table-responsive"><table class="data-table"><thead><tr><th>Код</th><th>Наименование</th><th>Тип оборудования</th><th>Подразделение</th><th class="text-end">Ед. оборудования</th><th class="text-end">Ставка, руб/маш-ч</th><th class="text-end">Операций</th>${TM_READONLY ? '' : '<th>Действия</th>'}</tr></thead><tbody>
        ${list.map(g => `<tr><td class="fw-semibold">${escapeHtml(g.код)}</td><td>${escapeHtml(g.наименование)}</td><td>${escapeHtml(g.класс || '—')}</td><td>${escapeHtml(g.подразделение || '—')}</td>
            <td class="text-end">${g.количество_ед}</td><td class="text-end">${tmMoney(g.ставка_часа)}</td><td class="text-end">${g.операций}</td>
            ${TM_READONLY ? '' : `<td class="actions"><button class="btn btn-sm btn-outline-primary" onclick='tmShowWorkCenterModal(${JSON.stringify(g).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-outline-danger" onclick="tmDeleteWorkCenter(${g.id}, '${tmQuote(g.код)}')"><i class="fas fa-trash"></i></button></td>`}</tr>`).join('')}
        </tbody></table></div></div></div>`;
    } catch (e) { showError(e.message); }
}

function tmShowWorkCenterModal(g = null) {
    const R = tmState.refs;
    const body = `<div class="row g-3">
        <div class="col-md-4 form-field"><label class="form-label" for="wcCode">Код *</label><input class="form-control" id="wcCode" maxlength="20" value="${escapeHtml(g?.код || '')}"></div>
        <div class="col-md-8 form-field"><label class="form-label" for="wcName">Наименование *</label><input class="form-control" id="wcName" maxlength="200" value="${escapeHtml(g?.наименование || '')}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="wcCls">Тип оборудования (классификатор)</label><select class="form-select" id="wcCls">${tmOptions(R.equipment_classes, g?.класс_id)}</select></div>
        <div class="col-md-6 form-field"><label class="form-label" for="wcSubj">Подразделение (субъект ХД)</label><select class="form-select" id="wcSubj">${tmOptions(R.subjects, g?.субъект_id)}</select></div>
        <div class="col-md-6 form-field"><label class="form-label" for="wcQty">Единиц оборудования *</label><input type="number" class="form-control" id="wcQty" min="1" step="1" value="${g?.количество_ед ?? 1}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="wcRate">Ставка машино-часа, руб.</label><input type="number" class="form-control" id="wcRate" min="0" step="any" value="${g?.ставка_часа ?? 0}"></div></div>`;
    bomModal(g ? `ГРЦ ${g.код}` : 'Новый ГРЦ', body, `<button class="btn btn-primary" onclick="tmSaveWorkCenter(this, ${g?.id || 'null'})"><i class="fas fa-save"></i> Сохранить</button>`);
}

async function tmSaveWorkCenter(btn, id) {
    const code = document.getElementById('wcCode').value.trim(), name = document.getElementById('wcName').value.trim();
    if (!code) { bomFieldError('wcCode', 'Обязательное поле'); return; }
    if (!name) { bomFieldError('wcName', 'Обязательное поле'); return; }
    const qty = tmVal('wcQty');
    if (!qty || qty < 1 || !Number.isInteger(qty)) { bomFieldError('wcQty', 'Целое число ≥ 1'); return; }
    const rate = tmNonNegative('wcRate', 'Ставка');
    if (rate === undefined) return;
    const payload = { код: code, наименование: name, класс_id: tmVal('wcCls'), субъект_id: tmVal('wcSubj'), количество_ед: qty, ставка_часа: rate };
    try {
        const r = id ? await apiRequest(`/tm/work-centers/${id}`, 'PUT', payload) : await apiRequest('/tm/work-centers', 'POST', payload);
        showToast(r.message); bomCloseModal(btn); tmState.refs = null; loadTmWorkCenters();
    } catch (e) { showToast(e.message, 'error'); }
}

async function tmDeleteWorkCenter(id, code) {
    if (!confirm(`Удалить ГРЦ «${code}»?`)) return;
    try { await apiRequest(`/tm/work-centers/${id}`, 'DELETE'); showToast('ГРЦ удалён'); tmState.refs = null; loadTmWorkCenters(); }
    catch (e) { showToast(e.message, 'error'); }
}

/* ================================== Инструмент и оснастка ================================== */
async function loadTmTools() {
    showLoading();
    try {
        await tmLoadRefs(true);
        const list = await apiRequest('/tm/tools');
        document.getElementById('content').innerHTML = `
        <div class="page-header"><h1><i class="fas fa-screwdriver-wrench"></i> Инструмент и оснастка</h1>
            <p class="subtitle">Технологическая оснастка (пресс-формы, клише, приспособления) и инструмент, назначаемые операциям маршрута</p></div>
        <div class="card-panel"><div class="card-panel-header"><span><i class="fas fa-list"></i> Позиций: ${list.length}</span>
            ${TM_READONLY ? '' : `<button class="btn btn-sm btn-success" onclick="tmShowToolModal()"><i class="fas fa-plus"></i> Добавить</button>`}</div>
        <div class="card-panel-body"><div class="table-responsive"><table class="data-table"><thead><tr><th>Обозначение</th><th>Наименование</th><th>Вид</th><th>Класс</th><th class="text-end">Операций</th>${TM_READONLY ? '' : '<th>Действия</th>'}</tr></thead><tbody>
        ${list.map(t => `<tr><td class="fw-semibold">${escapeHtml(t.обозначение)}</td><td>${escapeHtml(t.наименование)}</td>
            <td><span class="tm-tool ${t.вид === 'ОСНАСТКА' ? 'tm-tool-fix' : ''}">${t.вид === 'ОСНАСТКА' ? 'оснастка' : 'инструмент'}</span></td><td>${escapeHtml(t.класс || '—')}</td><td class="text-end">${t.операций}</td>
            ${TM_READONLY ? '' : `<td class="actions"><button class="btn btn-sm btn-outline-primary" onclick='tmShowToolModal(${JSON.stringify(t).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-outline-danger" onclick="tmDeleteTool(${t.id}, '${tmQuote(t.обозначение)}')"><i class="fas fa-trash"></i></button></td>`}</tr>`).join('')}
        </tbody></table></div></div></div>`;
    } catch (e) { showError(e.message); }
}

function tmShowToolModal(t = null) {
    const body = `<div class="row g-3">
        <div class="col-md-4 form-field"><label class="form-label" for="tlCode">Обозначение *</label><input class="form-control" id="tlCode" maxlength="50" value="${escapeHtml(t?.обозначение || '')}"></div>
        <div class="col-md-8 form-field"><label class="form-label" for="tlName">Наименование *</label><input class="form-control" id="tlName" maxlength="200" value="${escapeHtml(t?.наименование || '')}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="tlKind">Вид *</label><select class="form-select" id="tlKind">
            <option value="ИНСТРУМЕНТ" ${t?.вид !== 'ОСНАСТКА' ? 'selected' : ''}>Инструмент</option><option value="ОСНАСТКА" ${t?.вид === 'ОСНАСТКА' ? 'selected' : ''}>Оснастка</option></select></div>
        <div class="col-md-6 form-field"><label class="form-label" for="tlCls">Класс (классификатор)</label><select class="form-select" id="tlCls">${tmOptions(tmState.refs.tool_classes, t?.класс_id)}</select></div></div>`;
    bomModal(t ? t.обозначение : 'Новый инструмент / оснастка', body, `<button class="btn btn-primary" onclick="tmSaveTool(this, ${t?.id || 'null'})"><i class="fas fa-save"></i> Сохранить</button>`);
}

async function tmSaveTool(btn, id) {
    const code = document.getElementById('tlCode').value.trim(), name = document.getElementById('tlName').value.trim();
    if (!code) { bomFieldError('tlCode', 'Обязательное поле'); return; }
    if (!name) { bomFieldError('tlName', 'Обязательное поле'); return; }
    const payload = { обозначение: code, наименование: name, вид: document.getElementById('tlKind').value, класс_id: tmVal('tlCls') };
    try {
        const r = id ? await apiRequest(`/tm/tools/${id}`, 'PUT', payload) : await apiRequest('/tm/tools', 'POST', payload);
        showToast(r.message); bomCloseModal(btn); tmState.refs = null; loadTmTools();
    } catch (e) { showToast(e.message, 'error'); }
}

async function tmDeleteTool(id, code) {
    if (!confirm(`Удалить «${code}»?`)) return;
    try { await apiRequest(`/tm/tools/${id}`, 'DELETE'); showToast('Удалено'); tmState.refs = null; loadTmTools(); }
    catch (e) { showToast(e.message, 'error'); }
}
