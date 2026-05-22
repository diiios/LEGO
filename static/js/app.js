async function loadSets() {
    const response = await fetch('/sets');
    const sets = await response.json();
    let html = '<h2>Наборы</h2><table class="table table-bordered">...</table>';
    // заполнить таблицу
    document.getElementById('content').innerHTML = html;
}

// Функция для построения дерева из плоского списка
function buildTree(flatList, parentId = null) {
    const tree = [];
    for (const item of flatList) {
        if (item.parent_id === parentId) {
            const children = buildTree(flatList, item.id);
            if (children.length > 0) {
                item.children = children;
            } else {
                item.children = [];
            }
            tree.push(item);
        }
    }
    // Сортируем по sort_order
    tree.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    return tree;
}

// Функция для отображения дерева в HTML (рекурсивная)
function renderTree(node, level = 0) {
    const indent = ' '.repeat(level * 4);
    const icon = getNodeIcon(node.node_type);
    let html = `
        <div class="tree-node" data-id="${node.id}" data-type="${node.node_type}" style="margin-left: ${level * 20}px">
            <span class="tree-toggle" onclick="toggleNode(this)">▼</span>
            <span class="tree-icon">${icon}</span>
            <span class="tree-name" onclick="selectNode(${node.id}, '${node.name}')">${node.name}</span>
            <span class="tree-type">(${node.node_type})</span>
            <div class="tree-actions">
                <button onclick="editNode(${node.id})" class="btn-sm btn-warning">✏️</button>
                <button onclick="deleteNode(${node.id})" class="btn-sm btn-danger">🗑️</button>
                <button onclick="addChildNode(${node.id})" class="btn-sm btn-success">➕</button>
            </div>
        </div>
        <div class="tree-children" data-parent="${node.id}">
    `;
    
    if (node.children && node.children.length > 0) {
        for (const child of node.children) {
            html += renderTree(child, level + 1);
        }
    }
    
    html += `</div>`;
    
    // Добавляем продукты, если есть
    if (node.products && node.products.length > 0) {
        html += `<div class="tree-products" style="margin-left: ${(level + 1) * 20}px">`;
        for (const product of node.products) {
            const productIcon = getProductIcon(product.type);
            html += `
                <div class="tree-product" data-product-id="${product.id}">
                    <span class="tree-icon">${productIcon}</span>
                    <span>${product.name}</span>
                    <span class="product-type">[${product.type}]</span>
                </div>
            `;
        }
        html += `</div>`;
    }
    
    return html;
}

// Вспомогательные функции для иконок
function getNodeIcon(nodeType) {
    const icons = {
        'промежуточный': '📁',
        'терминальный': '📄',
        'набор': '🧩',
        'тематика': '🏷️',
        'возрастная_категория': '🎂'
    };
    return icons[nodeType] || '📦';
}

function getProductIcon(productType) {
    const icons = {
        'set': '🧩',
        'part': '🔧',
        'minifigure': '🧸'
    };
    return icons[productType] || '📦';
}

// Функция для сворачивания/разворачивания узла
function toggleNode(element) {
    const treeNode = element.closest('.tree-node');
    const childrenDiv = treeNode.nextElementSibling;
    if (childrenDiv && childrenDiv.classList.contains('tree-children')) {
        if (childrenDiv.style.display === 'none') {
            childrenDiv.style.display = 'block';
            element.textContent = '▼';
        } else {
            childrenDiv.style.display = 'none';
            element.textContent = '▶';
        }
    }
}

// Функция для загрузки и отображения всего дерева
async function loadTree() {
    try {
        const response = await fetch('/categories/tree?include_products=true');
        const trees = await response.json();
        
        let html = '<div class="tree-container">';
        for (const root of trees) {
            html += renderTree(root);
        }
        html += '</div>';
        
        document.getElementById('content').innerHTML = html;
    } catch (error) {
        console.error('Ошибка загрузки дерева:', error);
        document.getElementById('content').innerHTML = '<div class="alert alert-danger">Ошибка загрузки дерева</div>';
    }
}

// Функции для работы с узлами
async function selectNode(nodeId, nodeName) {
    console.log(`Выбран узел: ${nodeName} (ID: ${nodeId})`);
    // Загрузить информацию об узле
    await loadNodeInfo(nodeId);
}

async function loadNodeInfo(nodeId) {
    try {
        const response = await fetch(`/categories/${nodeId}/descendants`);
        const descendants = await response.json();
        
        // Показать информацию в боковой панели или модальном окне
        showNodeInfo(nodeId, descendants);
    } catch (error) {
        console.error('Ошибка загрузки информации об узле:', error);
    }
}

async function editNode(nodeId) {
    const newName = prompt('Введите новое название узла:');
    if (newName) {
        // Здесь нужен эндпоинт для обновления названия
        try {
            const response = await fetch(`/categories/${nodeId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName })
            });
            const result = await response.json();
            if (result.success) {
                alert('Узел успешно обновлён');
                loadTree(); // Перезагрузить дерево
            } else {
                alert('Ошибка: ' + result.message);
            }
        } catch (error) {
            console.error('Ошибка обновления:', error);
        }
    }
}

async function deleteNode(nodeId) {
    if (confirm('Вы уверены, что хотите удалить этот узел? Все дети также будут удалены!')) {
        try {
            const response = await fetch(`/categories/${nodeId}`, {
                method: 'DELETE'
            });
            const result = await response.json();
            if (result.success) {
                alert('Узел удалён');
                loadTree(); // Перезагрузить дерево
            } else {
                alert('Ошибка: ' + result.message);
            }
        } catch (error) {
            console.error('Ошибка удаления:', error);
        }
    }
}

async function addChildNode(parentId) {
    const childName = prompt('Введите название нового узла:');
    if (childName) {
        try {
            const response = await fetch('/categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: childName,
                    parent_id: parentId,
                    node_type: 'промежуточный'
                })
            });
            const result = await response.json();
            if (result.success) {
                alert('Узел успешно создан');
                loadTree(); // Перезагрузить дерево
            } else {
                alert('Ошибка: ' + result.message);
            }
        } catch (error) {
            console.error('Ошибка создания узла:', error);
        }
    }
}

// Функция для отображения информации об узле
function showNodeInfo(nodeId, descendants) {
    const modalHtml = `
        <div class="modal fade" id="nodeInfoModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Информация об узле #${nodeId}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <h6>Потомки:</h6>
                        <ul>
                            ${descendants.map(d => `<li>${d.название} (${d.тип_элемента})</li>`).join('')}
                        </ul>
                        <p>Всего потомков: ${descendants.length}</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Удалить старый модал, если есть
    const oldModal = document.getElementById('nodeInfoModal');
    if (oldModal) oldModal.remove();
    
    // Добавить и показать новый
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('nodeInfoModal'));
    modal.show();
}