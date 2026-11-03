/**
 * Задание 7 (усложнённый уровень). Заказы на изделия с вариантами исполнения и сложными ограничениями.
 * Разделы: «Типовые изделия» (конфигуратор, ограничения, формула цены), «Библиотека функций», «Заказы».
 * Администратор – конструкторский отдел и отдел сбыта; пользователь – заказчик (формирует заказы и варианты).
 */
const CFG_ADMIN = document.body.dataset.role === 'admin';
let cfgState = { templateId: null, orderId: null, refs: null, proto: null };

function cfgMoney(v) { return v == null ? '—' : Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function cfgNum(v) { return v == null ? '—' : Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 4 }); }
function cfgDate(d) { return d ? new Date(d + 'T00:00:00').toLocaleDateString('ru-RU') : '—'; }
const CFG_KIND = { 'ПРОСТОЕ': ['bg-light text-dark border', 'без конфигурации'], 'ТИПОВОЕ': ['cfg-badge-tpl', 'типовое'], 'ВАРИАНТ': ['cfg-badge-var', 'вариант исполнения'] };
function cfgKindBadge(k) { const [c, t] = CFG_KIND[k] || ['bg-light', k]; return `<span class="badge ${c}">${t}</span>`; }
function cfgStatusBadge(s) { return s === 'СОГЛАСОВАН' ? '<span class="badge bg-success">согласован</span>' : '<span class="badge bg-warning text-dark">черновик</span>'; }

async function cfgRefs(force = false) {
    if (force || !cfgState.refs) cfgState.refs = await apiRequest('/cfg/references');
    return cfgState.refs;
}

/* ---------- дерево выражения (паттерн «Интерпретатор») ---------- */
function cfgTreeHtml(n) {
    const icon = { 'Вызов функции': 'fa-code-branch', 'Параметр': 'fa-sliders-h', 'Константа': 'fa-hashtag', 'Значение перечисления': 'fa-list', 'Аргумент': 'fa-at' }[n.вид] || 'fa-circle';
    return `<li><span class="cfg-node cfg-node-${n.вид === 'Вызов функции' ? 'call' : 'leaf'}" title="${escapeHtml(n.вид + (n.класс ? ' · ' + n.класс : ''))}">
        <i class="fas ${icon}"></i> <b>${escapeHtml(n.текст)}</b>${n.пояснение ? ` <span class="text-muted">${escapeHtml(n.пояснение)}</span>` : ''}</span>
        ${n.дети ? `<ul>${n.дети.map(cfgTreeHtml).join('')}</ul>` : ''}</li>`;
}
function cfgTree(tree) { return `<ul class="cfg-tree">${cfgTreeHtml(tree)}</ul>`; }

/* ---------- поля значений параметров конфигурации ---------- */
function cfgParamInputs(params, values = {}, prefix = 'cv') {
    return `<div class="row g-2">${params.map(p => {
        const v = values[p.id] ?? values[String(p.id)] ?? '';
        const range = p.мин != null || p.макс != null ? `${cfgNum(p.мин)} … ${cfgNum(p.макс)}` : '';
        const input = p.тип === 'ENUM'
            ? `<select class="form-select" id="${prefix}${p.id}"><option value="">— выберите —</option>${p.значения.map(e => `<option value="${e.id}" ${String(e.id) === String(v) ? 'selected' : ''}>${escapeHtml(e.value)}</option>`).join('')}</select>`
            : `<input type="number" class="form-control" id="${prefix}${p.id}" step="${p.тип === 'INTEGER' ? 1 : 'any'}" value="${v}" placeholder="${range}">`;
        return `<div class="col-md-4 form-field"><label class="form-label" for="${prefix}${p.id}"><b>${escapeHtml(p.обозначение)}</b> – ${escapeHtml(p.полное_имя)}${p.ед_изм ? ', ' + escapeHtml(p.ед_изм) : ''}${range ? ` <span class="text-muted small">(${range})</span>` : ''}</label>${input}</div>`;
    }).join('')}</div>`;
}
function cfgReadValues(params, prefix = 'cv') {
    const vals = {};
    for (const p of params) {
        const raw = (document.getElementById(prefix + p.id)?.value || '').replace(',', '.').trim();
        if (raw === '') continue;
        vals[p.id] = Number(raw);
    }
    return vals;
}
function cfgCheckHtml(r) {
    return `<div class="alert ${r.допустимо ? 'alert-success' : 'alert-danger'} py-2 mb-2"><i class="fas ${r.допустимо ? 'fa-circle-check' : 'fa-circle-xmark'}"></i>
            ${r.допустимо ? `Вариант допустим. Цена варианта: <b>${cfgMoney(r.цена)} руб.</b>` : 'Вариант недопустим – нарушены ограничения, отмеченные ✗'}</div>
        <table class="data-table tm-mini"><thead><tr><th>Проверка</th><th>Вид</th><th>Результат</th></tr></thead><tbody>
        ${r.проверки.map(c => `<tr class="${c.результат ? '' : 'cfg-fail'}"><td>${escapeHtml(c.наименование)}</td><td class="small text-muted">${c.вид === 'ПАРАМЕТР' ? 'диапазон / тип' : 'ограничение'}</td>
            <td>${c.результат ? '<span class="text-success fw-bold">✓ выполнено</span>' : `<span class="text-danger fw-bold">✗ ${escapeHtml(c.сообщение || '')}</span>`}</td></tr>`).join('')}
        </tbody></table>`;
}

/* ================================== Типовые изделия ================================== */
async function loadCfgTemplates() {
    showLoading();
    try {
        const list = await apiRequest('/cfg/templates');
        if (!cfgState.templateId || !list.some(t => t.id === cfgState.templateId)) cfgState.templateId = list[0]?.id || null;
        document.getElementById('content').innerHTML = `
        <div class="page-header"><h1><i class="fas fa-sliders"></i> Типовые изделия с конфигуратором</h1>
            <p class="subtitle">Шаблоны изделий: параметры конфигурации, ограничения на их значения, формула цены и варианты исполнения</p></div>
        <div class="row g-3">
            <div class="col-xxl-3 col-lg-4"><div class="card-panel">
                <div class="card-panel-header"><span><i class="fas fa-list"></i> Типовые изделия</span>
                    ${CFG_ADMIN ? `<button class="btn btn-sm btn-success" title="Сделать изделие типовым" onclick="cfgShowMakeTemplate()"><i class="fas fa-plus"></i></button>` : ''}</div>
                <div class="card-panel-body"><div class="bom-product-list">
                ${list.map(t => `<button class="bom-product-item ${t.id === cfgState.templateId ? 'active' : ''}" onclick="cfgState.templateId=${t.id}; loadCfgTemplates()">
                    <span class="bom-product-icon cfg-icon-tpl"><i class="fas fa-sliders"></i></span>
                    <span class="bom-product-text"><span class="bom-product-name">${escapeHtml(t.наименование)}</span>
                    <span class="bom-product-meta">${escapeHtml(t.артикул || '')} · ${t.параметров} пар. · ${t.ограничений} огр. · ${t.вариантов} вар.</span></span></button>`).join('') || '<div class="empty-state py-4"><p>Нет типовых изделий</p></div>'}
                </div></div></div></div>
            <div class="col-xxl-9 col-lg-8"><div id="cfgTplDetail"></div></div>
        </div>`;
        if (cfgState.templateId) await cfgRenderTemplate(cfgState.templateId);
    } catch (e) { showError(e.message); }
}

async function cfgRenderTemplate(id) {
    const box = document.getElementById('cfgTplDetail');
    const t = await apiRequest(`/cfg/templates/${id}`);
    cfgState.tpl = t;
    const cp = t.параметры_класса;
    box.innerHTML = `<div class="card-panel">
        <div class="bom-head"><div><div class="bom-title">${escapeHtml(t.наименование)} ${cfgKindBadge('ТИПОВОЕ')}</div>
            <div class="bom-subtitle"><span><i class="fas fa-barcode"></i> ${escapeHtml(t.артикул || '—')}</span><span><i class="fas fa-folder"></i> ${escapeHtml(t.класс || '—')}</span></div></div>
            ${CFG_ADMIN ? `<div class="bom-actions"><button class="btn btn-sm btn-outline-secondary" onclick="cfgUnmakeTemplate(${t.id})"><i class="fas fa-rotate-left"></i> Снять признак шаблона</button></div>` : ''}
        </div>

        <div class="tm-sub-title mt-2"><i class="fas fa-sliders-h"></i> Параметры конфигурации (GET_CONFIG_PARAMS)</div>
        <table class="data-table tm-mini"><thead><tr><th>Параметр</th><th>Класс</th><th>Тип</th><th class="text-end">Мин</th><th class="text-end">Макс</th><th>Параметр конфигурации</th>${CFG_ADMIN ? '<th></th>' : ''}</tr></thead><tbody>
        ${cp.map(p => `<tr class="${p.флаг_конфигурации ? '' : 'text-muted'}"><td><b>${escapeHtml(p.обозначение)}</b> – ${escapeHtml(p.полное_имя)}${p.единица_измерения ? ', ' + escapeHtml(p.единица_измерения) : ''}</td>
            <td class="small">${escapeHtml(p.класс)}</td><td class="small">${escapeHtml(p.тип_параметра)}</td>
            <td class="text-end">${cfgNum(p.мин_значение)}</td><td class="text-end">${cfgNum(p.макс_значение)}</td>
            <td>${p.флаг_конфигурации ? '<span class="badge bg-primary">да</span>' : 'нет'}</td>
            ${CFG_ADMIN ? `<td class="actions"><button class="btn btn-sm btn-outline-primary" title="Изменить" onclick='cfgShowParamModal(${JSON.stringify(p).replace(/'/g, "&#39;")})'><i class="fas fa-edit"></i></button></td>` : ''}</tr>`).join('') || `<tr><td colspan="7" class="text-muted">У класса нет параметров – привяжите их в разделе «Параметры классов»</td></tr>`}
        </tbody></table>

        <div class="tm-sub-title mt-3 d-flex align-items-center gap-2"><i class="fas fa-scale-balanced"></i> Ограничения на значения параметров
            ${CFG_ADMIN ? `<button class="btn btn-sm btn-outline-success ms-2" onclick="cfgShowConstraintModal()"><i class="fas fa-plus"></i> Ограничение</button>` : ''}</div>
        <table class="data-table tm-mini"><thead><tr><th>№</th><th>Ограничение</th><th>Выражение</th><th>Активно</th><th></th></tr></thead><tbody>
        ${t.ограничения.map((c, i) => `<tr class="${c.активно ? '' : 'text-muted'}"><td>${i + 1}</td><td>${escapeHtml(c.наименование)}<div class="small text-muted">${escapeHtml(c.сообщение || '')}</div></td>
            <td><code class="cfg-expr">${escapeHtml(c.текст)}</code></td><td>${c.активно ? 'да' : 'нет'}</td>
            <td class="actions text-nowrap"><button class="btn btn-sm btn-outline-info" title="Дерево вызовов функций" onclick="cfgShowTree(${i})"><i class="fas fa-sitemap"></i></button>
            ${CFG_ADMIN ? `<button class="btn btn-sm btn-outline-primary" title="Изменить" onclick="cfgShowConstraintModal(${i})"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-outline-danger" title="Удалить" onclick="cfgDeleteConstraint(${c.id})"><i class="fas fa-trash"></i></button>` : ''}</td></tr>`).join('') || '<tr><td colspan="5" class="text-muted">Ограничений нет</td></tr>'}
        </tbody></table>

        <div class="tm-sub-title mt-3"><i class="fas fa-coins"></i> Формула цены варианта
            ${CFG_ADMIN ? `<button class="btn btn-sm btn-outline-primary ms-2" onclick="cfgShowPriceModal()"><i class="fas fa-edit"></i></button>` : ''}</div>
        <div class="mb-2">${t.формула_цены ? `<code class="cfg-expr">${escapeHtml(t.формула_цены.текст)}</code> руб. <button class="btn btn-sm btn-link p-0 ms-2" onclick="cfgShowTree(-1)">дерево</button>` : `<span class="text-muted">не задана – цена варианта = цена шаблона (${cfgMoney(t.цена)})</span>`}</div>

        <div class="tm-sub-title mt-3"><i class="fas fa-wand-magic-sparkles"></i> Задание варианта исполнения</div>
        <div class="cfg-configurator" id="cfgConfigurator">
            ${cfgState.proto ? `<div class="alert alert-info py-2 small"><i class="fas fa-clone"></i> Прототип: <b>${escapeHtml(cfgState.proto.наименование)}</b> – значения скопированы, измените нужные
                <button class="btn btn-sm btn-link p-0 ms-2" onclick="cfgState.proto=null; cfgRenderTemplate(${t.id})">сбросить</button></div>` : ''}
            ${cfgParamInputs(t.параметры_конфигурации, cfgState.proto ? cfgState.proto.значения : {})}
            <div class="d-flex gap-2 mt-3"><button class="btn btn-outline-primary" onclick="cfgRunCheck(${t.id})"><i class="fas fa-list-check"></i> Проверить ограничения</button>
                <button class="btn btn-primary" onclick="cfgCreateVariant(${t.id})"><i class="fas fa-plus"></i> Создать вариант исполнения</button></div>
            <div id="cfgCheckResult" class="mt-3"></div>
        </div>

        <div class="tm-sub-title mt-3"><i class="fas fa-cubes"></i> Варианты исполнения (${t.варианты.length})</div>
        <table class="data-table tm-mini"><thead><tr><th>Вариант исполнения</th><th>Артикул</th><th class="text-end">Цена, руб.</th><th class="text-end">В заказах</th><th></th></tr></thead><tbody>
        ${t.варианты.map(v => `<tr><td>${escapeHtml(v.наименование)}</td><td class="small">${escapeHtml(v.артикул)}</td><td class="text-end">${cfgMoney(v.цена)}</td><td class="text-end">${v.в_заказах}</td>
            <td class="actions text-nowrap"><button class="btn btn-sm btn-outline-info" title="Значения параметров" onclick="cfgShowVariant(${v.id})"><i class="fas fa-eye"></i></button>
            <button class="btn btn-sm btn-outline-secondary" title="Копия с изменением (прототип)" onclick="cfgUsePrototype(${v.id})"><i class="fas fa-clone"></i></button></td></tr>`).join('') || '<tr><td colspan="5" class="text-muted">Вариантов пока нет</td></tr>'}
        </tbody></table>
    </div>`;
}

function cfgShowTree(i) {
    const t = cfgState.tpl;
    const e = i < 0 ? t.формула_цены : t.ограничения[i];
    bomModal(i < 0 ? 'Формула цены – дерево вызовов' : `Ограничение «${e.наименование}» – дерево вызовов`,
        `<div class="mb-2"><code class="cfg-expr">${escapeHtml(e.текст)}</code></div>${cfgTree(e.дерево)}
         <div class="small text-muted mt-2">Узлы – вызовы функций из библиотеки, листья – параметры, константы и значения перечислений (паттерн «Интерпретатор»).</div>`);
}

async function cfgRunCheck(id) {
    const vals = cfgReadValues(cfgState.tpl.параметры_конфигурации);
    const out = document.getElementById('cfgCheckResult');
    try {
        const r = await apiRequest(`/cfg/templates/${id}/check`, 'POST', { значения: vals });
        out.innerHTML = cfgCheckHtml(r);
    } catch (e) { out.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`; }
}

async function cfgCreateVariant(id) {
    const vals = cfgReadValues(cfgState.tpl.параметры_конфигурации);
    try {
        const v = await apiRequest(`/cfg/templates/${cfgState.proto ? cfgState.proto.id : id}/variants`, 'POST', { значения: vals });
        showToast(`Вариант исполнения: ${v.наименование}`);
        cfgState.proto = null;
        await cfgRenderTemplate(id);
    } catch (e) {
        document.getElementById('cfgCheckResult').innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }
}

async function cfgShowVariant(id) {
    const v = await apiRequest(`/cfg/variants/${id}`);
    bomModal('Вариант исполнения', `<div class="fw-semibold mb-1">${escapeHtml(v.наименование)}</div>
        <div class="small text-muted mb-2">Артикул ${escapeHtml(v.артикул)} · шаблон «${escapeHtml(v.шаблон)}» · цена ${cfgMoney(v.цена)} руб.</div>
        <table class="data-table tm-mini"><thead><tr><th>Параметр</th><th>Значение</th></tr></thead><tbody>
        ${v.параметры.map(p => `<tr><td><b>${escapeHtml(p.обозначение)}</b> – ${escapeHtml(p.полное_имя)}</td><td>${escapeHtml(p.текст)} ${escapeHtml(p.ед_изм || '')}</td></tr>`).join('')}</tbody></table>`);
}

async function cfgUsePrototype(id) {
    cfgState.proto = await apiRequest(`/cfg/variants/${id}`);
    await cfgRenderTemplate(cfgState.templateId);
    document.getElementById('cfgConfigurator').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/* ----- описание шаблона и параметров конфигурации ----- */
async function cfgShowMakeTemplate() {
    const list = (await apiRequest('/cfg/products?вид=ПРОСТОЕ'));
    const body = `<div class="alert alert-light border small"><i class="fas fa-info-circle text-primary"></i> Типовое изделие – шаблон: в заказ попадают только его варианты исполнения.
        Параметры конфигурации берутся из параметров класса изделия.</div>
        <div class="form-field mb-3"><label class="form-label" for="mkProd">Изделие *</label><select class="form-select" id="mkProd"><option value="">— выберите —</option>
        ${list.map(p => `<option value="${p.id}">${escapeHtml(p.наименование)} (${escapeHtml(p.артикул || '—')}) · ${escapeHtml(p.класс || '')}</option>`).join('')}</select></div>
        <div class="form-field"><label class="form-label" for="mkPrice">Базовая цена, руб.</label><input type="number" class="form-control" id="mkPrice" min="0" step="any"></div>`;
    bomModal('Описание шаблона изделия', body, `<button class="btn btn-primary" onclick="cfgMakeTemplate(this)"><i class="fas fa-check"></i> Сделать типовым</button>`);
}
async function cfgMakeTemplate(btn) {
    const id = document.getElementById('mkProd').value;
    if (!id) { bomFieldError('mkProd', 'Выберите изделие'); return; }
    const price = document.getElementById('mkPrice').value;
    try {
        await apiRequest(`/cfg/products/${id}/kind`, 'PUT', { вид_конфигурации: 'ТИПОВОЕ', цена: price === '' ? null : Number(price) });
        bomCloseModal(btn); cfgState.templateId = Number(id); showToast('Изделие стало типовым'); loadCfgTemplates();
    } catch (e) { showToast(e.message, 'error'); }
}
async function cfgUnmakeTemplate(id) {
    if (!confirm('Снять признак «типовое изделие с конфигуратором»?')) return;
    try { await apiRequest(`/cfg/products/${id}/kind`, 'PUT', { вид_конфигурации: 'ПРОСТОЕ' }); cfgState.templateId = null; loadCfgTemplates(); }
    catch (e) { showToast(e.message, 'error'); }
}
function cfgShowParamModal(p) {
    const num = p.тип_параметра !== 'ENUM';
    const body = `<div class="fw-semibold mb-2">${escapeHtml(p.обозначение)} – ${escapeHtml(p.полное_имя)} <span class="text-muted small">(${escapeHtml(p.тип_параметра)})</span></div>
        <div class="form-check mb-3"><input class="form-check-input" type="checkbox" id="pcFlag" ${p.флаг_конфигурации ? 'checked' : ''}>
            <label class="form-check-label" for="pcFlag">Параметр конфигурации (запрашивается при задании варианта исполнения)</label></div>
        ${num ? `<div class="row g-3"><div class="col-6 form-field"><label class="form-label" for="pcMin">Мин</label><input type="number" class="form-control" id="pcMin" step="any" value="${p.мин_значение ?? ''}"></div>
            <div class="col-6 form-field"><label class="form-label" for="pcMax">Макс</label><input type="number" class="form-control" id="pcMax" step="any" value="${p.макс_значение ?? ''}"></div></div>` : ''}`;
    bomModal('Параметр конфигурации', body, `<button class="btn btn-primary" onclick="cfgSaveParam(this, ${p.id}, ${num})"><i class="fas fa-save"></i> Сохранить</button>`, '');
}
async function cfgSaveParam(btn, pcId, num) {
    const v = id => { const x = document.getElementById(id)?.value; return x === undefined || x === '' ? null : Number(x); };
    try {
        await apiRequest(`/cfg/class-params/${pcId}`, 'PUT', { флаг_конфигурации: document.getElementById('pcFlag').checked, мин_значение: num ? v('pcMin') : null, макс_значение: num ? v('pcMax') : null });
        bomCloseModal(btn); showToast('Параметр сохранён'); cfgRenderTemplate(cfgState.templateId);
    } catch (e) { showToast(e.message, 'error'); }
}

/* ----- ограничения и формула цены ----- */
function cfgExprHelp() {
    const ps = cfgState.tpl.параметры_конфигурации;
    return `<div class="small text-muted mt-1">Параметры: ${ps.map(p => `<code class="cfg-chip" onclick="cfgInsert('${p.обозначение}')">${escapeHtml(p.обозначение)}</code>`).join(' ')}.
        Операции: <code>+ - * /</code>, <code>&gt; &gt;= &lt; &lt;= = &lt;&gt;</code>, <code>IN (…)</code>, <code>AND OR NOT</code>, функции библиотеки: <code>IF(у, а, б)</code>, <code>BETWEEN(x, lo, hi)</code>, <code>RATIO_IN_RANGE(a, b, lo, hi)</code>, <code>MIN</code>, <code>MAX</code>.
        Значения перечислений – в кавычках: <code>цвет = 'Прозрачный'</code>.</div>`;
}
function cfgInsert(s) { const el = document.getElementById('cfgExpr'); if (!el) return; const p = el.selectionStart ?? el.value.length; el.value = el.value.slice(0, p) + s + el.value.slice(p); el.focus(); }
function cfgShowConstraintModal(i = null) {
    const c = i == null ? null : cfgState.tpl.ограничения[i];
    const body = `<div class="form-field mb-3"><label class="form-label" for="cfgCName">Наименование *</label><input class="form-control" id="cfgCName" maxlength="200" value="${escapeHtml(c?.наименование || '')}"></div>
        <div class="form-field mb-2"><label class="form-label" for="cfgExpr">Выражение (логическое) *</label><textarea class="form-control font-monospace" id="cfgExpr" rows="2">${escapeHtml(c?.текст || '')}</textarea>${cfgExprHelp()}</div>
        <div class="form-field mb-2"><label class="form-label" for="cfgCMsg">Сообщение при нарушении</label><input class="form-control" id="cfgCMsg" value="${escapeHtml(c?.сообщение || '')}"></div>
        ${c ? `<div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="cfgCActive" ${c.активно ? 'checked' : ''}><label class="form-check-label" for="cfgCActive">Активно</label></div>` : ''}
        <button class="btn btn-sm btn-outline-info" onclick="cfgPreview('Логическое значение')"><i class="fas fa-sitemap"></i> Разобрать выражение</button>
        <div id="cfgPreview" class="mt-2"></div>`;
    bomModal(c ? 'Изменить ограничение' : 'Описание ограничения на значения параметров', body,
        `<button class="btn btn-primary" onclick="cfgSaveConstraint(this, ${c ? c.id : 'null'})"><i class="fas fa-save"></i> Сохранить</button>`);
}
async function cfgPreview(want, args = null) {
    const out = document.getElementById('cfgPreview');
    const src = document.getElementById('cfgExpr').value;
    try {
        const r = await apiRequest('/cfg/expressions/preview', 'POST', { выражение: src, изделие_id: args ? null : cfgState.templateId, аргументы: args || [] });
        const bad = want && r.тип !== want && r.тип !== 'Любое значение';
        out.innerHTML = `<div class="small mb-1">Нормализованная запись: <code class="cfg-expr">${escapeHtml(r.текст)}</code> · тип результата: <b class="${bad ? 'text-danger' : ''}">${escapeHtml(r.тип)}</b>${bad ? ` (нужно «${want}»)` : ''}</div>${cfgTree(r.дерево)}`;
    } catch (e) { out.innerHTML = `<div class="alert alert-danger py-2 mb-0"><i class="fas fa-triangle-exclamation"></i> ${escapeHtml(e.message)}</div>`; }
}
async function cfgSaveConstraint(btn, id) {
    const name = document.getElementById('cfgCName').value.trim();
    const expr = document.getElementById('cfgExpr').value.trim();
    if (!name) { bomFieldError('cfgCName', 'Введите наименование'); return; }
    if (!expr) { bomFieldError('cfgExpr', 'Введите выражение'); return; }
    const body = { наименование: name, выражение: expr, сообщение: document.getElementById('cfgCMsg').value, активно: document.getElementById('cfgCActive')?.checked ?? true };
    try {
        await apiRequest(id ? `/cfg/constraints/${id}` : `/cfg/templates/${cfgState.templateId}/constraints`, id ? 'PUT' : 'POST', body);
        bomCloseModal(btn); showToast('Ограничение сохранено'); cfgRenderTemplate(cfgState.templateId);
    } catch (e) { document.getElementById('cfgPreview').innerHTML = `<div class="alert alert-danger py-2 mb-0"><i class="fas fa-triangle-exclamation"></i> ${escapeHtml(e.message)}</div>`; }
}
async function cfgDeleteConstraint(id) {
    if (!confirm('Удалить ограничение?')) return;
    try { await apiRequest(`/cfg/constraints/${id}`, 'DELETE'); showToast('Ограничение удалено'); cfgRenderTemplate(cfgState.templateId); }
    catch (e) { showToast(e.message, 'error'); }
}
function cfgShowPriceModal() {
    const t = cfgState.tpl;
    const body = `<div class="form-field mb-2"><label class="form-label" for="cfgExpr">Формула цены, руб. (числовое выражение; пусто – цена шаблона)</label>
        <textarea class="form-control font-monospace" id="cfgExpr" rows="2">${escapeHtml(t.формула_цены?.текст || '')}</textarea>${cfgExprHelp()}</div>
        <div class="form-field mb-2"><label class="form-label" for="cfgTplPrice">Цена шаблона, руб.</label><input type="number" class="form-control" id="cfgTplPrice" min="0" step="any" value="${t.цена ?? ''}"></div>
        <button class="btn btn-sm btn-outline-info" onclick="cfgPreview('Число')"><i class="fas fa-sitemap"></i> Разобрать выражение</button><div id="cfgPreview" class="mt-2"></div>`;
    bomModal('Формула цены варианта исполнения', body, `<button class="btn btn-primary" onclick="cfgSavePrice(this)"><i class="fas fa-save"></i> Сохранить</button>`);
}
async function cfgSavePrice(btn) {
    const p = document.getElementById('cfgTplPrice').value;
    try {
        await apiRequest(`/cfg/templates/${cfgState.templateId}/price-formula`, 'PUT', { выражение: document.getElementById('cfgExpr').value, цена: p === '' ? null : Number(p) });
        bomCloseModal(btn); showToast('Формула цены сохранена'); cfgRenderTemplate(cfgState.templateId);
    } catch (e) { document.getElementById('cfgPreview').innerHTML = `<div class="alert alert-danger py-2 mb-0">${escapeHtml(e.message)}</div>`; }
}

/* ================================== Библиотека функций ================================== */
async function loadCfgFunctions() {
    showLoading();
    try {
        const [list, refs] = await Promise.all([apiRequest('/cfg/functions'), cfgRefs(true)]);
        const groups = refs.классы_функций.map(c => ({ c, items: list.filter(f => f.класс === c.name) }));
        document.getElementById('content').innerHTML = `
        <div class="page-header"><h1><i class="fas fa-square-root-variable"></i> Библиотека функций ограничений</h1>
            <p class="subtitle">Функции для описания ограничений и формул цены. Встроенные функции выполняют оператор, составные – вычисляют своё тело над формальными параметрами</p></div>
        <div class="card-panel"><div class="card-panel-header"><span><i class="fas fa-layer-group"></i> Классификатор функций: ${list.length}</span>
            ${CFG_ADMIN ? `<button class="btn btn-sm btn-success" onclick="cfgShowFunctionModal()"><i class="fas fa-plus"></i> Функция</button>` : ''}</div>
        <div class="card-panel-body">${groups.map(g => `<div class="tm-sub-title mt-2"><i class="fas fa-folder"></i> ${escapeHtml(g.c.name)} (${g.items.length})</div>
            <table class="data-table tm-mini mb-2"><thead><tr><th style="width:24%">Функция</th><th>Наименование</th><th>Оператор / тело</th><th>Результат</th><th class="text-end">Вызовов</th><th></th></tr></thead><tbody>
            ${g.items.map(f => `<tr><td><code>${escapeHtml(f.сигнатура)}</code></td><td>${escapeHtml(f.наименование)}${f.описание ? `<div class="small text-muted">${escapeHtml(f.описание)}</div>` : ''}</td>
                <td>${f.составная ? `<code class="cfg-expr">${escapeHtml(f.тело.текст)}</code>` : `<span class="badge bg-light text-dark border">${escapeHtml(f.оператор)}</span>`}</td>
                <td class="small">${escapeHtml(f.тип || '')}</td><td class="text-end">${f.вызовов}</td>
                <td class="actions text-nowrap"><button class="btn btn-sm btn-outline-info" title="Вычислить (EVAL_FUNCTION)" onclick="cfgShowEvalModal(${f.id})"><i class="fas fa-calculator"></i></button>
                ${CFG_ADMIN && f.составная ? `<button class="btn btn-sm btn-outline-danger" title="Удалить" onclick="cfgDeleteFunction(${f.id})"><i class="fas fa-trash"></i></button>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="text-muted">нет</td></tr>'}
            </tbody></table>`).join('')}</div></div>`;
        cfgState.functions = list;
    } catch (e) { showError(e.message); }
}

/* ----- Функция_ограничения.Вычислить(аргументы): EVAL_FUNCTION для введённых значений ----- */
function cfgEvalInput(a, k) {
    const id = `evA${k}`;
    if (a.тип === 'Логическое значение')
        return `<select class="form-select form-select-sm cfg-eval" id="${id}"><option value="true">истина</option><option value="false">ложь</option></select>`;
    if (a.тип === 'Значение перечисления')
        return `<select class="form-select form-select-sm cfg-eval" id="${id}"><option value="">— выберите —</option>${cfgState.refs.перечисления.map(e =>
            `<optgroup label="${escapeHtml(e.name)}">${e.значения.map(v => `<option value="${v.id}">${escapeHtml(v.value)}</option>`).join('')}</optgroup>`).join('')}</select>`;
    return `<input class="form-control form-control-sm cfg-eval" id="${id}" ${a.тип === 'Число' ? 'type="number" step="any"' : 'placeholder="число или строка"'}>`;
}
function cfgEvalRows() {
    const f = cfgState.evalFn;
    const rows = [];
    let k = 0;
    f.аргументы.forEach((a, i) => {
        const reps = a.повторяемый ? cfgState.evalReps : 1;
        for (let r = 0; r < reps; r++, k++)
            rows.push(`<div class="row g-2 mb-1 align-items-center"><div class="col-4 small"><b>${escapeHtml(a.имя)}${a.повторяемый ? ` ${r + 1}` : ''}</b> <span class="text-muted">(${escapeHtml(a.тип || 'Любое значение')})</span></div>
                <div class="col-8">${cfgEvalInput(a, k)}</div></div>`);
    });
    const rep = f.аргументы.some(a => a.повторяемый);
    return rows.join('') + (rep ? `<button class="btn btn-sm btn-link p-0" onclick="cfgState.evalReps++; document.getElementById('evRows').innerHTML = cfgEvalRows()">+ ещё значение</button>` : '');
}
async function cfgShowEvalModal(fid) {
    await cfgRefs();
    const f = cfgState.functions.find(x => x.id === fid);
    cfgState.evalFn = f; cfgState.evalReps = 2;
    const body = `<div class="mb-2"><code>${escapeHtml(f.сигнатура)}</code> – ${escapeHtml(f.наименование)}
            ${f.составная ? `<div class="small text-muted mt-1">Тело: <code class="cfg-expr">${escapeHtml(f.тело.текст)}</code></div>` : `<div class="small text-muted mt-1">Оператор: <b>${escapeHtml(f.оператор)}</b></div>`}</div>
        <div class="tm-sub-title">Фактические параметры (значения аргументов)</div>
        <div id="evRows">${cfgEvalRows()}</div>
        <div id="evResult" class="mt-3"></div>`;
    bomModal('Вычисление функции (EVAL_FUNCTION)', body, `<button class="btn btn-primary" onclick="cfgEvaluate()"><i class="fas fa-calculator"></i> Вычислить</button>`);
}
async function cfgEvaluate() {
    const vals = Array.from(document.querySelectorAll('#evRows .cfg-eval')).map(el => {
        const v = el.value.trim();
        if (v === 'true' || v === 'false') return v === 'true';
        return v === '' ? null : v;
    });
    const out = document.getElementById('evResult');
    try {
        const r = await apiRequest(`/cfg/functions/${cfgState.evalFn.id}/evaluate`, 'POST', { аргументы: vals });
        const cls = r.результат === true ? 'alert-success' : (r.результат === false ? 'alert-warning' : 'alert-info');
        out.innerHTML = `<div class="alert ${cls} py-2 mb-0"><code>${escapeHtml(r.вызов)}</code> = <b>${escapeHtml(r.результат_текст)}</b>
            <span class="small text-muted">(${escapeHtml(r.тип || '')})</span></div>`;
    } catch (e) { out.innerHTML = `<div class="alert alert-danger py-2 mb-0"><i class="fas fa-triangle-exclamation"></i> ${escapeHtml(e.message)}</div>`; }
}
function cfgArgRow(i, name = '', typeId = '') {
    const types = cfgState.refs.типы;
    return `<div class="row g-2 mb-1 cfg-arg"><div class="col-6"><input class="form-control form-control-sm" placeholder="имя" value="${escapeHtml(name)}"></div>
        <div class="col-6"><select class="form-select form-select-sm">${types.map(t => `<option value="${t.id}" ${String(t.id) === String(typeId) ? 'selected' : ''}>${escapeHtml(t.name)}</option>`).join('')}</select></div></div>`;
}
function cfgReadArgs() {
    return Array.from(document.querySelectorAll('.cfg-arg')).map(r => ({ имя: r.querySelector('input').value.trim(), тип_id: Number(r.querySelector('select').value) })).filter(a => a.имя);
}
function cfgShowFunctionModal() {
    const R = cfgState.refs;
    const num = R.типы.find(t => t.name === 'Число')?.id;
    const body = `<div class="row g-3"><div class="col-md-4 form-field"><label class="form-label" for="fnCode">Обозначение *</label><input class="form-control" id="fnCode" maxlength="40" placeholder="AREA_LE"></div>
        <div class="col-md-8 form-field"><label class="form-label" for="fnName">Наименование *</label><input class="form-control" id="fnName" maxlength="200"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="fnClass">Класс функции *</label><select class="form-select" id="fnClass">${R.классы_функций.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')}</select></div>
        <div class="col-12"><label class="form-label">Формальные параметры *</label><div id="fnArgs">${cfgArgRow(1, 'a', num)}${cfgArgRow(2, 'b', num)}</div>
            <button class="btn btn-sm btn-link p-0" onclick="document.getElementById('fnArgs').insertAdjacentHTML('beforeend', cfgArgRow(0, '', ${num}))">+ параметр</button></div>
        <div class="col-12 form-field"><label class="form-label" for="cfgExpr">Тело функции – выражение над параметрами *</label><textarea class="form-control font-monospace" id="cfgExpr" rows="2" placeholder="a * b <= 256"></textarea></div>
        <div class="col-12 form-field"><label class="form-label" for="fnDescr">Описание</label><input class="form-control" id="fnDescr"></div></div>
        <button class="btn btn-sm btn-outline-info mt-2" onclick="cfgPreview(null, cfgReadArgs())"><i class="fas fa-sitemap"></i> Разобрать тело</button><div id="cfgPreview" class="mt-2"></div>`;
    bomModal('Функция с формальными параметрами', body, `<button class="btn btn-primary" onclick="cfgSaveFunction(this)"><i class="fas fa-save"></i> Добавить</button>`);
}
async function cfgSaveFunction(btn) {
    const code = document.getElementById('fnCode').value.trim(), name = document.getElementById('fnName').value.trim();
    if (!code) { bomFieldError('fnCode', 'Введите обозначение'); return; }
    if (!name) { bomFieldError('fnName', 'Введите наименование'); return; }
    try {
        await apiRequest('/cfg/functions', 'POST', { обозначение: code, наименование: name, класс_id: Number(document.getElementById('fnClass').value),
            аргументы: cfgReadArgs(), тело: document.getElementById('cfgExpr').value, описание: document.getElementById('fnDescr').value || null });
        bomCloseModal(btn); showToast('Функция добавлена'); loadCfgFunctions();
    } catch (e) { document.getElementById('cfgPreview').innerHTML = `<div class="alert alert-danger py-2 mb-0">${escapeHtml(e.message)}</div>`; }
}
async function cfgDeleteFunction(id) {
    if (!confirm('Удалить функцию из библиотеки?')) return;
    try { await apiRequest(`/cfg/functions/${id}`, 'DELETE'); showToast('Функция удалена'); loadCfgFunctions(); }
    catch (e) { showToast(e.message, 'error'); }
}

/* ================================== Заказы ================================== */
async function loadCfgOrders() {
    showLoading();
    try {
        const list = await apiRequest('/cfg/orders');
        await cfgRefs(true);
        if (!cfgState.orderId || !list.some(o => o.id === cfgState.orderId)) cfgState.orderId = list[0]?.id || null;
        document.getElementById('content').innerHTML = `
        <div class="page-header"><h1><i class="fas fa-file-invoice"></i> Заказы на изделия</h1>
            <p class="subtitle">Регистрация заказа, формирование позиций с вариантами исполнения, проверка ограничений, согласование и бланк заказа</p></div>
        <div class="row g-3">
            <div class="col-xxl-3 col-lg-4"><div class="card-panel">
                <div class="card-panel-header"><span><i class="fas fa-list"></i> Заказы: ${list.length}</span>
                    <button class="btn btn-sm btn-success" title="Зарегистрировать заказ" onclick="cfgShowOrderModal()"><i class="fas fa-plus"></i></button></div>
                <div class="card-panel-body"><div class="bom-product-list">
                ${list.map(o => `<button class="bom-product-item ${o.id === cfgState.orderId ? 'active' : ''}" onclick="cfgState.orderId=${o.id}; loadCfgOrders()">
                    <span class="bom-product-icon text-primary"><i class="fas fa-file-invoice"></i></span>
                    <span class="bom-product-text"><span class="bom-product-name">${escapeHtml(o.номер)} ${cfgStatusBadge(o.статус)}</span>
                    <span class="bom-product-meta">${escapeHtml(o.заказчик)} · ${o.позиций} поз. · ${cfgMoney(o.сумма)} руб.</span></span></button>`).join('') || '<div class="empty-state py-4"><p>Заказов нет</p></div>'}
                </div></div></div></div>
            <div class="col-xxl-9 col-lg-8"><div id="cfgOrderDetail"></div></div>
        </div>`;
        if (cfgState.orderId) await cfgRenderOrder(cfgState.orderId);
    } catch (e) { showError(e.message); }
}

async function cfgRenderOrder(id) {
    const o = await apiRequest(`/cfg/orders/${id}`);
    cfgState.order = o;
    const draft = o.статус === 'ЧЕРНОВИК';
    document.getElementById('cfgOrderDetail').innerHTML = `<div class="card-panel">
        <div class="bom-head"><div><div class="bom-title">Заказ ${escapeHtml(o.номер)} ${cfgStatusBadge(o.статус)}</div>
            <div class="bom-subtitle"><span><i class="fas fa-building"></i> ${escapeHtml(o.заказчик)}</span><span><i class="fas fa-calendar"></i> от ${cfgDate(o.дата_регистрации)}</span>
            <span><i class="fas fa-flag-checkered"></i> срок ${cfgDate(o.срок_изготовления)}</span>${o.контактное_лицо ? `<span><i class="fas fa-user"></i> ${escapeHtml(o.контактное_лицо)} ${escapeHtml(o.телефон || '')}</span>` : ''}</div></div>
            <div class="bom-actions">
                ${draft ? `<button class="btn btn-sm btn-success" onclick="cfgShowConfigureModal()"><i class="fas fa-wand-magic-sparkles"></i> Вариант исполнения</button>
                    <button class="btn btn-sm btn-outline-success" onclick="cfgShowAddItemModal()"><i class="fas fa-plus"></i> Изделие</button>` : ''}
                <button class="btn btn-sm btn-outline-dark" onclick="cfgShowDocument()"><i class="fas fa-print"></i> Бланк заказа</button>
                ${CFG_ADMIN ? (draft ? `<button class="btn btn-sm btn-primary" onclick="cfgSetStatus('СОГЛАСОВАН')"><i class="fas fa-check-double"></i> Согласовать</button>`
                                     : `<button class="btn btn-sm btn-outline-secondary" onclick="cfgSetStatus('ЧЕРНОВИК')"><i class="fas fa-rotate-left"></i> В черновик</button>`) : ''}
                ${draft ? `<button class="btn btn-sm btn-outline-primary" title="Изменить реквизиты" onclick="cfgShowOrderModal(true)"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-outline-danger" title="Удалить заказ" onclick="cfgDeleteOrder()"><i class="fas fa-trash"></i></button>` : ''}
            </div></div>
        ${o.примечание ? `<div class="small text-muted mb-2"><i class="fas fa-note-sticky"></i> ${escapeHtml(o.примечание)}</div>` : ''}
        <div class="tm-sub-title mt-2"><i class="fas fa-list-ol"></i> Позиции заказа</div>
        <div class="table-responsive"><table class="data-table"><thead><tr><th>№</th><th>Изделие</th><th>Вариант исполнения</th><th class="text-end">Кол-во</th><th class="text-end">Цена, руб.</th><th class="text-end">Стоимость, руб.</th><th></th></tr></thead><tbody>
        ${o.позиции.map(p => `<tr><td>${p.номер}</td><td>${escapeHtml(p.шаблон || p.изделие)}<div class="small text-muted">${escapeHtml(p.артикул || '')} ${cfgKindBadge(p.вид_конфигурации)}</div></td>
            <td>${p.параметры.length ? p.параметры.map(x => `<span class="cfg-pv">${escapeHtml(x.обозначение)} = <b>${escapeHtml(x.текст)}</b></span>`).join('') : '<span class="text-muted">—</span>'}</td>
            <td class="text-end">${cfgNum(p.количество)}</td><td class="text-end">${cfgMoney(p.цена)}</td><td class="text-end fw-semibold">${cfgMoney(p.стоимость)}</td>
            <td class="actions text-nowrap">${p.вид_конфигурации === 'ВАРИАНТ' ? `<button class="btn btn-sm btn-outline-info" title="Значения параметров" onclick="cfgShowVariant(${p.изделие_id})"><i class="fas fa-eye"></i></button>` : ''}
            ${draft ? `${p.вид_конфигурации === 'ВАРИАНТ' ? `<button class="btn btn-sm btn-outline-secondary" title="Копия с изменением (прототип)" onclick="cfgShowConfigureModal(${p.изделие_id})"><i class="fas fa-clone"></i></button>` : ''}
                <button class="btn btn-sm btn-outline-primary" title="Изменить количество" onclick="cfgEditQty(${p.id}, ${p.количество})"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-outline-danger" title="Удалить позицию" onclick="cfgDeleteItem(${p.id})"><i class="fas fa-trash"></i></button>` : ''}</td></tr>`).join('') || '<tr><td colspan="7" class="text-muted">Позиций нет – добавьте изделие или вариант исполнения</td></tr>'}
        </tbody><tfoot><tr><td colspan="5" class="text-end fw-bold">Сумма заказа:</td><td class="text-end fw-bold">${cfgMoney(o.сумма)}</td><td></td></tr></tfoot></table></div>
    </div>`;
}

function cfgShowOrderModal(edit = false) {
    const o = edit ? cfgState.order : {};
    const R = cfgState.refs;
    const today = new Date().toISOString().slice(0, 10);
    const body = `<div class="row g-3">
        <div class="col-md-8 form-field"><label class="form-label" for="ordCust">Заказчик *</label><select class="form-select" id="ordCust" onchange="cfgFillContact()"><option value="">— выберите —</option>
            ${R.заказчики.map(s => `<option value="${s.id}" ${s.id === o.заказчик_id ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('')}</select></div>
        <div class="col-md-4 form-field"><label class="form-label" for="ordNum">Номер</label><input class="form-control" id="ordNum" maxlength="30" value="${escapeHtml(o.номер || '')}" placeholder="автоматически"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="ordDate">Дата регистрации *</label><input type="date" class="form-control" id="ordDate" value="${o.дата_регистрации || today}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="ordDue">Срок изготовления</label><input type="date" class="form-control" id="ordDue" value="${o.срок_изготовления || ''}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="ordPerson">Контактное лицо</label><input class="form-control" id="ordPerson" value="${escapeHtml(o.контактное_лицо || '')}"></div>
        <div class="col-md-6 form-field"><label class="form-label" for="ordPhone">Телефон / e-mail</label><input class="form-control" id="ordPhone" value="${escapeHtml(o.телефон || '')}"></div>
        <div class="col-12 form-field"><label class="form-label" for="ordNote">Примечание</label><input class="form-control" id="ordNote" value="${escapeHtml(o.примечание || '')}"></div></div>`;
    bomModal(edit ? 'Реквизиты заказа' : 'Регистрация заказа', body, `<button class="btn btn-primary" onclick="cfgSaveOrder(this, ${edit ? o.id : 'null'})"><i class="fas fa-save"></i> Сохранить</button>`);
}
function cfgFillContact() {
    const s = cfgState.refs.заказчики.find(x => String(x.id) === document.getElementById('ordCust').value);
    if (!s) return;
    if (!document.getElementById('ordPerson').value) document.getElementById('ordPerson').value = s.контактное_лицо || '';
    if (!document.getElementById('ordPhone').value) document.getElementById('ordPhone').value = s.телефон || '';
}
async function cfgSaveOrder(btn, id) {
    const cust = document.getElementById('ordCust').value;
    if (!cust) { bomFieldError('ordCust', 'Выберите заказчика'); return; }
    const reg = document.getElementById('ordDate').value, due = document.getElementById('ordDue').value;
    if (due && reg && due < reg) { bomFieldError('ordDue', 'Срок раньше даты регистрации'); return; }
    const body = { заказчик_id: Number(cust), номер: document.getElementById('ordNum').value || null, дата_регистрации: reg || null, срок_изготовления: due || null,
        контактное_лицо: document.getElementById('ordPerson').value || null, телефон: document.getElementById('ordPhone').value || null, примечание: document.getElementById('ordNote').value || null };
    try {
        const r = await apiRequest(id ? `/cfg/orders/${id}` : '/cfg/orders', id ? 'PUT' : 'POST', body);
        bomCloseModal(btn); cfgState.orderId = r.id; showToast(`Заказ ${r.номер} сохранён`); loadCfgOrders();
    } catch (e) { showToast(e.message, 'error'); }
}
async function cfgSetStatus(s) {
    try { await apiRequest(`/cfg/orders/${cfgState.orderId}/status`, 'PUT', { статус: s }); showToast(s === 'СОГЛАСОВАН' ? 'Заказ согласован' : 'Заказ возвращён в черновик'); loadCfgOrders(); }
    catch (e) { showToast(e.message, 'error'); }
}
async function cfgDeleteOrder() {
    if (!confirm('Удалить заказ-черновик?')) return;
    try { await apiRequest(`/cfg/orders/${cfgState.orderId}`, 'DELETE'); cfgState.orderId = null; loadCfgOrders(); }
    catch (e) { showToast(e.message, 'error'); }
}
async function cfgShowAddItemModal() {
    const [simple, variants] = await Promise.all([apiRequest('/cfg/products?вид=ПРОСТОЕ'), apiRequest('/cfg/products?вид=ВАРИАНТ')]);
    const opt = p => `<option value="${p.id}">${escapeHtml(p.наименование)} (${escapeHtml(p.артикул || '—')}) · ${cfgMoney(p.цена)} руб.</option>`;
    const body = `<div class="alert alert-light border small"><i class="fas fa-info-circle text-primary"></i> В заказ добавляется изделие без конфигурации или уже созданный вариант исполнения.
            Новый вариант задаётся кнопкой «Вариант исполнения»; типовое изделие (шаблон) в заказ не добавляется.</div>
        <div class="form-field mb-3"><label class="form-label" for="itProd">Изделие *</label><select class="form-select" id="itProd"><option value="">— выберите —</option>
        <optgroup label="Изделия без конфигурации">${simple.filter(p => p.цена).map(opt).join('')}</optgroup>
        <optgroup label="Варианты исполнения">${variants.map(opt).join('')}</optgroup></select></div>
        <div class="form-field"><label class="form-label" for="itQty">Количество *</label><input type="number" class="form-control" id="itQty" min="1" step="1" value="1"></div>`;
    bomModal('Добавить изделие в заказ', body, `<button class="btn btn-primary" onclick="cfgAddItem(this)"><i class="fas fa-plus"></i> Добавить</button>`);
}
async function cfgAddItem(btn) {
    const p = document.getElementById('itProd').value;
    if (!p) { bomFieldError('itProd', 'Выберите изделие'); return; }
    const q = bomPositiveNumber('itQty', 'Количество');
    if (q == null) return;
    try { await apiRequest(`/cfg/orders/${cfgState.orderId}/items`, 'POST', { изделие_id: Number(p), количество: q }); bomCloseModal(btn); showToast('Позиция добавлена'); loadCfgOrders(); }
    catch (e) { showToast(e.message, 'error'); }
}

/* ----- задание варианта исполнения в заказе (CHECK_CONSTRAINTS → CREATE_VARIANT → ADD_TO_ORDER) ----- */
async function cfgShowConfigureModal(protoVariantId = null) {
    const templates = await apiRequest('/cfg/templates');
    let proto = null;
    if (protoVariantId) proto = await apiRequest(`/cfg/variants/${protoVariantId}`);
    const tplId = proto ? proto.шаблон_id : templates[0]?.id;
    const body = `${proto ? `<div class="alert alert-info py-2 small"><i class="fas fa-clone"></i> Копия с изменением: прототип – <b>${escapeHtml(proto.наименование)}</b></div>` : ''}
        <div class="row g-3 mb-2"><div class="col-md-8 form-field"><label class="form-label" for="cfTpl">Типовое изделие (шаблон) *</label><select class="form-select" id="cfTpl" ${proto ? 'disabled' : ''} onchange="cfgConfLoad()">
            ${templates.map(t => `<option value="${t.id}" ${t.id === tplId ? 'selected' : ''}>${escapeHtml(t.наименование)} (${escapeHtml(t.артикул || '')})</option>`).join('')}</select></div>
        <div class="col-md-4 form-field"><label class="form-label" for="cfQty">Количество *</label><input type="number" class="form-control" id="cfQty" min="1" step="1" value="${proto ? 1 : 100}"></div></div>
        <div id="cfParams"></div>
        <button class="btn btn-sm btn-outline-primary mt-3" onclick="cfgConfCheck()"><i class="fas fa-list-check"></i> Проверить ограничения</button>
        <div id="cfCheck" class="mt-2"></div>`;
    bomModal('Задание варианта исполнения', body, `<button class="btn btn-primary" onclick="cfgConfAdd(this)"><i class="fas fa-cart-plus"></i> Добавить в заказ</button>`, 'modal-xl');
    cfgState.confProto = proto;
    await cfgConfLoad();
}
async function cfgConfLoad() {
    const id = document.getElementById('cfTpl').value;
    cfgState.confParams = await apiRequest(`/cfg/templates/${id}/config-params`);
    document.getElementById('cfParams').innerHTML = cfgParamInputs(cfgState.confParams, cfgState.confProto ? cfgState.confProto.значения : {}, 'cf');
    document.getElementById('cfCheck').innerHTML = '';
}
async function cfgConfCheck() {
    const id = document.getElementById('cfTpl').value;
    try { document.getElementById('cfCheck').innerHTML = cfgCheckHtml(await apiRequest(`/cfg/templates/${id}/check`, 'POST', { значения: cfgReadValues(cfgState.confParams, 'cf') })); }
    catch (e) { document.getElementById('cfCheck').innerHTML = `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`; }
}
async function cfgConfAdd(btn) {
    const q = bomPositiveNumber('cfQty', 'Количество');
    if (q == null) return;
    const proto = cfgState.confProto;
    try {
        const r = await apiRequest(`/cfg/orders/${cfgState.orderId}/configure`, 'POST', {
            изделие_id: proto ? proto.id : Number(document.getElementById('cfTpl').value), значения: cfgReadValues(cfgState.confParams, 'cf'), количество: q });
        bomCloseModal(btn); showToast(`Добавлено: ${r.вариант.наименование}`); loadCfgOrders();
    } catch (e) {
        await cfgConfCheck();
        if (!document.querySelector('#cfCheck .alert-danger'))
            document.getElementById('cfCheck').insertAdjacentHTML('afterbegin', `<div class="alert alert-danger py-2"><i class="fas fa-triangle-exclamation"></i> ${escapeHtml(e.message)}</div>`);
    }
}
async function cfgEditQty(itemId, q) {
    const body = `<div class="form-field"><label class="form-label" for="eqQty">Количество *</label><input type="number" class="form-control" id="eqQty" min="1" step="1" value="${q}"></div>`;
    bomModal('Количество в позиции заказа', body, `<button class="btn btn-primary" onclick="cfgSaveQty(this, ${itemId})"><i class="fas fa-save"></i> Сохранить</button>`, '');
}
async function cfgSaveQty(btn, itemId) {
    const q = bomPositiveNumber('eqQty', 'Количество');
    if (q == null) return;
    try { await apiRequest(`/cfg/order-items/${itemId}`, 'PUT', { количество: q }); bomCloseModal(btn); loadCfgOrders(); }
    catch (e) { showToast(e.message, 'error'); }
}
async function cfgDeleteItem(itemId) {
    if (!confirm('Удалить позицию заказа?')) return;
    try { await apiRequest(`/cfg/order-items/${itemId}`, 'DELETE'); showToast('Позиция удалена'); loadCfgOrders(); }
    catch (e) { showToast(e.message, 'error'); }
}

/* ----- бланк заказа (вывод состава заказа) ----- */
function cfgDocumentHtml(o) {
    return `<div class="cfg-doc"><h4 class="text-center mb-1">БЛАНК ЗАКАЗА № ${escapeHtml(o.номер)}</h4>
        <div class="text-center small mb-3">от ${cfgDate(o.дата_регистрации)} · статус: ${o.статус === 'СОГЛАСОВАН' ? 'согласован' : 'черновик'}</div>
        <table class="cfg-doc-head"><tr><td>Заказчик:</td><td><b>${escapeHtml(o.заказчик)}</b></td></tr>
        <tr><td>Контактное лицо:</td><td>${escapeHtml(o.контактное_лицо || '—')} ${escapeHtml(o.телефон || '')}</td></tr>
        <tr><td>Срок изготовления:</td><td>${cfgDate(o.срок_изготовления)}</td></tr></table>
        <table class="cfg-doc-table"><thead><tr><th>№</th><th>Наименование</th><th>Артикул</th><th>Вариант исполнения</th><th>Кол-во</th><th>Цена, руб.</th><th>Сумма, руб.</th></tr></thead><tbody>
        ${o.позиции.map(p => `<tr><td>${p.номер}</td><td>${escapeHtml(p.шаблон || p.изделие)}</td><td>${escapeHtml(p.артикул || '')}</td>
            <td>${p.параметры.map(x => `${escapeHtml(x.полное_имя)}: ${escapeHtml(x.текст)}${x.ед_изм ? ' ' + escapeHtml(x.ед_изм) : ''}`).join('<br>') || '—'}</td>
            <td class="r">${cfgNum(p.количество)}</td><td class="r">${cfgMoney(p.цена)}</td><td class="r">${cfgMoney(p.стоимость)}</td></tr>`).join('')}
        </tbody><tfoot><tr><td colspan="6" class="r"><b>Итого:</b></td><td class="r"><b>${cfgMoney(o.сумма)}</b></td></tr></tfoot></table>
        <div class="d-flex justify-content-between mt-4 small"><span>Заказчик ____________________</span><span>Отдел сбыта ____________________</span></div></div>`;
}
function cfgShowDocument() {
    const html = cfgDocumentHtml(cfgState.order);
    bomModal(`Бланк заказа ${cfgState.order.номер}`, html, `<button class="btn btn-primary" onclick="cfgPrint()"><i class="fas fa-print"></i> Печать</button>`, 'modal-xl');
}
function cfgPrint() {
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(`<html><head><title>Бланк заказа ${escapeHtml(cfgState.order.номер)}</title><style>
        body{font-family:Arial,sans-serif;font-size:13px;margin:24px} h4{font-size:18px;margin:0;text-align:center} .text-center{text-align:center}
        table{border-collapse:collapse;width:100%;margin-top:10px} .cfg-doc-table th,.cfg-doc-table td{border:1px solid #444;padding:4px 6px;vertical-align:top}
        .r{text-align:right} .d-flex{display:flex;justify-content:space-between;margin-top:36px}</style></head><body>${cfgDocumentHtml(cfgState.order)}</body></html>`);
    w.document.close(); w.focus(); w.print();
}
