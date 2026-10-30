/**
 * Задание 5. Материальная спецификация изделий (Bill of materials)
 * Общий модуль для интерфейсов администратора (редактирование) и пользователя (просмотр).
 */
const BOM_READONLY = document.body.dataset.role !== 'admin';

const BOM_KIND_TITLES = {
    'МАТЕРИАЛ': 'Материал',
    'КОМПЛЕКТУЮЩЕЕ': 'Комплектующее',
    'ДЕТАЛЬ': 'Деталь',
    'УЗЕЛ': 'Сборочная единица',
    'КОМПЛЕКС': 'Комплекс',
};
const BOM_KIND_ICONS = {
    'МАТЕРИАЛ': 'fa-flask',
    'КОМПЛЕКТУЮЩЕЕ': 'fa-box-open',
    'ДЕТАЛЬ': 'fa-puzzle-piece',
    'УЗЕЛ': 'fa-cubes-stacked',
    'КОМПЛЕКС': 'fa-cubes',
};
const BOM_KIND_COLORS = {
    'МАТЕРИАЛ': '#6d4c41',
    'КОМПЛЕКТУЮЩЕЕ': '#00838f',
    'ДЕТАЛЬ': '#1565c0',
    'УЗЕЛ': '#6a1b9a',
    'КОМПЛЕКС': '#e65100',
};
const BOM_CHANGE_COLORS = {
    'ДОБАВЛЕНИЕ': 'success', 'ЗАМЕНА': 'warning', 'ИЗМЕНЕНИЕ_НОРМЫ': 'info', 'УДАЛЕНИЕ': 'danger',
    'ИСКЛЮЧЕНИЕ': 'danger', 'ВОССТАНОВЛЕНИЕ': 'secondary', 'МОДИФИКАЦИЯ': 'primary', 'ПРОЧЕЕ': 'dark',
};

let bomState = { products: [], units: [], classes: [], selectedId: null, tab: 'spec', search: '', kind: '', pendingId: null };

function bomNum(v, digits = 6) {
    if (v == null) return '—';
    return Number(v).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function bomKindBadge(kind) {
    const color = BOM_KIND_COLORS[kind] || '#616161';
    return `<span class="bom-kind" style="--kind:${color}"><i class="fas ${BOM_KIND_ICONS[kind] || 'fa-cube'}"></i> ${escapeHtml(BOM_KIND_TITLES[kind] || kind || '—')}</span>`;
}

function bomModal(title, bodyHtml, footerHtml = '', size = 'modal-lg') {
    const modal = document.createElement('div');
    modal.className = 'modal fade modal-app';
    modal.tabIndex = -1;
    modal.innerHTML = `<div class="modal-dialog ${size}"><div class="modal-content">
        <div class="modal-header"><h5 class="modal-title">${escapeHtml(title)}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>${footerHtml}</div>
    </div></div>`;
    document.body.appendChild(modal);
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
    bootstrap.Modal.getOrCreateInstance(modal).show();
    return modal;
}

function bomCloseModal(el) {
    const m = el.closest('.modal');
    if (m) bootstrap.Modal.getOrCreateInstance(m).hide();
}

function bomFieldError(id, message) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('field-invalid');
    let msg = el.parentElement.querySelector('.field-error-msg');
    if (!msg) { msg = document.createElement('div'); msg.className = 'field-error-msg'; el.parentElement.appendChild(msg); }
    msg.textContent = message;
    el.addEventListener('input', () => { el.classList.remove('field-invalid'); msg.remove(); }, { once: true });
}

function bomPositiveNumber(id, label) {
    const raw = (document.getElementById(id)?.value || '').replace(',', '.').trim();
    const v = Number(raw);
    if (!raw || !isFinite(v)) { bomFieldError(id, `${label}: введите число`); return null; }
    if (v <= 0) { bomFieldError(id, `${label}: значение должно быть больше 0`); return null; }
    return v;
}

async function bomLoadRefs(force = false) {
    if (force || !bomState.units.length) bomState.units = await apiRequest('/bom/units');
    if (force || !bomState.classes.length) bomState.classes = await apiRequest('/categories');
    bomState.products = await apiRequest('/bom/products');
}

function bomUnitOptions(selected) {
    return `<option value="">—</option>` + bomState.units.map(u =>
        `<option value="${u.id}" ${u.id === selected ? 'selected' : ''}>${escapeHtml(u.обозначение)} — ${escapeHtml(u.наименование)}</option>`).join('');
}

function bomNavigate(fn) {
    if (BOM_READONLY && typeof navigateUser === 'function') navigateUser(null, fn);
    else if (typeof navigateAdmin === 'function') navigateAdmin(null, fn);
    else fn();
    const link = Array.from(document.querySelectorAll('.app-sidebar .nav-link')).find(l => (l.getAttribute('onclick') || '').includes(fn.name));
    if (link) setActiveNav(link);
}

function bomOpenProduct(id, tab = 'spec') {
    bomState.pendingId = id;
    bomState.tab = tab;
    bomNavigate(loadBomSpecs);
}

/* ============================== Страница «Спецификации» ============================== */
async function loadBomSpecs() {
    showLoading();
    try {
        await bomLoadRefs();
        const kinds = Object.keys(BOM_KIND_TITLES);
        document.getElementById('content').innerHTML = `
        <div class="page-header">
            <h1><i class="fas fa-sitemap"></i> Спецификации изделий (BOM)</h1>
            <p class="subtitle">${BOM_READONLY
                ? 'Просмотр состава изделий на всю глубину вложенности и расчёт сводных норм расхода материалов'
                : 'Формирование состава изделий, нормы расхода, модификации и управление изменениями'}</p>
        </div>
        <div class="row g-3">
            <div class="col-xxl-3 col-lg-4">
                <div class="card-panel bom-list-panel">
                    <div class="card-panel-header"><span><i class="fas fa-list"></i> Изделия</span><span class="text-muted small" id="bomListCount"></span></div>
                    <div class="card-panel-body">
                        <div class="d-flex gap-2 mb-2">
                            <input type="search" class="form-control form-control-sm" id="bomSearch" placeholder="Наименование или артикул" value="${escapeHtml(bomState.search)}">
                            <select class="form-select form-select-sm" id="bomKind" style="max-width:170px">
                                <option value="">Все типы</option>
                                ${kinds.map(k => `<option value="${k}" ${bomState.kind === k ? 'selected' : ''}>${BOM_KIND_TITLES[k]}</option>`).join('')}
                            </select>
                        </div>
                        <div class="bom-product-list" id="bomProductList"></div>
                    </div>
                </div>
            </div>
            <div class="col-xxl-9 col-lg-8"><div id="bomDetail"></div></div>
        </div>`;
        document.getElementById('bomSearch').addEventListener('input', e => { bomState.search = e.target.value; bomRenderList(); });
        document.getElementById('bomKind').addEventListener('change', e => { bomState.kind = e.target.value; bomRenderList(); });
        bomRenderList();
        const target = bomState.pendingId || bomState.selectedId
            || (bomState.products.find(p => p.артикул === 'SET-75257') || bomState.products[0] || {}).id;
        bomState.pendingId = null;
        if (target) await bomSelectProduct(target, bomState.tab);
        else document.getElementById('bomDetail').innerHTML = `<div class="card-panel"><div class="empty-state"><i class="fas fa-box-open"></i><p>Нет изделий</p></div></div>`;
    } catch (e) { showError(e.message); }
}

function bomRenderList() {
    const q = bomState.search.toLowerCase();
    const list = bomState.products.filter(p =>
        (!bomState.kind || p.тип_изделия === bomState.kind) &&
        (!q || `${p.наименование} ${p.артикул || ''}`.toLowerCase().includes(q)));
    const el = document.getElementById('bomProductList');
    if (!el) return;
    document.getElementById('bomListCount').textContent = `${list.length} из ${bomState.products.length}`;
    if (!list.length) { el.innerHTML = `<div class="empty-state py-4"><i class="fas fa-search"></i><p>Ничего не найдено</p></div>`; return; }
    el.innerHTML = list.map(p => `
        <button class="bom-product-item ${p.id === bomState.selectedId ? 'active' : ''}" onclick="bomSelectProduct(${p.id})">
            <span class="bom-product-icon" style="color:${BOM_KIND_COLORS[p.тип_изделия] || '#616161'}"><i class="fas ${BOM_KIND_ICONS[p.тип_изделия] || 'fa-cube'}"></i></span>
            <span class="bom-product-text">
                <span class="bom-product-name">${escapeHtml(p.наименование)}</span>
                <span class="bom-product-meta">${escapeHtml(p.артикул || 'без артикула')} · ${BOM_KIND_TITLES[p.тип_изделия] || p.тип_изделия}</span>
            </span>
            <span class="bom-product-flags">
                ${p.является_модификацией ? '<span class="badge bg-warning text-dark" title="Модификация">мод.</span>' : ''}
                ${p.модификаций ? `<span class="badge bg-primary" title="Модификаций">${p.модификаций} мод.</span>` : ''}
                ${p.позиций_собственных ? `<span class="badge bg-light text-dark border" title="Собственных позиций">${p.позиций_собственных}</span>` : ''}
            </span>
        </button>`).join('');
}

async function bomSelectProduct(id, tab) {
    bomState.selectedId = id;
    if (tab) bomState.tab = tab;
    bomRenderList();
    const box = document.getElementById('bomDetail');
    if (!box) return;
    box.innerHTML = `<div class="card-panel"><div class="loading-state"><div class="spinner"></div><p>Загрузка...</p></div></div>`;
    try {
        const p = await apiRequest(`/bom/products/${id}`);
        const isMaterial = p.тип_изделия === 'МАТЕРИАЛ';
        const tabs = [
            ['spec', 'fa-list-ol', 'Состав'],
            ['tree', 'fa-sitemap', 'Полный состав'],
            ['calc', 'fa-calculator', 'Сводные нормы'],
            ['changes', 'fa-history', 'Изменения'],
            ['used', 'fa-diagram-project', 'Применяемость'],
        ];
        if (isMaterial && ['spec', 'tree', 'calc'].includes(bomState.tab)) bomState.tab = 'used';
        const actions = BOM_READONLY ? '' : `
            <div class="bom-actions">
                <button class="btn btn-sm btn-outline-secondary" onclick="bomShowKindModal(${p.id})"><i class="fas fa-sliders-h"></i> Свойства</button>
                ${isMaterial ? '' : `<button class="btn btn-sm btn-outline-primary" onclick="bomShowModificationModal(${p.id})"><i class="fas fa-code-branch"></i> Создать модификацию</button>`}
                <button class="btn btn-sm btn-outline-dark" onclick="bomShowChangeModal(${p.id})"><i class="fas fa-file-signature"></i> Зарегистрировать изменение</button>
            </div>`;
        const baseInfo = p.является_модификацией ? `
            <div class="bom-mod-info"><i class="fas fa-code-branch"></i>
                Модификация изделия <a href="#" onclick="event.preventDefault(); bomSelectProduct(${p.базовое_изделие_id}, 'spec')">«${escapeHtml(p.базовое_изделие)}»</a>.
                Базовая часть спецификации наследуется; в модификации хранятся только собственные отличия
                (добавление, замена, исключение компонентов).
                ${p.цепочка_базовых.length > 1 ? `<div class="small mt-1">Цепочка: ${p.цепочка_базовых.map(b => escapeHtml(b.наименование)).join(' → ')}</div>` : ''}
            </div>` : '';
        const modsInfo = p.модификации.length ? `
            <div class="bom-mods-line"><span class="text-muted">Модификации:</span>
                ${p.модификации.map(m => `<a href="#" class="bom-chip" onclick="event.preventDefault(); bomSelectProduct(${m.id}, 'spec')"><i class="fas fa-code-branch"></i> ${escapeHtml(m.наименование)}</a>`).join('')}
            </div>` : '';
        box.innerHTML = `
        <div class="card-panel">
            <div class="bom-head">
                <div>
                    <div class="bom-title">${escapeHtml(p.наименование)}</div>
                    <div class="bom-subtitle">
                        <span><i class="fas fa-barcode"></i> ${escapeHtml(p.артикул || '—')}</span>
                        ${bomKindBadge(p.тип_изделия)}
                        <span><i class="fas fa-folder"></i> ${escapeHtml(p.класс_название || '—')}</span>
                        <span><i class="fas fa-ruler"></i> ЕИ: ${escapeHtml(p.ед_изм || '—')}</span>
                        ${p.является_модификацией ? '<span class="badge bg-warning text-dark">Модификация</span>' : '<span class="badge bg-success">Базовое изделие</span>'}
                    </div>
                </div>
                ${actions}
            </div>
            ${baseInfo}${modsInfo}
            <ul class="nav nav-tabs bom-tabs px-3">
                ${tabs.map(([k, ic, t]) => `<li class="nav-item"><a href="#" class="nav-link ${bomState.tab === k ? 'active' : ''} ${isMaterial && ['spec', 'tree', 'calc'].includes(k) ? 'disabled' : ''}" onclick="event.preventDefault(); bomSwitchTab('${k}')"><i class="fas ${ic}"></i> ${t}</a></li>`).join('')}
            </ul>
            <div class="card-panel-body" id="bomTabBody"></div>
        </div>`;
        await bomRenderTab(p);
    } catch (e) { box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`; }
}

function bomSwitchTab(tab) {
    bomState.tab = tab;
    bomSelectProduct(bomState.selectedId, tab);
}

async function bomRenderTab(p) {
    const body = document.getElementById('bomTabBody');
    try {
        if (bomState.tab === 'spec') body.innerHTML = await bomSpecHtml(p);
        else if (bomState.tab === 'tree') body.innerHTML = await bomTreeHtml(p);
        else if (bomState.tab === 'calc') { body.innerHTML = bomCalcFormHtml(p); }
        else if (bomState.tab === 'changes') body.innerHTML = await bomChangesHtml(p.id);
        else if (bomState.tab === 'used') body.innerHTML = await bomWhereUsedHtml(p);
        if (bomState.tab === 'calc') await bomRunCalc();
    } catch (e) { body.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(e.message)}</div>`; }
}

/* ----- Вкладка «Состав» (1 уровень) ----- */
async function bomSpecHtml(p) {
    const s = await apiRequest(`/bom/products/${p.id}/spec`);
    const isMod = p.является_модификацией;
    let html = `<div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
        <div class="text-muted small">Позиций в спецификации: <b>${s.items.length}</b>${isMod ? ` (собственных: ${s.items.filter(i => !i.унаследовано).length}, унаследовано: ${s.items.filter(i => i.унаследовано).length}, исключено: ${s.excluded.length})` : ''}</div>
        ${BOM_READONLY ? '' : `<button class="btn btn-sm btn-success" onclick="bomShowPositionModal(${p.id})"><i class="fas fa-plus"></i> Добавить позицию</button>`}
    </div>`;
    if (!s.items.length) {
        html += `<div class="empty-state py-4"><i class="fas fa-layer-group"></i><p>Спецификация пуста. ${BOM_READONLY ? '' : 'Добавьте компоненты кнопкой «Добавить позицию».'}</p></div>`;
    } else {
        html += `<div class="table-responsive"><table class="data-table bom-table"><thead><tr>
            <th>№</th><th>Компонент</th><th>Тип</th><th class="text-end">Расход</th><th class="text-end">Для кол-ва</th><th>ЕИ</th><th class="text-end">Норма на 1</th><th>Признак</th>${BOM_READONLY ? '' : '<th>Действия</th>'}
        </tr></thead><tbody>`;
        for (const i of s.items) {
            let flag = '';
            if (i.унаследовано) flag = `<span class="badge bg-light text-dark border" title="Наследуется из «${escapeHtml(i.источник)}»"><i class="fas fa-level-up-alt"></i> из базового</span>`;
            else if (i.вид_позиции === 'ДОБАВЛЕНИЕ') flag = `<span class="badge bg-success">добавление</span>`;
            else if (i.вид_позиции === 'ЗАМЕНА') flag = `<span class="badge bg-warning text-dark">замена</span>`;
            else flag = i.флаг_базы ? `<span class="badge bg-primary" title="Флаг базы: наследуется модификациями">базовая</span>` : `<span class="badge bg-secondary" title="Не наследуется модификациями">не базовая</span>`;
            let acts = '';
            if (!BOM_READONLY) {
                if (i.унаследовано) {
                    acts = `<button class="btn btn-sm btn-outline-warning" title="Заменить норму в модификации" onclick="bomShowPositionModal(${p.id}, null, ${i.компонент_id}, ${i.расход}, ${i.для_количества}, ${i.ед_изм_id || 'null'})"><i class="fas fa-exchange-alt"></i></button>
                            <button class="btn btn-sm btn-outline-danger" title="Исключить из модификации" onclick="bomShowExcludeModal(${p.id}, ${i.компонент_id}, '${escapeHtml(i.компонент).replace(/'/g, "\\'")}')"><i class="fas fa-ban"></i></button>`;
                } else {
                    acts = `<button class="btn btn-sm btn-outline-primary" title="Изменить норму" onclick='bomShowPositionModal(${p.id}, ${JSON.stringify(i).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button>
                            <button class="btn btn-sm btn-outline-danger" title="Удалить позицию" onclick="bomDeletePosition(${i.позиция_id}, '${escapeHtml(i.компонент).replace(/'/g, "\\'")}')"><i class="fas fa-trash"></i></button>`;
                }
            }
            html += `<tr class="${i.унаследовано ? 'bom-inherited' : ''}">
                <td>${i.номер}</td>
                <td><a href="#" onclick="event.preventDefault(); bomSelectProduct(${i.компонент_id})">${escapeHtml(i.компонент)}</a><div class="small text-muted">${escapeHtml(i.артикул || '')}${i.примечание ? ' · ' + escapeHtml(i.примечание) : ''}</div></td>
                <td>${bomKindBadge(i.тип_изделия)}</td>
                <td class="text-end">${bomNum(i.расход)}</td>
                <td class="text-end">${bomNum(i.для_количества)}</td>
                <td>${escapeHtml(i.ед_изм || '—')}</td>
                <td class="text-end">${bomNum(i.норма_на_единицу)}</td>
                <td>${flag}</td>
                ${BOM_READONLY ? '' : `<td class="actions">${acts}</td>`}
            </tr>`;
        }
        html += `</tbody></table></div>`;
    }
    if (s.excluded.length) {
        html += `<div class="bom-excluded mt-3"><div class="fw-semibold mb-1"><i class="fas fa-ban text-danger"></i> Исключено из модификации</div>
            <table class="data-table"><tbody>${s.excluded.map(x => `<tr><td><s>${escapeHtml(x.компонент)}</s> <span class="small text-muted">${escapeHtml(x.артикул || '')}</span></td><td class="small text-muted">${escapeHtml(x.примечание || '')}</td>
            ${BOM_READONLY ? '' : `<td class="actions"><button class="btn btn-sm btn-outline-secondary" onclick="bomRestorePosition(${x.позиция_id})"><i class="fas fa-undo"></i> Восстановить</button></td>`}</tr>`).join('')}</tbody></table></div>`;
    }
    return html;
}

/* ----- Вкладка «Полный состав» (FIND_BOM) ----- */
async function bomTreeHtml(p) {
    const f = await apiRequest(`/bom/products/${p.id}/find`);
    if (!f.rows.length) return `<div class="empty-state py-4"><i class="fas fa-sitemap"></i><p>У изделия нет состава</p></div>`;
    let html = `<div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
        <div class="text-muted small">Строк состава: <b>${f.всего_строк}</b> · глубина вложенности: <b>${f.глубина}</b> · количество указано на 1 ед. «${escapeHtml(p.наименование)}»</div>
        <div><button class="btn btn-sm btn-outline-secondary" onclick="bomTreeToggleAll(false)"><i class="fas fa-compress"></i> Свернуть</button>
        <button class="btn btn-sm btn-outline-secondary" onclick="bomTreeToggleAll(true)"><i class="fas fa-expand"></i> Развернуть</button></div>
    </div>
    <div class="table-responsive"><table class="data-table bom-tree-table"><thead><tr><th>Компонент</th><th>Тип</th><th class="text-end">Норма на ед. родителя</th><th class="text-end">Кол-во на 1 изделие</th><th>ЕИ</th></tr></thead><tbody>`;
    for (const r of f.rows) {
        const hasChildren = f.rows.some(x => x.путь.length === r.путь.length + 1 && x.путь.slice(0, -1).join('.') === r.путь.join('.'));
        html += `<tr data-path="${r.путь.join('.')}" data-level="${r.уровень}">
            <td style="padding-left:${0.6 + (r.уровень - 1) * 1.4}rem">
                ${hasChildren ? `<span class="bom-tree-toggle" onclick="bomTreeToggle(this)">▼</span>` : '<span class="bom-tree-leaf">•</span>'}
                <span class="bom-level">${r.уровень}</span>
                ${escapeHtml(r.компонент)}<span class="bom-sku">${escapeHtml(r.артикул || '')}</span>
                ${r.унаследовано ? '<span class="badge bg-light text-dark border ms-1" title="Позиция унаследована от базового изделия">насл.</span>' : ''}
            </td>
            <td>${bomKindBadge(r.тип_изделия)}</td>
            <td class="text-end">${bomNum(r.норма_на_единицу)}</td>
            <td class="text-end fw-semibold">${bomNum(r.количество)}</td>
            <td>${escapeHtml(r.ед_изм || '—')}</td>
        </tr>`;
    }
    return html + `</tbody></table></div>`;
}

function bomTreeToggle(el) {
    const row = el.closest('tr');
    const path = row.dataset.path + '.';
    const collapse = el.textContent === '▼';
    el.textContent = collapse ? '▶' : '▼';
    document.querySelectorAll('.bom-tree-table tbody tr').forEach(tr => {
        if (tr.dataset.path.startsWith(path)) {
            tr.style.display = collapse ? 'none' : '';
            const t = tr.querySelector('.bom-tree-toggle');
            if (t && !collapse) t.textContent = '▼';
        }
    });
}

function bomTreeToggleAll(expand) {
    document.querySelectorAll('.bom-tree-table tbody tr').forEach(tr => {
        const t = tr.querySelector('.bom-tree-toggle');
        if (t) t.textContent = expand ? '▼' : '▶';
        tr.style.display = expand || tr.dataset.level === '1' ? '' : 'none';
    });
}

/* ----- Вкладка «Сводные нормы» (CALC_BOM) ----- */
function bomCalcFormHtml(p) {
    const classes = bomState.classes.slice().sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    return `<div class="bom-calc-form row g-2 align-items-end mb-3">
        <div class="col-sm-3 form-field"><label class="form-label" for="bomCalcQty">Количество изделий *</label>
            <input type="number" class="form-control" id="bomCalcQty" value="${bomState.calcQty || 100}" min="1" step="1"></div>
        <div class="col-sm-6 form-field"><label class="form-label" for="bomCalcClass">Класс ресурсов</label>
            <select class="form-select" id="bomCalcClass"><option value="">Все конечные компоненты (материалы и покупные изделия)</option>
            ${classes.map(c => `<option value="${c.id}" ${String(bomState.calcClass || '') === String(c.id) ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}</select></div>
        <div class="col-sm-3"><button class="btn btn-primary w-100" onclick="bomRunCalc()"><i class="fas fa-calculator"></i> Рассчитать</button></div>
    </div><div id="bomCalcResult"></div>`;
}

async function bomRunCalc() {
    const qtyEl = document.getElementById('bomCalcQty');
    const q = bomPositiveNumber('bomCalcQty', 'Количество');
    if (q == null) return;
    const cls = document.getElementById('bomCalcClass').value;
    bomState.calcQty = q; bomState.calcClass = cls;
    const out = document.getElementById('bomCalcResult');
    out.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
    try {
        const r = await apiRequest(`/bom/products/${bomState.selectedId}/calc?quantity=${q}${cls ? '&class_id=' + cls : ''}`);
        if (!r.items.length) { out.innerHTML = `<div class="empty-state py-4"><i class="fas fa-calculator"></i><p>Компоненты выбранного класса в составе изделия не найдены</p></div>`; return; }
        let html = `<div class="small text-muted mb-2">Сводные нормы на <b>${bomNum(q)}</b> шт. «${escapeHtml(r.product.наименование)}»${r.класс ? `, класс «${escapeHtml(r.класс)}»` : ''}</div>
        <div class="table-responsive"><table class="data-table bom-calc-table"><thead><tr><th>Компонент</th><th>Тип</th><th>Класс</th><th class="text-end">Норма на 1 изделие</th><th class="text-end">Сводная норма</th><th>ЕИ</th><th class="text-end">Вхождений</th></tr></thead><tbody>`;
        for (const i of r.items) {
            html += `<tr><td>${escapeHtml(i.компонент)}<div class="small text-muted">${escapeHtml(i.артикул || '')}</div></td><td>${bomKindBadge(i.тип_изделия)}</td><td>${escapeHtml(i.класс || '—')}</td>
                <td class="text-end">${bomNum(i.норма_на_единицу)}</td><td class="text-end fw-bold">${bomNum(i.сводная_норма, 3)}</td><td>${escapeHtml(i.ед_изм || '—')}</td><td class="text-end">${i.вхождений}</td></tr>`;
        }
        out.innerHTML = html + `</tbody></table></div>`;
    } catch (e) { out.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(e.message)}</div>`; }
}

/* ----- Вкладка «Изменения» ----- */
function bomChangesTable(rows, showProduct) {
    if (!rows.length) return `<div class="empty-state py-4"><i class="fas fa-history"></i><p>Изменений не зарегистрировано</p></div>`;
    let html = `<div class="table-responsive"><table class="data-table bom-changes-table"><thead><tr><th>Номер</th><th>Дата</th>${showProduct ? '<th>Изделие</th>' : ''}<th>Тип</th><th>Компонент</th><th>Было</th><th>Стало</th><th>Описание / автор</th></tr></thead><tbody>`;
    for (const c of rows) {
        html += `<tr><td class="text-nowrap fw-semibold">${escapeHtml(c.номер)}</td><td class="text-nowrap">${formatDate(c.дата)}</td>
            ${showProduct ? `<td><a href="#" onclick="event.preventDefault(); bomOpenProduct(${c.изделие_id}, 'changes')">${escapeHtml(c.изделие || '—')}</a></td>` : ''}
            <td><span class="badge bg-${BOM_CHANGE_COLORS[c.тип_изменения] || 'secondary'} ${c.тип_изменения === 'ЗАМЕНА' ? 'text-dark' : ''}">${escapeHtml(c.тип_изменения.replace('_', ' ').toLowerCase())}</span></td>
            <td>${escapeHtml(c.компонент || '—')}</td><td class="small">${escapeHtml(c.старое_значение || '—')}</td><td class="small">${escapeHtml(c.новое_значение || '—')}</td>
            <td class="bom-desc">${escapeHtml(c.описание)}<div class="small text-muted"><i class="fas fa-user-pen"></i> ${escapeHtml(c.автор || '—')}</div></td></tr>`;
    }
    return html + `</tbody></table></div>`;
}

async function bomChangesHtml(productId) {
    const rows = await apiRequest(`/bom/changes?product_id=${productId}`);
    return bomChangesTable(rows, false);
}

/* ----- Вкладка «Применяемость» ----- */
async function bomWhereUsedHtml(p) {
    const rows = await apiRequest(`/bom/products/${p.id}/where-used`);
    if (!rows.length) return `<div class="empty-state py-4"><i class="fas fa-diagram-project"></i><p>Изделие не входит в состав других изделий</p></div>`;
    return `<div class="small text-muted mb-2">Изделие «${escapeHtml(p.наименование)}» непосредственно входит в спецификации:</div>
    <div class="table-responsive"><table class="data-table"><thead><tr><th>Изделие-родитель</th><th>Артикул</th><th class="text-end">Расход</th><th class="text-end">Для кол-ва</th><th>ЕИ</th><th>Вид позиции</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td><a href="#" onclick="event.preventDefault(); bomSelectProduct(${r.изделие_id}, 'spec')">${escapeHtml(r.изделие)}</a></td><td>${escapeHtml(r.артикул || '—')}</td><td class="text-end">${bomNum(r.расход)}</td><td class="text-end">${bomNum(r.для_количества)}</td><td>${escapeHtml(r.ед_изм || '—')}</td><td>${escapeHtml(r.вид_позиции.toLowerCase())}</td></tr>`).join('')}
    </tbody></table></div>`;
}

/* ============================== Модальные окна (администратор) ============================== */
function bomAuthorField(id = 'bomAuthor') {
    return `<div class="col-md-6 form-field"><label class="form-label" for="${id}">Автор изменения</label><input type="text" class="form-control" id="${id}" value="Администратор" maxlength="100"></div>`;
}

function bomShowPositionModal(productId, item = null, presetCompId = null, presetQty = null, presetPer = null, presetUnit = null) {
    const parent = bomState.products.find(p => p.id === productId) || {};
    const isMod = !!parent.является_модификацией;
    const edit = !!item;
    const kinds = Object.keys(BOM_KIND_TITLES);
    const options = kinds.map(k => {
        const list = bomState.products.filter(p => p.тип_изделия === k && p.id !== productId);
        if (!list.length) return '';
        return `<optgroup label="${BOM_KIND_TITLES[k]}">${list.map(p => `<option value="${p.id}" data-unit="${p.ед_изм_id || ''}" ${(presetCompId || item?.компонент_id) === p.id ? 'selected' : ''}>${escapeHtml(p.наименование)} (${escapeHtml(p.артикул || '—')})</option>`).join('')}</optgroup>`;
    }).join('');
    const replace = !!presetCompId;
    const title = edit ? `Изменение позиции: ${item.компонент}` : replace ? 'Замена нормы унаследованного компонента' : 'Добавление позиции спецификации';
    const body = `
        <div class="alert alert-light border small mb-3"><i class="fas fa-info-circle text-primary"></i>
            Изделие: <b>${escapeHtml(parent.наименование || '')}</b>.
            ${isMod ? 'Это модификация: позиция будет сохранена как собственное отличие (добавление или замена унаследованного компонента).' : 'Норма расхода задаётся на указанное количество изделия-родителя (поле «Для количества»).'}
        </div>
        <div class="row g-3">
            <div class="col-12 form-field"><label class="form-label" for="bomComp">Компонент *</label>
                <select class="form-select" id="bomComp" ${edit || replace ? 'disabled' : ''}><option value="">— выберите изделие —</option>${options}</select></div>
            <div class="col-md-4 form-field"><label class="form-label" for="bomQty">Расход *</label><input type="number" class="form-control" id="bomQty" min="0" step="any" value="${item?.расход ?? presetQty ?? ''}"></div>
            <div class="col-md-4 form-field"><label class="form-label" for="bomPer">Для количества *</label><input type="number" class="form-control" id="bomPer" min="0" step="any" value="${item?.для_количества ?? presetPer ?? 1}"><div class="form-hint">напр. 1000 — норма на 1000 шт.</div></div>
            <div class="col-md-4 form-field"><label class="form-label" for="bomUnit">ЕИ нормы</label><select class="form-select" id="bomUnit">${bomUnitOptions(item?.ед_изм_id ?? presetUnit)}</select></div>
            ${isMod ? '' : `<div class="col-12"><div class="form-check"><input class="form-check-input" type="checkbox" id="bomBase" ${!item || item.флаг_базы ? 'checked' : ''}>
                <label class="form-check-label" for="bomBase">Флаг базы — позиция входит в базовую часть спецификации и наследуется модификациями</label></div></div>`}
            <div class="col-12 form-field"><label class="form-label" for="bomNote">Примечание</label><input type="text" class="form-control" id="bomNote" value="${escapeHtml(item?.примечание || '')}"></div>
            <div class="col-md-6 form-field"><label class="form-label" for="bomReason">Причина изменения</label><input type="text" class="form-control" id="bomReason" placeholder="Номер извещения, обоснование"></div>
            ${bomAuthorField()}
        </div>`;
    const footer = `<button class="btn btn-primary" onclick="bomSavePosition(this, ${productId}, ${edit ? item.позиция_id : 'null'})"><i class="fas fa-save"></i> Сохранить</button>`;
    const m = bomModal(title, body, footer);
    const sel = m.querySelector('#bomComp');
    sel.addEventListener('change', () => {
        const u = sel.selectedOptions[0]?.dataset.unit;
        if (u) m.querySelector('#bomUnit').value = u;
    });
}

async function bomSavePosition(btn, productId, positionId) {
    const compId = Number(document.getElementById('bomComp').value);
    if (!positionId && !compId) { bomFieldError('bomComp', 'Выберите компонент'); return; }
    const qty = bomPositiveNumber('bomQty', 'Расход');
    const per = bomPositiveNumber('bomPer', 'Для количества');
    if (qty == null || per == null) return;
    const unit = document.getElementById('bomUnit').value;
    const baseEl = document.getElementById('bomBase');
    const payload = {
        расход: qty, для_количества: per, ед_изм_id: unit ? Number(unit) : null,
        флаг_базы: baseEl ? baseEl.checked : null,
        примечание: document.getElementById('bomNote').value.trim() || null,
        причина: document.getElementById('bomReason').value.trim() || null,
        автор: document.getElementById('bomAuthor').value.trim() || null,
    };
    try {
        let r;
        if (positionId) r = await apiRequest(`/bom/positions/${positionId}`, 'PUT', payload);
        else r = await apiRequest(`/bom/products/${productId}/spec`, 'POST', { компонент_id: compId, ...payload });
        showToast(r.message || 'Сохранено');
        bomCloseModal(btn);
        bomState.products = await apiRequest('/bom/products');
        bomSelectProduct(productId, 'spec');
    } catch (e) { showToast(e.message, 'error'); }
}

async function bomDeletePosition(positionId, name) {
    if (!confirm(`Удалить компонент «${name}» из спецификации?`)) return;
    try {
        const r = await apiRequest(`/bom/positions/${positionId}?автор=${encodeURIComponent('Администратор')}`, 'DELETE');
        showToast(r.message || 'Позиция удалена');
        bomState.products = await apiRequest('/bom/products');
        bomSelectProduct(bomState.selectedId, 'spec');
    } catch (e) { showToast(e.message, 'error'); }
}

async function bomRestorePosition(positionId) {
    try {
        await apiRequest(`/bom/positions/${positionId}?автор=${encodeURIComponent('Администратор')}`, 'DELETE');
        showToast('Компонент восстановлен по базовому изделию');
        bomSelectProduct(bomState.selectedId, 'spec');
    } catch (e) { showToast(e.message, 'error'); }
}

function bomShowExcludeModal(productId, compId, compName) {
    const body = `<p>Исключить унаследованный компонент <b>«${escapeHtml(compName)}»</b> из спецификации модификации?
        Базовое изделие при этом не изменится.</p>
        <div class="row g-3"><div class="col-md-6 form-field"><label class="form-label" for="bomReason">Причина *</label><input type="text" class="form-control" id="bomReason"></div>${bomAuthorField()}</div>`;
    bomModal('Исключение компонента', body,
        `<button class="btn btn-danger" onclick="bomExclude(this, ${productId}, ${compId})"><i class="fas fa-ban"></i> Исключить</button>`, '');
}

async function bomExclude(btn, productId, compId) {
    const reason = document.getElementById('bomReason').value.trim();
    if (!reason) { bomFieldError('bomReason', 'Укажите причину исключения'); return; }
    try {
        const r = await apiRequest(`/bom/products/${productId}/exclude`, 'POST',
            { компонент_id: compId, причина: reason, автор: document.getElementById('bomAuthor').value.trim() || null });
        showToast(r.message);
        bomCloseModal(btn);
        bomSelectProduct(productId, 'spec');
    } catch (e) { showToast(e.message, 'error'); }
}

function bomShowModificationModal(baseId) {
    const base = bomState.products.find(p => p.id === baseId) || {};
    const body = `
        <div class="alert alert-light border small"><i class="fas fa-code-branch text-primary"></i>
            Модификация наследует базовую часть спецификации изделия <b>«${escapeHtml(base.наименование || '')}»</b>.
            После создания можно добавить, заменить или исключить компоненты.</div>
        <div class="row g-3">
            <div class="col-md-8 form-field"><label class="form-label" for="bomModName">Наименование модификации *</label><input type="text" class="form-control" id="bomModName" maxlength="200" value="${escapeHtml((base.наименование || '') + ' — модификация')}"></div>
            <div class="col-md-4 form-field"><label class="form-label" for="bomModSku">Артикул</label><input type="text" class="form-control" id="bomModSku" maxlength="50" value="${escapeHtml((base.артикул || '') + '-M1')}"></div>
            <div class="col-md-6 form-field"><label class="form-label" for="bomReason">Основание</label><input type="text" class="form-control" id="bomReason" placeholder="Заказ, извещение, причина"></div>
            ${bomAuthorField()}
        </div>`;
    bomModal('Создание модификации', body,
        `<button class="btn btn-primary" onclick="bomCreateModification(this, ${baseId})"><i class="fas fa-code-branch"></i> Создать</button>`);
}

async function bomCreateModification(btn, baseId) {
    const name = document.getElementById('bomModName').value.trim();
    if (!name) { bomFieldError('bomModName', 'Укажите наименование'); return; }
    try {
        const r = await apiRequest(`/bom/products/${baseId}/modifications`, 'POST', {
            наименование: name, артикул: document.getElementById('bomModSku').value.trim() || null,
            причина: document.getElementById('bomReason').value.trim() || null,
            автор: document.getElementById('bomAuthor').value.trim() || null,
        });
        showToast(r.message);
        bomCloseModal(btn);
        bomState.products = await apiRequest('/bom/products');
        bomSelectProduct(r.product_id, 'spec');
    } catch (e) { showToast(e.message, 'error'); }
}

function bomShowChangeModal(productId) {
    const p = bomState.products.find(x => x.id === productId) || {};
    const body = `<div class="row g-3">
        <div class="col-12"><div class="small text-muted">Изделие: <b>${escapeHtml(p.наименование || '')}</b></div></div>
        <div class="col-12 form-field"><label class="form-label" for="bomChangeDesc">Описание изменения *</label><textarea class="form-control" id="bomChangeDesc" rows="3" placeholder="Что, почему и на основании чего изменено"></textarea></div>
        ${bomAuthorField()}</div>`;
    bomModal('Регистрация изменения спецификации', body,
        `<button class="btn btn-primary" onclick="bomRegisterChange(this, ${productId})"><i class="fas fa-file-signature"></i> Зарегистрировать</button>`);
}

async function bomRegisterChange(btn, productId) {
    const d = document.getElementById('bomChangeDesc').value.trim();
    if (!d) { bomFieldError('bomChangeDesc', 'Опишите изменение'); return; }
    try {
        const r = await apiRequest(`/bom/products/${productId}/changes`, 'POST', { описание: d, автор: document.getElementById('bomAuthor').value.trim() || null });
        showToast(r.message);
        bomCloseModal(btn);
        bomSelectProduct(productId, 'changes');
    } catch (e) { showToast(e.message, 'error'); }
}

function bomShowKindModal(productId) {
    const p = bomState.products.find(x => x.id === productId) || {};
    const body = `<div class="row g-3">
        <div class="col-md-7 form-field"><label class="form-label" for="bomKindSel">Тип изделия *</label>
            <select class="form-select" id="bomKindSel">${Object.entries(BOM_KIND_TITLES).map(([k, t]) => `<option value="${k}" ${p.тип_изделия === k ? 'selected' : ''}>${t}</option>`).join('')}</select>
            <div class="form-hint">Материал не может иметь собственную спецификацию</div></div>
        <div class="col-md-5 form-field"><label class="form-label" for="bomKindUnit">Основная ЕИ</label><select class="form-select" id="bomKindUnit">${bomUnitOptions(p.ед_изм_id)}</select></div>
    </div>`;
    bomModal(`Свойства изделия: ${p.наименование || ''}`, body,
        `<button class="btn btn-primary" onclick="bomSaveKind(this, ${productId})"><i class="fas fa-save"></i> Сохранить</button>`, '');
}

async function bomSaveKind(btn, productId) {
    const unit = document.getElementById('bomKindUnit').value;
    try {
        const r = await apiRequest(`/bom/products/${productId}/kind`, 'PUT', { тип_изделия: document.getElementById('bomKindSel').value, ед_изм_id: unit ? Number(unit) : null });
        showToast(r.message);
        bomCloseModal(btn);
        bomState.products = await apiRequest('/bom/products');
        bomSelectProduct(productId);
    } catch (e) { showToast(e.message, 'error'); }
}

/* ============================== Страница «Модификации» ============================== */
async function loadBomModifications() {
    showLoading();
    try {
        await bomLoadRefs();
        const mods = await apiRequest('/bom/modifications');
        const bases = bomState.products.filter(p => p.модификаций > 0);
        let html = `<div class="page-header"><h1><i class="fas fa-code-branch"></i> Базовые изделия и модификации</h1>
            <p class="subtitle">Модификация наследует базовую часть спецификации и хранит только отличия</p></div>
        <div class="card-panel"><div class="card-panel-header"><span>Модификации (${mods.length})</span></div><div class="card-panel-body">`;
        if (!mods.length) html += `<div class="empty-state"><i class="fas fa-code-branch"></i><p>Модификаций пока нет</p></div>`;
        else {
            html += `<div class="table-responsive"><table class="data-table"><thead><tr><th>Модификация</th><th>Артикул</th><th>Базовое изделие</th><th class="text-center">Унаследовано</th><th class="text-center">Добавлено</th><th class="text-center">Заменено</th><th class="text-center">Исключено</th><th></th></tr></thead><tbody>`;
            for (const m of mods) {
                html += `<tr><td class="fw-semibold">${escapeHtml(m.наименование)}</td><td>${escapeHtml(m.артикул || '—')}</td>
                    <td><a href="#" onclick="event.preventDefault(); bomOpenProduct(${m.базовое_изделие_id})">${escapeHtml(m.базовое_изделие)}</a></td>
                    <td class="text-center">${m.унаследовано}</td><td class="text-center text-success fw-bold">+${m.добавлено}</td>
                    <td class="text-center text-warning fw-bold">${m.заменено}</td><td class="text-center text-danger fw-bold">−${m.исключено}</td>
                    <td class="actions"><button class="btn btn-sm btn-outline-primary" onclick="bomOpenProduct(${m.id})"><i class="fas fa-eye"></i> Спецификация</button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="bomOpenProduct(${m.id}, 'calc')"><i class="fas fa-calculator"></i></button></td></tr>`;
            }
            html += `</tbody></table></div>`;
        }
        html += `</div></div>`;
        if (bases.length) {
            html += `<div class="card-panel mt-3"><div class="card-panel-header"><span>Базовые изделия, имеющие модификации</span></div><div class="card-panel-body"><div class="d-flex flex-wrap gap-2">
                ${bases.map(b => `<a href="#" class="bom-chip" onclick="event.preventDefault(); bomOpenProduct(${b.id})">${escapeHtml(b.наименование)} <span class="badge bg-primary ms-1">${b.модификаций}</span></a>`).join('')}
            </div></div></div>`;
        }
        document.getElementById('content').innerHTML = html;
    } catch (e) { showError(e.message); }
}

/* ============================== Страница «Журнал изменений» ============================== */
async function loadBomChanges() {
    showLoading();
    try {
        await bomLoadRefs();
        const types = ['ДОБАВЛЕНИЕ', 'ЗАМЕНА', 'ИЗМЕНЕНИЕ_НОРМЫ', 'УДАЛЕНИЕ', 'ИСКЛЮЧЕНИЕ', 'ВОССТАНОВЛЕНИЕ', 'МОДИФИКАЦИЯ', 'ПРОЧЕЕ'];
        const withSpec = bomState.products.filter(p => p.тип_изделия !== 'МАТЕРИАЛ');
        document.getElementById('content').innerHTML = `
        <div class="page-header"><h1><i class="fas fa-history"></i> Журнал изменений спецификаций</h1>
            <p class="subtitle">История изменений: что, когда, кем и почему было изменено</p></div>
        <div class="card-panel mb-3"><div class="card-panel-body"><div class="row g-2 align-items-end">
            <div class="col-md-4 form-field"><label class="form-label" for="bchProduct">Изделие</label><select class="form-select" id="bchProduct"><option value="">Все изделия</option>${withSpec.map(p => `<option value="${p.id}">${escapeHtml(p.наименование)}</option>`).join('')}</select></div>
            <div class="col-md-2 form-field"><label class="form-label" for="bchType">Тип</label><select class="form-select" id="bchType"><option value="">Все</option>${types.map(t => `<option value="${t}">${t.replace('_', ' ').toLowerCase()}</option>`).join('')}</select></div>
            <div class="col-md-2 form-field"><label class="form-label" for="bchFrom">Дата с</label><input type="date" class="form-control" id="bchFrom"></div>
            <div class="col-md-2 form-field"><label class="form-label" for="bchTo">Дата по</label><input type="date" class="form-control" id="bchTo"></div>
            <div class="col-md-2"><button class="btn btn-primary w-100" onclick="bomApplyChangesFilter()"><i class="fas fa-filter"></i> Применить</button></div>
        </div></div></div>
        <div class="card-panel"><div class="card-panel-header"><span>Изменения</span><span class="text-muted small" id="bchCount"></span></div><div class="card-panel-body" id="bchResult"></div></div>`;
        await bomApplyChangesFilter();
    } catch (e) { showError(e.message); }
}

async function bomApplyChangesFilter() {
    const params = new URLSearchParams();
    const pr = document.getElementById('bchProduct').value, t = document.getElementById('bchType').value;
    const f = document.getElementById('bchFrom').value, to = document.getElementById('bchTo').value;
    if (f && to && f > to) { bomFieldError('bchTo', 'Дата «по» раньше даты «с»'); return; }
    if (pr) params.set('product_id', pr);
    if (t) params.set('kind', t);
    if (f) params.set('date_from', f + 'T00:00:00');
    if (to) params.set('date_to', to + 'T23:59:59');
    const rows = await apiRequest('/bom/changes?' + params.toString());
    document.getElementById('bchCount').textContent = `найдено: ${rows.length}`;
    document.getElementById('bchResult').innerHTML = bomChangesTable(rows, true);
}

/* ============================== Справочник единиц измерения ============================== */
async function loadBomUnits() {
    showLoading();
    try {
        await bomLoadRefs(true);
        let html = `<div class="page-header"><h1><i class="fas fa-ruler-combined"></i> Единицы измерения</h1><p class="subtitle">Справочник ЕИ норм расхода (коды по ОКЕИ)</p></div>
        <div class="card-panel"><div class="card-panel-header"><span>Единицы измерения (${bomState.units.length})</span>
            ${BOM_READONLY ? '' : `<button class="btn btn-sm btn-success" onclick="bomShowUnitModal()"><i class="fas fa-plus"></i> Добавить</button>`}</div>
        <div class="card-panel-body"><div class="table-responsive"><table class="data-table"><thead><tr><th>ID</th><th>Код ОКЕИ</th><th>Наименование</th><th>Обозначение</th>${BOM_READONLY ? '' : '<th>Действия</th>'}</tr></thead><tbody>`;
        for (const u of bomState.units) {
            html += `<tr><td>${u.id}</td><td>${escapeHtml(u.код)}</td><td>${escapeHtml(u.наименование)}</td><td><b>${escapeHtml(u.обозначение)}</b></td>
            ${BOM_READONLY ? '' : `<td class="actions"><button class="btn btn-sm btn-outline-primary" onclick='bomShowUnitModal(${JSON.stringify(u)})'><i class="fas fa-edit"></i></button>
            <button class="btn btn-sm btn-outline-danger" onclick="bomDeleteUnit(${u.id})"><i class="fas fa-trash"></i></button></td>`}</tr>`;
        }
        document.getElementById('content').innerHTML = html + `</tbody></table></div></div></div>`;
    } catch (e) { showError(e.message); }
}

function bomShowUnitModal(u = null) {
    const body = `<div class="row g-3">
        <div class="col-md-3 form-field"><label class="form-label" for="bomUCode">Код *</label><input type="text" class="form-control" id="bomUCode" maxlength="10" value="${escapeHtml(u?.код || '')}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="bomUName">Наименование *</label><input type="text" class="form-control" id="bomUName" maxlength="50" value="${escapeHtml(u?.наименование || '')}"></div>
        <div class="col-md-3 form-field"><label class="form-label" for="bomUSym">Обозначение *</label><input type="text" class="form-control" id="bomUSym" maxlength="10" value="${escapeHtml(u?.обозначение || '')}"></div></div>`;
    bomModal(u ? 'Изменение единицы измерения' : 'Новая единица измерения', body,
        `<button class="btn btn-primary" onclick="bomSaveUnit(this, ${u ? u.id : 'null'})"><i class="fas fa-save"></i> Сохранить</button>`, '');
}

async function bomSaveUnit(btn, id) {
    const data = { код: document.getElementById('bomUCode').value.trim(), наименование: document.getElementById('bomUName').value.trim(), обозначение: document.getElementById('bomUSym').value.trim() };
    let ok = true;
    if (!data.код) { bomFieldError('bomUCode', 'Обязательное поле'); ok = false; }
    if (!data.наименование) { bomFieldError('bomUName', 'Обязательное поле'); ok = false; }
    if (!data.обозначение) { bomFieldError('bomUSym', 'Обязательное поле'); ok = false; }
    if (!ok) return;
    try {
        const r = id ? await apiRequest(`/bom/units/${id}`, 'PUT', data) : await apiRequest('/bom/units', 'POST', data);
        showToast(r.message);
        bomCloseModal(btn);
        loadBomUnits();
    } catch (e) { showToast(e.message, 'error'); }
}

async function bomDeleteUnit(id) {
    if (!confirm('Удалить единицу измерения?')) return;
    try { await apiRequest(`/bom/units/${id}`, 'DELETE'); showToast('Единица измерения удалена'); loadBomUnits(); }
    catch (e) { showToast(e.message, 'error'); }
}
