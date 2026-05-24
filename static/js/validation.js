/** Валидация форм: подсветка полей и сообщения об ошибках */

function getFieldWrap(el) {
    return el?.closest('.form-field') || el?.parentElement;
}

function clearFieldError(fieldId) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    el.classList.remove('field-invalid');
    const wrap = getFieldWrap(el);
    const msg = wrap?.querySelector('.field-error-msg');
    if (msg) msg.remove();
}

function clearFormErrors(root = document) {
    root.querySelectorAll('.field-invalid').forEach(el => el.classList.remove('field-invalid'));
    root.querySelectorAll('.field-error-msg').forEach(el => el.remove());
}

function setFieldError(fieldId, message) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    el.classList.add('field-invalid');
    const wrap = getFieldWrap(el);
    if (!wrap) return;
    let msg = wrap.querySelector('.field-error-msg');
    if (!msg) {
        msg = document.createElement('div');
        msg.className = 'field-error-msg';
        msg.setAttribute('role', 'alert');
        wrap.appendChild(msg);
    }
    msg.textContent = message;
}

function getVal(fieldId) {
    const el = document.getElementById(fieldId);
    if (!el) return null;
    if (el.type === 'checkbox') return el.checked;
    return (el.value ?? '').toString().trim();
}

function getNum(fieldId) {
    const v = getVal(fieldId);
    if (v === '' || v == null) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : NaN;
}

const V = {
    required(fieldId, label) {
        const v = getVal(fieldId);
        if (!v) return { fieldId, message: `${label}: обязательное поле` };
        return null;
    },
    requiredSelect(fieldId, label) {
        const v = getVal(fieldId);
        if (!v) return { fieldId, message: `${label}: выберите значение` };
        return null;
    },
    text(fieldId, label, { minLen = 1, maxLen = 200 } = {}) {
        const v = getVal(fieldId);
        if (!v) return { fieldId, message: `${label}: обязательное поле` };
        if (v.length < minLen) return { fieldId, message: `${label}: минимум ${minLen} символов` };
        if (v.length > maxLen) return { fieldId, message: `${label}: не более ${maxLen} символов` };
        return null;
    },
    nonNegative(fieldId, label, { required = true } = {}) {
        const v = getVal(fieldId);
        if (!v) return required ? { fieldId, message: `${label}: обязательное поле` } : null;
        const n = Number(v);
        if (Number.isNaN(n)) return { fieldId, message: `${label}: введите число` };
        if (n < 0) return { fieldId, message: `${label}: не может быть отрицательным` };
        return null;
    },
    positiveInt(fieldId, label, { required = true, min = 1, max = 999999 } = {}) {
        const v = getVal(fieldId);
        if (!v) return required ? { fieldId, message: `${label}: обязательное поле` } : null;
        const n = Number(v);
        if (!Number.isInteger(n) || Number.isNaN(n)) return { fieldId, message: `${label}: целое число` };
        if (n < min) return { fieldId, message: `${label}: не меньше ${min}` };
        if (n > max) return { fieldId, message: `${label}: не больше ${max}` };
        return null;
    },
    age(fieldId, label) {
        const v = getVal(fieldId);
        if (!v) return { fieldId, message: `${label}: обязательное поле` };
        const n = Number(v);
        if (Number.isNaN(n) || !Number.isInteger(n)) return { fieldId, message: `${label}: целое число лет` };
        if (n < 0 || n > 99) return { fieldId, message: `${label}: от 0 до 99 лет` };
        return null;
    },
    year(fieldId, label, { required = true } = {}) {
        const v = getVal(fieldId);
        if (!v) return required ? { fieldId, message: `${label}: обязательное поле` } : null;
        const n = Number(v);
        const y = new Date().getFullYear();
        if (Number.isNaN(n) || !Number.isInteger(n)) return { fieldId, message: `${label}: целый год` };
        if (n < 1950 || n > y + 2) return { fieldId, message: `${label}: от 1950 до ${y + 2}` };
        return null;
    },
    rangeMinMax(minId, maxId, labels = ['Минимум', 'Максимум']) {
        const minV = getVal(minId);
        const maxV = getVal(maxId);
        const errors = [];
        if (minV) {
            const mn = Number(minV);
            if (Number.isNaN(mn)) errors.push({ fieldId: minId, message: `${labels[0]}: введите число` });
            else if (mn < 0) errors.push({ fieldId: minId, message: `${labels[0]}: не может быть отрицательным` });
        }
        if (maxV) {
            const mx = Number(maxV);
            if (Number.isNaN(mx)) errors.push({ fieldId: maxId, message: `${labels[1]}: введите число` });
            else if (mx < 0) errors.push({ fieldId: maxId, message: `${labels[1]}: не может быть отрицательным` });
        }
        if (minV && maxV && !errors.length) {
            const mn = Number(minV);
            const mx = Number(maxV);
            if (mn > mx) {
                errors.push({ fieldId: maxId, message: `${labels[1]} не может быть меньше ${labels[0]}` });
            }
        }
        return errors;
    },
    ageRange(minId, maxId) {
        const errors = [];
        const minV = getVal(minId);
        const maxV = getVal(maxId);
        if (minV) {
            const e = V.age(minId, 'Мин. возраст');
            if (e) errors.push(e);
        }
        if (maxV) {
            const e = V.age(maxId, 'Макс. возраст');
            if (e) errors.push(e);
        }
        if (minV && maxV && !errors.length) {
            if (Number(minV) > Number(maxV)) {
                errors.push({ fieldId: maxId, message: 'Макс. возраст не может быть меньше минимального' });
            }
        }
        return errors;
    },
};

function runValidation(rules) {
    clearFormErrors();
    const errors = [];
    for (const rule of rules) {
        const result = rule();
        if (!result) continue;
        if (Array.isArray(result)) errors.push(...result);
        else errors.push(result);
    }
    errors.forEach(e => setFieldError(e.fieldId, e.message));
    if (errors.length) {
        const first = document.getElementById(errors[0].fieldId);
        first?.focus();
        showToast('Исправьте ошибки в форме', 'error');
    }
    return errors.length === 0;
}

/** Валидация панели фильтров (без модалки) */
function validateFilterPanel(fieldIds, rules) {
    fieldIds.forEach(clearFieldError);
    const errors = [];
    rules.forEach(rule => {
        const result = rule();
        if (!result) return;
        if (Array.isArray(result)) errors.push(...result);
        else errors.push(result);
    });
    errors.forEach(e => setFieldError(e.fieldId, e.message));
    return errors.length === 0;
}
