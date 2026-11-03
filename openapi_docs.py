# openapi_docs.py
"""
Оформление документации Swagger (/docs): всё на русском языке, разделы по заданиям,
внутри раздела запросы упорядочены: сначала получение (GET), затем создание (POST),
изменение (PUT) и удаление (DELETE).
"""
import re
from typing import Any, Callable, Dict, List, Tuple

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

TITLE = "API информационной системы LEGO"
DESCRIPTION = """
Сервер практических работ по дисциплине «Методы и средства проектирования информационных систем».

Разделы сгруппированы по заданиям: **ПР1–ПР4** (6-й семестр) – классификатор, перечисления, справочник,
хозяйственные операции; **ПР5** – материальные спецификации (BOM); **ПР6** – маршрутная технология;
**ПР7** – заказы на изделия с вариантами исполнения и сложными ограничениями.
Внутри раздела запросы идут в порядке: получение → создание → изменение → удаление.

Как пользоваться: раскрыть раздел → выбрать запрос → **Try it out** → заполнить параметры → **Execute**.
Коды ответа: 200 – успешно, 400 – нарушено бизнес-правило, 404 – не найдено, 422 – неверные параметры запроса.
"""

# --------------------------------------------------------------------------- разделы (порядок = порядок в Swagger)
TAGS: List[Tuple[str, str]] = [
    ("ПР1. Классификатор: дерево и поиск", "Просмотр дерева классов, поиск потомков, родителей, терминальных классов, диагностика циклов"),
    ("ПР1. Классификатор: ведение", "Создание, перемещение, изменение порядка и удаление классов"),
    ("ПР2. Перечисления", "Перечисления и их значения, порядок значений"),
    ("ПР3. Параметры классов", "Параметры и их привязка к классам с наследованием"),
    ("ПР3. Справочник изделий", "Изделия, значения параметров, отбор по параметрам"),
    ("ПР4. Типы хозяйственных операций", "Классы ХО, роли и параметры типа"),
    ("ПР4. Субъекты хозяйственной деятельности", "Участники операций и подразделения"),
    ("ПР4. Хозяйственные операции", "Экземпляры ХО: участники, значения параметров, позиции"),
    ("Каталог LEGO: наборы", "Наборы и их состав"),
    ("Каталог LEGO: детали", "Детали"),
    ("Каталог LEGO: мини-фигурки", "Мини-фигурки"),
    ("Каталог LEGO: справочники", "Тематики, возрастные категории, типы деталей"),
    ("Каталог LEGO: поиск", "Поиск наборов и деталей"),
    ("ПР5. Единицы измерения", "Справочник единиц измерения"),
    ("ПР5. Изделия и спецификации", "Тип изделия, спецификация 1-го уровня, позиции спецификации"),
    ("ПР5. Модификации и изменения", "Создание модификаций, исключение компонентов, журнал изменений"),
    ("ПР5. Расчёты по спецификации", "FIND_BOM, CALC_BOM, применяемость"),
    ("ПР6. Справочники маршрутной технологии", "Классы операций, профессии, квалификации (разряды)"),
    ("ПР6. Групповые рабочие центры (ГРЦ)", "Ведение ГРЦ"),
    ("ПР6. Инструмент и оснастка", "Ведение инструмента и назначение его операциям"),
    ("ПР6. Технологический маршрут", "Изделия-операции (ТЕХ / ЗАКУПКА), входные ресурсы"),
    ("ПР6. Типовые технологические процессы", "Типовые ТП, параметры ТПП, типовые операции и ресурсы, применение к операции"),
    ("ПР6. Расчёты по маршруту", "FIND_TM, MR_Q, SUM_MR, TR_TO, трудоёмкость по этапам, загрузка ГРЦ, себестоимость"),
    ("ПР7. Типовые изделия и параметры конфигурации", "Шаблоны изделий, состав параметров конфигурации (GET_CONFIG_PARAMS), формула цены"),
    ("ПР7. Ограничения и библиотека функций", "Ограничения шаблонов, разбор выражений, функции с формальными параметрами"),
    ("ПР7. Варианты исполнения", "CHECK_CONSTRAINTS, CREATE_VARIANT, значения параметров варианта"),
    ("ПР7. Заказы", "Регистрация, состав заказа (ADD_TO_ORDER), согласование"),
    ("Служебные", "Состояние сервера, тестовые данные, очистка базы"),
]

# правило: (раздел, функция (метод, путь) -> bool); первое подходящее
R: List[Tuple[str, Callable[[str, str], bool]]] = [
    ("Служебные", lambda m, p: p in ("/api", "/test-data", "/clear", "/reset-database", "/tm/typical/stats")),
    # ПР7
    ("ПР7. Заказы", lambda m, p: p.startswith("/cfg/orders") or p.startswith("/cfg/order-items")),
    ("ПР7. Варианты исполнения", lambda m, p: p.startswith("/cfg/variants") or bool(re.match(
        r"^/cfg/templates/\{product_id\}/(check|variants)$", p))),
    ("ПР7. Ограничения и библиотека функций", lambda m, p: p.startswith(("/cfg/constraints", "/cfg/functions",
        "/cfg/expressions")) or p == "/cfg/templates/{product_id}/constraints"),
    ("ПР7. Типовые изделия и параметры конфигурации", lambda m, p: p.startswith("/cfg/")),
    # ПР6
    ("ПР6. Расчёты по маршруту", lambda m, p: bool(re.match(
        r"^/tm/(products/\{product_id\}/(find|materials|labor|labor-stages|cost)|operations/\{op_id\}/(calc|mr)|work-centers/\{wc_id\}/load)$", p))),
    ("ПР6. Справочники маршрутной технологии", lambda m, p: p in ("/tm/references", "/tm/workforce")),
    ("ПР6. Групповые рабочие центры (ГРЦ)", lambda m, p: p.startswith("/tm/work-centers")),
    ("ПР6. Инструмент и оснастка", lambda m, p: p.startswith("/tm/tools") or p.startswith("/tm/operation-tools")
        or p == "/tm/operations/{op_id}/tools"),
    ("ПР6. Типовые технологические процессы", lambda m, p: p.startswith("/tm/typical") or p == "/tm/operations/{op_id}/typical"),
    ("ПР6. Технологический маршрут", lambda m, p: p.startswith("/tm/")),
    # ПР5
    ("ПР5. Единицы измерения", lambda m, p: p.startswith("/bom/units")),
    ("ПР5. Расчёты по спецификации", lambda m, p: bool(re.match(r"^/bom/products/\{product_id\}/(find|calc|where-used)$", p))),
    ("ПР5. Модификации и изменения", lambda m, p: p.startswith("/bom/modifications") or p.startswith("/bom/changes")
        or bool(re.match(r"^/bom/products/\{product_id\}/(modifications|changes|exclude)$", p))),
    ("ПР5. Изделия и спецификации", lambda m, p: p.startswith("/bom/")),
    # ПР1
    ("ПР1. Классификатор: дерево и поиск", lambda m, p: (m == "get" and p.startswith("/categories")) or p == "/cycles"),
    ("ПР1. Классификатор: ведение", lambda m, p: p.startswith("/categories")),
    # ПР2–ПР4
    ("ПР2. Перечисления", lambda m, p: p.startswith("/enumerations") or p.startswith("/enum-values")),
    ("ПР3. Параметры классов", lambda m, p: p.startswith("/parameters") or p.startswith("/classes/")),
    ("ПР3. Справочник изделий", lambda m, p: p.startswith("/products")),
    ("ПР4. Типы хозяйственных операций", lambda m, p: p.startswith("/ho-types") or p.startswith("/ho-roles")),
    ("ПР4. Субъекты хозяйственной деятельности", lambda m, p: p.startswith("/subjects")),
    ("ПР4. Хозяйственные операции", lambda m, p: p.startswith("/ho-operations")),
    # каталог LEGO
    ("Каталог LEGO: поиск", lambda m, p: p.startswith("/search")),
    ("Каталог LEGO: наборы", lambda m, p: p.startswith("/sets")),
    ("Каталог LEGO: детали", lambda m, p: p.startswith("/parts")),
    ("Каталог LEGO: мини-фигурки", lambda m, p: p.startswith("/minifigures")),
    ("Каталог LEGO: справочники", lambda m, p: p.startswith(("/themes", "/age-categories", "/part-types"))),
]

# названия запросов, у которых нет русского описания
SUMMARY: Dict[Tuple[str, str], str] = {
    ("get", "/api"): "Состояние сервера и ссылки на интерфейсы",
    ("get", "/sets"): "Получить все наборы",
    ("post", "/parts"): "Создать деталь",
    ("get", "/parts/{part_id}"): "Получить деталь по ID",
    ("put", "/parts/{part_id}"): "Обновить деталь",
    ("put", "/part-types/{type_id}"): "Обновить тип детали",
    ("get", "/ho-types"): "Получить классификатор типов ХО",
    ("post", "/ho-types"): "Создать тип ХО",
    ("post", "/ho-types/{type_id}/roles"): "Добавить роль к типу ХО",
    ("get", "/ho-types/{type_id}/roles"): "Получить роли типа ХО",
    ("post", "/ho-types/{type_id}/parameters"): "Добавить параметр к типу ХО",
    ("get", "/ho-types/{type_id}/parameters"): "Получить параметры типа ХО",
    ("get", "/subjects"): "Получить субъектов хозяйственной деятельности",
    ("post", "/subjects"): "Создать субъекта хозяйственной деятельности",
    ("get", "/ho-operations"): "Получить список хозяйственных операций",
    ("post", "/ho-operations"): "Создать хозяйственную операцию",
    ("put", "/ho-operations/{op_id}/actors"): "Назначить участника на роль в ХО",
    ("post", "/ho-operations/{op_id}/values"): "Задать значение параметра ХО",
    ("post", "/ho-operations/{op_id}/items"): "Добавить позицию (изделие) в ХО",
    ("get", "/ho-operations/{op_id}"): "Получить ХО со всеми характеристиками",
    ("post", "/ho-operations/filter"): "Поиск ХО заданного класса",
    ("post", "/tm/operations/{op_id}/typical"): "Применить типовой ТП к операции со значениями параметров",
}

PARAMS: Dict[str, str] = {
    "product_id": "id изделия", "quantity": "Количество изделий q (больше 0)", "own": "true – только операции самого изделия, без компонентов",
    "op_id": "id строки маршрута (операции) или хозяйственной операции", "wc_id": "id ГРЦ", "tool_id": "id инструмента",
    "input_id": "id позиции входного ресурса", "link_id": "id назначения инструмента операции", "tp_id": "id типового ТП",
    "kind": "Вид элемента или типа изделия", "item_id": "id элемента", "node_id": "id класса (узла классификатора)",
    "parent_id": "id родительского класса", "class_id": "id класса", "enum_id": "id перечисления", "value_id": "id значения перечисления",
    "param_id": "id параметра", "parameter_id": "id параметра", "param_class_id": "id привязки параметра к классу",
    "unit_id": "id единицы измерения", "position_id": "id позиции спецификации", "set_id": "id набора", "part_id": "id детали",
    "mf_id": "id мини-фигурки", "theme_id": "id тематики", "cat_id": "id возрастной категории", "type_id": "id типа",
    "role_id": "id роли", "subject_id": "id субъекта", "operation_id": "id операции", "skip": "Сколько записей пропустить",
    "limit": "Сколько записей вернуть", "date_from": "Дата начала периода", "date_to": "Дата окончания периода",
    "include_inherited": "Учитывать параметры, унаследованные от родителей",
    "pc_id": "id параметра класса", "constraint_id": "id ограничения", "variant_id": "id варианта исполнения",
    "function_id": "id функции", "order_id": "id заказа", "вид": "Вид конфигурации: ПРОСТОЕ, ТИПОВОЕ или ВАРИАНТ", "include_products": "Включить изделия в узлы дерева",
}

METHOD_ORDER = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}
HIDDEN = {"/", "/user", "/admin", "/app"}   # HTML-страницы интерфейса – не API


def _ru(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


SORTER = """operationsSorter: function (a, b) {
        var order = {get: 0, post: 1, put: 2, patch: 3, delete: 4};
        var d = order[a.get("method")] - order[b.get("method")];
        return d !== 0 ? d : a.get("path").localeCompare(b.get("path"));
    },
    presets: ["""


def setup_openapi(app: FastAPI) -> None:
    params = {"docExpansion": "none", "defaultModelsExpandDepth": -1, "filter": True, "displayRequestDuration": True}
    docs_url = app.docs_url or "/docs"
    # своя страница /docs: та же стандартная Swagger UI + сортировка GET → POST → PUT → DELETE внутри раздела
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != docs_url]

    @app.get(docs_url, include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        page = get_swagger_ui_html(openapi_url=app.openapi_url, title=TITLE + " – Swagger",
                                   swagger_ui_parameters=params).body.decode()
        return HTMLResponse(page.replace("presets: [", SORTER, 1))

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=TITLE, version=app.version, description=DESCRIPTION, routes=app.routes)
        tag_rank = {t: i for i, (t, _) in enumerate(TAGS)}
        ops = []
        for path, methods in schema["paths"].items():
            if path in HIDDEN:
                continue
            for m, op in methods.items():
                tag = next((t for t, f in R if f(m, path)), "Служебные")
                op["tags"] = [tag]
                summ = SUMMARY.get((m, path))
                if not summ and not _ru(op.get("summary", "")):
                    first = (op.get("description") or "").strip().split("\n")[0].strip()
                    summ = first if _ru(first) else None
                if summ:
                    op["summary"] = summ
                if not _ru(op.get("description", "")):
                    op.pop("description", None)
                for prm in op.get("parameters", []):
                    if not prm.get("description") and prm["name"] in PARAMS:
                        prm["description"] = PARAMS[prm["name"]]
                for code, r in op.get("responses", {}).items():
                    r["description"] = {"200": "Успешный ответ", "201": "Создано",
                                        "422": "Ошибка проверки параметров запроса"}.get(code, r.get("description"))
                ops.append((tag_rank.get(tag, 999), METHOD_ORDER.get(m, 9), path, m, op))
        ops.sort(key=lambda x: x[:3])
        # одна операция – один ключ пути в нужном порядке: в Swagger UI порядок внутри раздела = порядок путей
        paths: Dict[str, Dict[str, Any]] = {}
        for _, _, path, m, op in ops:
            paths.setdefault(path, {})[m] = op
        # путь с методами из разных мест сортировки остаётся одним объектом: переупорядочим методы внутри
        for path in paths:
            paths[path] = dict(sorted(paths[path].items(), key=lambda kv: METHOD_ORDER.get(kv[0], 9)))
        schema["paths"] = paths
        schema["tags"] = [{"name": t, "description": d} for t, d in TAGS]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
