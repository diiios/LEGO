/** Интерфейс работы 5: спецификации изделий */

let bomTab = 'spec';   // какая вкладка открыта сейчас

async function loadBomPage() {
    showLoading();
    try {
        const products = await apiRequest('/products');
        const options = products.map(p =>
            `<option value="${p.id}">${escapeHtml(p.наименование)} (${escapeHtml(p.артикул || '—')})</option>`
        ).join('');

        document.getElementById('content').innerHTML = `
            <div class="card">
                <div class="card-header"><i class="fas fa-sitemap"></i> Спецификация изделия</div>
                <div class="card-body">
                    <label class="form-label">Изделие</label>
                    <select id="bomProduct" class="form-select mb-3" onchange="renderBomTab()">
                        <option value="">— выберите изделие —</option>
                        ${options}
                    </select>

                    <ul class="nav nav-tabs mb-3">
                        <li class="nav-item"><a class="nav-link active" href="#" data-tab="spec"  onclick="showBomTab(event, 'spec')">Состав</a></li>
                        <li class="nav-item"><a class="nav-link"        href="#" data-tab="tree"  onclick="showBomTab(event, 'tree')">Дерево</a></li>
                        <li class="nav-item"><a class="nav-link"        href="#" data-tab="calc"  onclick="showBomTab(event, 'calc')">Расчёт норм</a></li>
                        <li class="nav-item"><a class="nav-link"        href="#" data-tab="mods"  onclick="showBomTab(event, 'mods')">Модификации</a></li>
                        <li class="nav-item"><a class="nav-link"        href="#" data-tab="log"   onclick="showBomTab(event, 'log')">Журнал</a></li>
                    </ul>

                    <div id="bomTable"></div>
                </div>
            </div>`;
        bomTab = 'spec';
    } catch (e) {
        showError(e.message);
    }
}

// ---------- Вкладки ----------
function showBomTab(ev, tab) {
    ev.preventDefault();
    activateBomTab(tab);
    renderBomTab();
}

// Подсветить вкладку и запомнить её (можно вызывать из кода, без клика)
function activateBomTab(tab) {
    document.querySelectorAll('.nav-tabs .nav-link').forEach(a =>
        a.classList.toggle('active', a.dataset.tab === tab)
    );
    bomTab = tab;
}

// Выбрать другое изделие в списке и открыть нужную вкладку
function openBomProduct(productId, tab = 'spec') {
    document.getElementById('bomProduct').value = productId;
    activateBomTab(tab);
    renderBomTab();
}

function renderBomTab() {
    const productId = Number(document.getElementById('bomProduct').value);
    const box = document.getElementById('bomTable');
    if (!productId) {
        box.innerHTML = '<p class="text-muted">Выберите изделие.</p>';
        return;
    }
    if (bomTab === 'spec') loadBomTable();
    else if (bomTab === 'tree') loadBomTree();
    else if (bomTab === 'calc') loadBomCalc();
    else if (bomTab === 'mods') loadBomMods();
    else if (bomTab === 'log') loadBomLog();
    else box.innerHTML = '<p class="text-muted">Эта вкладка будет на следующих шагах.</p>';
}

// ---------- Дерево состава (FIND_BOM) ----------
function loadBomTree() {
    // поле «количество» и место под само дерево
    document.getElementById('bomTable').innerHTML = `
        <div class="d-flex align-items-center gap-2 mb-3">
            <label for="bomTreeQty" class="form-label mb-0">Количество изделий:</label>
            <input id="bomTreeQty" type="number" min="1" step="any" value="1"
                   class="form-control" style="width: 120px" onchange="drawBomTree()">
        </div>
        <div id="bomTreeBody"></div>`;
    drawBomTree();
}

async function drawBomTree() {
    const productId = Number(document.getElementById('bomProduct').value);
    const qty = Number(document.getElementById('bomTreeQty').value) || 1;
    const body = document.getElementById('bomTreeBody');
    body.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        const tree = await apiRequest(`/products/${productId}/bom/tree?qty=${qty}`);
        if (tree.строки.length === 0) {
            body.innerHTML = '<p class="text-muted">Состав пуст.</p>';
            return;
        }

        let html = `<table class="table table-sm table-hover">
            <thead><tr>
                <th>Компонент</th><th>Артикул</th><th>На 1</th><th>На ${qty}</th><th>ЕИ</th><th></th>
            </tr></thead><tbody>
            <tr><td colspan="6"><b>${escapeHtml(tree.изделие)}</b></td></tr>`;   // корень дерева

        for (const r of tree.строки) {
            const indent = r.уровень * 24;                   // отступ по уровню вложенности
            const marks = [];
            if (r.из_базы) marks.push('<span class="badge bg-secondary">из базы</span>');
            if (r.лист)    marks.push('<span class="badge bg-success">лист</span>');

            html += `<tr>
                <td style="padding-left: ${indent}px">└─ ${escapeHtml(r.компонент)}</td>
                <td><code>${escapeHtml(r.артикул || '—')}</code></td>
                <td>${r.кол_на_1}</td>
                <td><b>${r.кол_на_N}</b></td>
                <td>${escapeHtml(r.ед_изм || '—')}</td>
                <td>${marks.join(' ')}</td>
            </tr>`;
        }
        html += '</tbody></table>';

        if (tree.предупреждения.length > 0) {
            html += `<div class="alert alert-warning">${tree.предупреждения.map(escapeHtml).join('<br>')}</div>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

// ---------- Расчёт сводных норм (CALC_BOM) ----------
async function loadBomCalc() {
    const box = document.getElementById('bomTable');
    box.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        const cats = await apiRequest('/categories');     // все узлы классификатора

        // Собираем дерево классов: для каждого родителя — список детей
        const children = {};
        for (const c of cats) {
            const key = c.parent_id ?? 'root';            // ?? — «если null, то 'root'»
            (children[key] = children[key] || []).push(c);
        }
        // Обход в глубину: каждый уровень сдвигаем двумя пробелами
        function options(parentKey, depth) {
            let html = '';
            for (const c of children[parentKey] || []) {
                const pad = '&nbsp;&nbsp;'.repeat(depth);
                html += `<option value="${c.id}">${pad}${escapeHtml(c.name)}</option>`;
                html += options(c.id, depth + 1);         // рекурсия: дети этого узла
            }
            return html;
        }

        box.innerHTML = `
            <div class="row g-2 align-items-end mb-3">
                <div class="col-auto">
                    <label for="bomCalcQty" class="form-label">Количество изделий</label>
                    <input id="bomCalcQty" type="number" min="1" step="any" value="10"
                           class="form-control" style="width: 120px" onchange="drawBomCalc()">
                </div>
                <div class="col">
                    <label for="bomCalcClass" class="form-label">Класс компонентов</label>
                    <select id="bomCalcClass" class="form-select" onchange="drawBomCalc()">
                        <option value="">— все компоненты —</option>
                        ${options('root', 0)}
                    </select>
                </div>
            </div>
            <div id="bomCalcBody"></div>`;
        drawBomCalc();
    } catch (e) {
        box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function drawBomCalc() {
    const productId = Number(document.getElementById('bomProduct').value);
    const qty = Number(document.getElementById('bomCalcQty').value) || 1;
    const classId = document.getElementById('bomCalcClass').value;
    const body = document.getElementById('bomCalcBody');
    body.innerHTML = '<p class="text-muted">Считаем...</p>';

    let url = `/products/${productId}/bom/calc?qty=${qty}`;
    if (classId) url += `&class_id=${classId}`;            // класс — только если выбран

    try {
        const res = await apiRequest(url);
        if (res.строки.length === 0) {
            body.innerHTML = '<p class="text-muted">Нет компонентов' +
                (res.класс ? ` класса «${escapeHtml(res.класс)}»` : '') + '.</p>';
            return;
        }

        let html = `<p class="mb-2">Сводные нормы на <b>${res.количество}</b> шт. «${escapeHtml(res.изделие)}»` +
                   (res.класс ? `, класс «${escapeHtml(res.класс)}» и подклассы` : '') + ':</p>';
        html += `<table class="table table-bordered table-sm">
            <thead><tr>
                <th>Компонент</th><th>Артикул</th><th>Класс</th>
                <th>На 1</th><th>На ${res.количество}</th><th>ЕИ</th><th>Вхождений в дерево</th>
            </tr></thead><tbody>`;
        for (const r of res.строки) {
            html += `<tr>
                <td>${escapeHtml(r.компонент)}</td>
                <td><code>${escapeHtml(r.артикул || '—')}</code></td>
                <td>${escapeHtml(r.класс || '—')}</td>
                <td>${r.кол_на_1}</td>
                <td><b>${r.кол_на_N}</b></td>
                <td>${escapeHtml(r.ед_изм || '—')}</td>
                <td>${r.вхождений}</td>
            </tr>`;
        }
        html += '</tbody></table>';

        if (res.предупреждения.length > 0) {
            html += `<div class="alert alert-warning">${res.предупреждения.map(escapeHtml).join('<br>')}</div>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

// ---------- Модификации ----------
async function loadBomMods() {
    const productId = Number(document.getElementById('bomProduct').value);
    const box = document.getElementById('bomTable');
    box.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        // два запроса параллельно: кто база у этого изделия + его модификации
        const [spec, mods] = await Promise.all([
            apiRequest(`/products/${productId}/bom/effective`),
            apiRequest(`/products/${productId}/modifications`),
        ]);
        let html = '';

        // 1. Если выбранное изделие само является модификацией
        if (spec.базовое_изделие_id) {
            html += `<div class="alert alert-info d-flex justify-content-between align-items-center">
                <span>Это модификация изделия «${escapeHtml(spec.базовое_изделие)}».</span>
                <button class="btn btn-sm btn-outline-primary"
                        onclick="openBomProduct(${spec.базовое_изделие_id})">Перейти к базовому</button>
            </div>`;
        }

        // 2. Список модификаций этого изделия
        html += '<h6>Модификации этого изделия</h6>';
        if (mods.length === 0) {
            html += '<p class="text-muted">Модификаций нет.</p>';
        } else {
            html += `<table class="table table-bordered table-sm">
                <thead><tr><th>Наименование</th><th>Артикул</th><th>Своих строк</th><th>Своих модификаций</th><th></th></tr></thead><tbody>`;
            for (const m of mods) {
                html += `<tr>
                    <td>${escapeHtml(m.наименование)}</td>
                    <td><code>${escapeHtml(m.артикул || '—')}</code></td>
                    <td>${m.своих_строк}</td>
                    <td>${m.модификаций}</td>
                    <td><button class="btn btn-sm btn-primary" onclick="openBomProduct(${m.id})">Открыть</button></td>
                </tr>`;
            }
            html += '</tbody></table>';
        }

        // 3. Форма создания
        html += `<div class="bom-edit"><h6 class="mt-4">Создать модификацию</h6>
            <div class="row g-2 align-items-end">
                <div class="col">
                    <label class="form-label">Наименование</label>
                    <input id="bomModName" class="form-control" value="${escapeHtml(spec.изделие)} — модификация">
                </div>
                <div class="col-3">
                    <label class="form-label">Артикул</label>
                    <input id="bomModSku" class="form-control" placeholder="необязательно">
                </div>
                <div class="col-auto">
                    <button class="btn btn-success" onclick="createBomModification()">
                        <i class="fas fa-plus"></i> Создать</button>
                </div>
            </div>
            <small class="text-muted">Строки базового изделия не копируются: модификация получает их из базы,
                а хранит только свои отличия.</small></div>`;

        box.innerHTML = html;
    } catch (e) {
        box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function createBomModification() {
    const productId = Number(document.getElementById('bomProduct').value);
    const name = document.getElementById('bomModName').value.trim();
    const sku = document.getElementById('bomModSku').value.trim();
    try {
        const res = await apiRequest(`/products/${productId}/modifications`, 'POST', {
            наименование: name,
            артикул: sku || null,
        });
        // новое изделие добавляем в выпадающий список, чтобы его можно было выбрать
        document.getElementById('bomProduct').add(new Option(`${name} (${sku || '—'})`, res.product_id));
        showToast('Модификация создана');
        openBomProduct(res.product_id, 'spec');            // сразу открыть её состав
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ---------- Журнал изменений ----------
const BOM_ACTION_COLORS = {                // цвет значка для каждого вида записи
    'ДОБАВЛЕНИЕ':  'bg-success',
    'ИЗМЕНЕНИЕ':   'bg-warning text-dark',
    'УДАЛЕНИЕ':    'bg-danger',
    'МОДИФИКАЦИЯ': 'bg-primary',
    'ИЗВЕЩЕНИЕ':   'bg-info text-dark',
};

function formatBomDate(iso) {
    if (!iso) return '—';
    const utc = iso.endsWith('Z') ? iso : iso + 'Z';   // сервер хранит время в UTC
    return new Date(utc).toLocaleString('ru-RU');       // → «30.09.2026, 18:40:12» по местному времени
}

async function loadBomLog() {
    const productId = Number(document.getElementById('bomProduct').value);
    const box = document.getElementById('bomTable');
    box.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        const log = await apiRequest(`/products/${productId}/changes`);

        // 1. Форма ручной записи (REGISTER_CHANGE)
        let html = `
            <div class="card mb-3 bom-edit"><div class="card-body">
                <h6>Зарегистрировать изменение (извещение)</h6>
                <input id="bomLogText" class="form-control mb-2"
                       placeholder="Например: Извещение №2: замена плит по требованию технолога">
                <div class="row g-2">
                    <div class="col"><input id="bomLogWas" class="form-control" placeholder="Было (необязательно)"></div>
                    <div class="col"><input id="bomLogNow" class="form-control" placeholder="Стало (необязательно)"></div>
                    <div class="col-auto">
                        <button class="btn btn-primary" onclick="registerBomChange()">
                            <i class="fas fa-file-signature"></i> Записать</button>
                    </div>
                </div>
            </div></div>`;

        // 2. Сам журнал
        if (log.length === 0) {
            html += '<p class="text-muted">Записей нет.</p>';
        } else {
            html += `<table class="table table-bordered table-sm">
                <thead><tr><th>Дата</th><th>Действие</th><th>Описание</th><th>Было</th><th>Стало</th></tr></thead><tbody>`;
            for (const ch of log) {
                const color = BOM_ACTION_COLORS[ch.действие] || 'bg-secondary';
                html += `<tr>
                    <td class="text-nowrap">${formatBomDate(ch.дата)}</td>
                    <td><span class="badge ${color}">${escapeHtml(ch.действие)}</span></td>
                    <td>${escapeHtml(ch.описание)}</td>
                    <td class="text-muted">${escapeHtml(ch.было || '')}</td>
                    <td>${escapeHtml(ch.стало || '')}</td>
                </tr>`;
            }
            html += '</tbody></table>';
        }
        box.innerHTML = html;
    } catch (e) {
        box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function registerBomChange() {
    const productId = Number(document.getElementById('bomProduct').value);
    const data = {
        описание: document.getElementById('bomLogText').value.trim(),
        было: document.getElementById('bomLogWas').value.trim() || null,
        стало: document.getElementById('bomLogNow').value.trim() || null,
    };
    try {
        await apiRequest(`/products/${productId}/changes`, 'POST', data);
        showToast('Изменение зарегистрировано');
        loadBomLog();                                   // перерисовать журнал — новая запись будет сверху
    } catch (e) {
        showToast(e.message, 'error');                  // например, «Опишите изменение»
    }
}

// ---------- Таблица состава ----------
async function loadBomTable() {
    const productId = Number(document.getElementById('bomProduct').value);
    const box = document.getElementById('bomTable');
    if (!productId) { box.innerHTML = ''; return; }

    box.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        const spec = await apiRequest(`/products/${productId}/bom/effective`);
        let html = '';

        if (spec.базовое_изделие) {
            html += `<div class="alert alert-info">
                Модификация изделия «${escapeHtml(spec.базовое_изделие)}». Серые строки получены из базы.
            </div>`;
        }

        if (spec.строки.length === 0) {
            html += '<p class="text-muted">Состав пуст.</p>';
        } else {
            html += `<table class="table table-bordered">
                <thead><tr>
                    <th>№</th><th>Компонент</th><th>Артикул</th><th>Расход</th>
                    <th>На кол-во</th><th>ЕИ</th><th>Флаг базы</th><th>Источник</th><th class="bom-edit">Действия</th>
                </tr></thead><tbody>`;

            for (const r of spec.строки) {
                const own = r.источник_id === productId;
                // НОВОЕ: кнопки только у своих строк
                const actions = own
                    ? `<button class="btn btn-sm btn-warning" title="Изменить"
                            onclick="showEditBomItemModal(${r.строка_id}, ${r.расход}, ${r.для_количества}, ${r.флаг_базы})">
                            <i class="fas fa-edit"></i></button>
                       <button class="btn btn-sm btn-danger" title="Удалить"
                            onclick="deleteBomItem(${r.строка_id})">
                            <i class="fas fa-trash"></i></button>`
                    : '<span class="text-muted">в базовом изделии</span>';

                html += `<tr class="${own ? '' : 'table-secondary'}">
                    <td>${r.номер}</td>
                    <td>${escapeHtml(r.компонент)}</td>
                    <td><code>${escapeHtml(r.артикул || '—')}</code></td>
                    <td>${r.расход}</td>
                    <td>${r.для_количества}</td>
                    <td>${escapeHtml(r.ед_изм || '—')}</td>
                    <td>${r.флаг_базы ? 'да' : 'нет'}</td>
                    <td>${escapeHtml(r.источник)}</td>
                    <td class="action-buttons bom-edit">${actions}</td>
                </tr>`;
            }
            html += '</tbody></table>';
        }

        if (spec.исключено.length > 0) {
            html += `<div class="alert alert-warning"><i class="fas fa-ban"></i> <b>Исключено из базы:</b>
                     <ul class="mb-0 mt-2">`;
            for (const x of spec.исключено) {
                html += `<li class="mb-1">${escapeHtml(x.компонент)}
                    <button class="btn btn-sm btn-outline-success ms-2 bom-edit" onclick="restoreBomItem(${x.строка_id})">
                        <i class="fas fa-undo"></i> Вернуть</button></li>`;
            }
            html += `</ul></div>`;
        }

        // НОВОЕ: кнопка добавления (есть всегда, даже при пустом составе)
        html += `<button class="btn btn-success bom-edit" onclick="showAddBomItemModal()">
                    <i class="fas fa-plus"></i> Добавить компонент</button>`;

        box.innerHTML = html;
    } catch (e) {
        box.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

// ---------- НОВОЕ: удаление строки ----------
async function deleteBomItem(itemId) {
    if (!confirm('Удалить строку из состава?')) return;       // окно «ОК / Отмена»
    try {
        await apiRequest(`/bom-items/${itemId}`, 'DELETE');
        showToast('Строка удалена');
        loadBomTable();                                        // перерисовать таблицу
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ---------- НОВОЕ: добавление строки ----------
async function showAddBomItemModal() {
    const productId = Number(document.getElementById('bomProduct').value);
    try {
        // два запроса параллельно: список изделий и список ЕИ
        const [products, units] = await Promise.all([apiRequest('/products'), apiRequest('/units')]);

        const productOptions = products
            .filter(p => p.id !== productId)                   // само изделие в свой состав не предлагаем
            .map(p => `<option value="${p.id}">${escapeHtml(p.наименование)} (${escapeHtml(p.артикул || '—')})</option>`)
            .join('');
        const unitOptions = units
            .map(u => `<option value="${u.id}">${escapeHtml(u.обозначение)} — ${escapeHtml(u.имя)}</option>`)
            .join('');

        const body = `
            <label class="form-label">Компонент</label>
            <select id="bomComp" class="form-select mb-2">${productOptions}</select>

            <div class="row">
                <div class="col"><label class="form-label">Расход</label>
                    <input id="bomQty" type="number" step="any" class="form-control mb-2" value="1"></div>
                <div class="col"><label class="form-label">На количество изделия</label>
                    <input id="bomFor" type="number" step="any" class="form-control mb-2" value="1"></div>
                <div class="col"><label class="form-label">ЕИ</label>
                    <select id="bomUnit" class="form-select mb-2">
                        <option value="">— без ЕИ —</option>${unitOptions}</select></div>
            </div>

            <div class="form-check">
                <input id="bomFlag" type="checkbox" class="form-check-input" checked>
                <label class="form-check-label" for="bomFlag">Флаг базы (строку наследуют модификации)</label>
            </div>
            <small class="text-muted">В модификации расход 0 = исключить компонент, полученный из базы.</small>`;

        const footer = `<button class="btn btn-success" onclick="addBomItem()">Добавить</button>`;
        bomModal = showAdminDynamicModal('Добавить компонент в состав', body, footer);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function addBomItem() {
    const productId = Number(document.getElementById('bomProduct').value);
    const unit = document.getElementById('bomUnit').value;
    const data = {
        компонент_id: Number(document.getElementById('bomComp').value),
        расход: Number(document.getElementById('bomQty').value),
        для_количества: Number(document.getElementById('bomFor').value),
        ед_изм_id: unit ? Number(unit) : null,
        флаг_базы: document.getElementById('bomFlag').checked,
    };
    try {
        await apiRequest(`/products/${productId}/bom`, 'POST', data);
        bootstrap.Modal.getInstance(bomModal).hide();          // закрыть окно
        showToast('Компонент добавлен');
        loadBomTable();
    } catch (e) {
        showToast(e.message, 'error');                         // окно остаётся открытым — можно исправить
    }
}

function showEditBomItemModal(itemId, расход, дляКоличества, флагБазы) {
    const body = `
        <div class="row">
            <div class="col"><label class="form-label">Расход</label>
                <input id="bomEditQty" type="number" step="any" class="form-control" value="${расход}"></div>
            <div class="col"><label class="form-label">На количество изделия</label>
                <input id="bomEditFor" type="number" step="any" class="form-control" value="${дляКоличества}"></div>
        </div>
        <div class="form-check mt-3">
            <input id="bomEditFlag" type="checkbox" class="form-check-input" ${флагБазы ? 'checked' : ''}>
            <label class="form-check-label" for="bomEditFlag">Флаг базы (строку наследуют модификации)</label>
        </div>`;
    const footer = `<button class="btn btn-warning" onclick="updateBomItem(${itemId})">Сохранить</button>`;
    bomModal = showAdminDynamicModal('Изменить строку состава', body, footer);
}

async function updateBomItem(itemId) {
    const data = {
        расход: Number(document.getElementById('bomEditQty').value),
        для_количества: Number(document.getElementById('bomEditFor').value),
        флаг_базы: document.getElementById('bomEditFlag').checked,
    };
    try {
        const res = await apiRequest(`/bom-items/${itemId}`, 'PUT', data);
        bootstrap.Modal.getInstance(bomModal).hide();
        showToast(res.message);
        loadBomTable();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ---------- Вернуть компонент, исключённый из базы ----------
async function restoreBomItem(itemId) {
    try {
        await apiRequest(`/bom-items/${itemId}`, 'DELETE');   // удаляем строку «× 0»
        showToast('Компонент возвращён из базового изделия');
        loadBomTable();
    } catch (e) {
        showToast(e.message, 'error');
    }
}