/** Общие утилиты для интерфейсов пользователя и администратора */
const API_BASE = '';

async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (data) options.body = JSON.stringify(data);
    const response = await fetch(API_BASE + url, options);
    if (!response.ok) {
        let detail = 'Ошибка запроса';
        try {
            const err = await response.json();
            detail = err.detail || (typeof err.message === 'string' ? err.message : detail);
            if (Array.isArray(detail)) detail = detail.map(d => d.msg || d).join('; ');
        } catch (_) { /* ignore */ }
        throw new Error(detail);
    }
    if (method === 'DELETE' || response.status === 204) return { success: true };
    const text = await response.text();
    return text ? JSON.parse(text) : { success: true };
}

function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text == null ? '' : String(text);
    return d.innerHTML;
}

function showToast(message, type = 'success') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
    const toast = document.createElement('div');
    toast.className = `toast-item ${type === 'danger' ? 'error' : type}`;
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function showLoading(containerId = 'content') {
    const el = document.getElementById(containerId);
    if (el) {
        el.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Загрузка...</p></div>`;
    }
}

function showError(message, containerId = 'content') {
    const el = document.getElementById(containerId);
    if (el) {
        el.innerHTML = `<div class="card-panel"><div class="card-panel-body"><div class="alert alert-danger mb-0"><i class="fas fa-exclamation-triangle"></i> ${escapeHtml(message)}</div></div></div>`;
    }
}

function setActiveNav(clickedLink) {
    document.querySelectorAll('.app-sidebar .nav-link').forEach(l => l.classList.remove('active'));
    if (clickedLink) clickedLink.classList.add('active');
}

function initSidebarToggle() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('appSidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    }
}

function initGlobalSearch(handler) {
    const input = document.getElementById('globalSearch');
    if (!input || !handler) return;
    let timer;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => handler(input.value.trim()), 350);
    });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handler(input.value.trim());
        }
    });
}

function formatPrice(n) {
    if (n == null) return '—';
    return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}

function formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('ru-RU');
}

function validateRequired(ids) {
    let ok = true;
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const val = (el.value || '').trim();
        const invalid = !val;
        el.classList.toggle('field-invalid', invalid);
        let msg = el.parentElement.querySelector('.field-error-msg');
        if (invalid) {
            if (!msg) {
                msg = document.createElement('div');
                msg.className = 'field-error-msg';
                el.parentElement.appendChild(msg);
            }
            msg.textContent = 'Обязательное поле';
            ok = false;
        } else if (msg) msg.remove();
    });
    return ok;
}

function openModal(id) {
    const el = document.getElementById(id);
    if (el) bootstrap.Modal.getOrCreateInstance(el).show();
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
        const m = bootstrap.Modal.getInstance(el);
        if (m) m.hide();
    }
}

function buildSelectOptions(items, valueKey, labelKey, placeholder = '— выберите —') {
    let html = `<option value="">${placeholder}</option>`;
    for (const item of items) {
        html += `<option value="${item[valueKey]}">${escapeHtml(item[labelKey])}</option>`;
    }
    return html;
}

function getNodeIcon(t) {
    const icons = {
        промежуточный: 'fa-folder',
        терминальный: 'fa-file',
        набор: 'fa-cubes',
        тематика: 'fa-tag',
        возрастная_категория: 'fa-child',
        тип_детали: 'fa-cog',
    };
    return icons[t] || 'fa-box';
}

function getProductIcon(t) {
    const icons = { set: 'fa-cubes', part: 'fa-microchip', minifigure: 'fa-user-astronaut' };
    return icons[t] || 'fa-box';
}

function renderTreeReadonly(node, level = 0, onSelect = null) {
    const hasChildren = (node.children?.length > 0) || (node.products?.length > 0);
    const selectAttr = onSelect ? `onclick="window.selectTreeNode && window.selectTreeNode(${node.id}, '${escapeHtml(node.name).replace(/'/g, "\\'")}')"` : '';
    let html = `<div class="tree-node-row" data-id="${node.id}" ${selectAttr} style="padding-left:${level * 12}px">
        <span class="tree-toggle" onclick="event.stopPropagation();toggleTreeBranch(this)">${hasChildren ? '▼' : '•'}</span>
        <i class="fas ${getNodeIcon(node.node_type)} text-primary"></i>
        <span class="flex-grow-1">${escapeHtml(node.name)}</span>
        <span class="badge-type">${escapeHtml(node.node_type)}</span>
    </div><div class="tree-children">`;
    if (node.children) for (const c of node.children) html += renderTreeReadonly(c, level + 1, onSelect);
    if (node.products?.length) {
        html += `<div class="tree-products">`;
        for (const p of node.products) {
            html += `<div class="small py-1"><i class="fas ${getProductIcon(p.type)}"></i> ${escapeHtml(p.name)} <span class="badge-type">${p.type}</span></div>`;
        }
        html += `</div>`;
    }
    html += `</div>`;
    return html;
}

function toggleTreeBranch(el) {
    const row = el.closest('.tree-node-row');
    const children = row?.nextElementSibling;
    if (children?.classList.contains('tree-children')) {
        const hidden = children.style.display === 'none';
        children.style.display = hidden ? 'block' : 'none';
        el.textContent = hidden ? '▼' : '▶';
    }
}

/** Пояснение разницы «Деталь» (1.1) и «Изделие» (1.3) для интерфейса пользователя */
function entityInfoHtml(kind) {
    if (kind === 'part') {
        return `<div class="entity-info entity-info-part" role="note">
            <strong><i class="fas fa-microchip"></i> Деталь</strong> — конструктивный элемент LEGO для наборов (работы 1.1–1.2).
            Жёсткие поля: тип, цвет, размер, вес. Входит в <em>состав набора</em>, не продаётся отдельно на складе.
            <span class="entity-info-hint">Пример: «Кирпич 2×4 красный».</span>
        </div>`;
    }
    if (kind === 'product') {
        return `<div class="entity-info entity-info-product" role="note">
            <strong><i class="fas fa-box"></i> Изделие</strong> — товар на складе с артикулом (работа 1.3).
            Гибкие <em>параметры</em> из справочника (вес, цвет, материал…), привязка к классу изделия.
            Используется в <em>хозяйственных операциях</em>. Параметры здесь — не поля детали.
            <span class="entity-info-hint">Пример: «Кирпич красный», артикул BR001, параметр «вес» = 2.5.</span>
        </div>`;
    }
    return `<div class="entity-info entity-info-compare" role="note">
        <p><strong>Деталь</strong> — элемент для сборки наборов. <strong>Изделие</strong> — товар для учёта и продажи с настраиваемыми параметрами.</p>
        <p class="mb-0 small text-muted">Ищете деталь для каталога конструктора → раздел «Детали». Подбор товара по характеристикам → «Изделия».</p>
    </div>`;
}
