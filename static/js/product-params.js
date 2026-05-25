/** Значения параметров изделий: формы создания/редактирования */

const productParamsCache = {
    classParams: {},
    enumValues: {},
};

async function fetchClassParameters(classId) {
    if (!classId) return [];
    const key = String(classId);
    if (!productParamsCache.classParams[key]) {
        productParamsCache.classParams[key] = await apiRequest(`/classes/${classId}/parameters`);
    }
    return productParamsCache.classParams[key];
}

function invalidateClassParamsCache() {
    productParamsCache.classParams = {};
}

async function fetchEnumValues(enumId) {
    if (!enumId) return [];
    const key = String(enumId);
    if (!productParamsCache.enumValues[key]) {
        productParamsCache.enumValues[key] = await apiRequest(`/enumerations/${enumId}/values`);
    }
    return productParamsCache.enumValues[key];
}

function defaultParamValue(param, rawValue) {
    if (rawValue !== null && rawValue !== undefined && rawValue !== '') return rawValue;
    if (param.значение_по_умолчанию != null && param.значение_по_умолчанию !== '') {
        return param.значение_по_умолчанию;
    }
    return '';
}

async function buildParamValueInputHtml(param, fieldId, currentValue) {
    const unit = param.единица_измерения ? ` (${param.единица_измерения})` : '';
    const reqMark = param.обязательный ? ' *' : '';
    const label = `${param.полное_имя}${unit}${reqMark}`;
    const type = param.тип_параметра;
    const val = defaultParamValue(param, currentValue);
    let input = '';

    if (type === 'ENUM' && param.перечисление_id) {
        const values = await fetchEnumValues(param.перечисление_id);
        let opts = '<option value="">— не задано —</option>';
        for (const v of values) {
            const selected = String(val) === String(v.id) ? ' selected' : '';
            opts += `<option value="${v.id}"${selected}>${escapeHtml(v.value)}</option>`;
        }
        input = `<select class="form-select product-param-input" id="${fieldId}" data-param-class-id="${param.param_class_id}" data-type="ENUM" data-required="${param.обязательный ? '1' : '0'}">${opts}</select>`;
    } else if (type === 'REAL' || type === 'INTEGER') {
        const step = type === 'INTEGER' ? '1' : 'any';
        const minAttr = param.мин_значение != null ? ` min="${param.мин_значение}"` : ' min="0"';
        const maxAttr = param.макс_значение != null ? ` max="${param.макс_значение}"` : '';
        const vAttr = val !== '' && val != null ? ` value="${val}"` : '';
        input = `<input type="number" class="form-control product-param-input" id="${fieldId}" data-param-class-id="${param.param_class_id}" data-type="${type}" data-required="${param.обязательный ? '1' : '0'}" step="${step}"${minAttr}${maxAttr}${vAttr}>`;
    } else if (type === 'STRING') {
        input = `<input type="text" class="form-control product-param-input" id="${fieldId}" data-param-class-id="${param.param_class_id}" data-type="STRING" data-required="${param.обязательный ? '1' : '0'}" value="${escapeHtml(val ?? '')}">`;
    } else if (type === 'DATETIME') {
        const dt = val ? String(val).replace(' ', 'T').slice(0, 16) : '';
        input = `<input type="datetime-local" class="form-control product-param-input" id="${fieldId}" data-param-class-id="${param.param_class_id}" data-type="DATETIME" data-required="${param.обязательный ? '1' : '0'}" value="${dt}">`;
    } else {
        input = `<input type="text" class="form-control product-param-input" id="${fieldId}" data-param-class-id="${param.param_class_id}" data-type="STRING" data-required="${param.обязательный ? '1' : '0'}" value="${escapeHtml(val ?? '')}">`;
    }

    const hasValue = val !== '' && val != null;
    const clearBtn = hasValue
        ? `<button type="button" class="btn btn-sm btn-outline-danger" title="Удалить значение" onclick="clearProductParamField('${fieldId}')"><i class="fas fa-times"></i></button>`
        : '';

    return `<div class="form-field mb-3 product-param-row" data-param-class-id="${param.param_class_id}">
        <label class="form-label" for="${fieldId}">${escapeHtml(label)}</label>
        <div class="d-flex gap-2 align-items-start">
            <div class="flex-grow-1">${input}</div>
            ${clearBtn}
        </div>
        <div class="form-hint small text-muted">Код: ${escapeHtml(param.обозначение)}</div>
    </div>`;
}

/**
 * @param {string} containerId
 * @param {number|null} classId
 * @param {number|null} productId — при редактировании
 */
async function renderProductParamsForm(containerId, classId, productId = null) {
    const box = document.getElementById(containerId);
    if (!box) return;

    if (!classId) {
        box.innerHTML = '<p class="form-hint mb-0">Сначала выберите класс изделия — появятся параметры, привязанные к этому классу в справочнике.</p>';
        return;
    }

    box.innerHTML = '<div class="loading-state py-2"><div class="spinner spinner-sm"></div></div>';

    try {
        const classParams = await fetchClassParameters(classId);
        if (!classParams.length) {
            box.innerHTML = '<p class="alert alert-warning small mb-0">У выбранного класса нет привязанных параметров. Привяжите их в разделе «Параметры» → класс в классификаторе.</p>';
            return;
        }

        let valuesByPc = {};
        if (productId) {
            const vals = await apiRequest(`/products/${productId}/values`);
            vals.forEach(v => { valuesByPc[v.param_class_id] = v.raw_value; });
        }

        let html = '<div class="product-params-form-title">Значения параметров</div>';
        html += '<p class="form-hint small">Параметры определяются классом изделия (работа 1.3). Обязательные поля отмечены *.</p>';
        for (const param of classParams) {
            const fieldId = `${containerId}_pc_${param.param_class_id}`;
            html += await buildParamValueInputHtml(param, fieldId, valuesByPc[param.param_class_id]);
        }
        box.innerHTML = html;
        box.dataset.productId = productId ? String(productId) : '';
    } catch (e) {
        box.innerHTML = `<div class="alert alert-danger small">${escapeHtml(e.message)}</div>`;
    }
}

function clearProductParamField(fieldId) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    if (el.tagName === 'SELECT') el.value = '';
    else el.value = '';
    el.classList.remove('field-invalid');
}

function readParamInputValue(el) {
    const type = el.dataset.type;
    const raw = getVal(el.id);
    if (raw === '' || raw == null) return null;
    if (type === 'ENUM') return parseInt(raw, 10);
    if (type === 'INTEGER') return parseInt(raw, 10);
    if (type === 'REAL') return parseFloat(raw);
    return raw;
}

function validateProductParamsForm(containerId) {
    const box = document.getElementById(containerId);
    if (!box) return true;
    let ok = true;
    box.querySelectorAll('.product-param-input').forEach(el => {
        clearFieldError(el.id);
        const required = el.dataset.required === '1';
        const val = readParamInputValue(el);
        if (required && (val === null || val === '')) {
            setFieldError(el.id, 'Обязательный параметр');
            ok = false;
        }
    });
    return ok;
}

/**
 * Сохранить значения из формы (создание или редактирование).
 * @returns {Promise<{saved: number, deleted: number, errors: string[]}>}
 */
async function saveProductParamsFromForm(containerId, productId) {
    const box = document.getElementById(containerId);
    const result = { saved: 0, deleted: 0, errors: [] };
    if (!box || !productId) return result;

    const existing = await apiRequest(`/products/${productId}/values`);
    const hadValue = new Set(
        existing.filter(v => v.raw_value != null && v.raw_value !== '').map(v => v.param_class_id)
    );

    const inputs = box.querySelectorAll('.product-param-input');
    for (const el of inputs) {
        const pcId = parseInt(el.dataset.paramClassId, 10);
        const val = readParamInputValue(el);

        if (val === null || val === '') {
            if (hadValue.has(pcId)) {
                try {
                    await apiRequest(`/products/${productId}/values/${pcId}`, 'DELETE');
                    result.deleted += 1;
                } catch (e) {
                    result.errors.push(e.message);
                }
            }
            continue;
        }

        try {
            await apiRequest(`/products/${productId}/values`, 'POST', {
                param_class_id: pcId,
                value: val,
            });
            result.saved += 1;
        } catch (e) {
            result.errors.push(`${el.id}: ${e.message}`);
            setFieldError(el.id, e.message);
        }
    }
    return result;
}

function bindProductClassParams(classSelectId, containerId, getProductId = null) {
    const sel = document.getElementById(classSelectId);
    if (!sel || sel.dataset.paramsBound) return;
    sel.dataset.paramsBound = '1';
    const run = () => {
        const classId = parseInt(getVal(classSelectId), 10) || null;
        const productId = typeof getProductId === 'function' ? getProductId() : null;
        renderProductParamsForm(containerId, classId, productId);
    };
    sel.addEventListener('change', run);
}
