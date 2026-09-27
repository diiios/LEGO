"""
Проверка шага 4 работы 5: модификации и «действующий состав».

Запуск (из папки проекта, venv активирован, база в Docker работает):
    python checks/lab5_step4_check.py

Создаёт ВРЕМЕННЫЕ класс, единицы и изделия TEST-L5-*, проверяет и всё удаляет.

Базовое изделие «Набор»:                    Модификация «Тёмная сторона» (свои строки):
    Башня × 2          флаг 1 (наследуется)     Кирпич красный × 0   ← исключить
    Кирпич красный × 10 флаг 1 (наследуется)    Кирпич синий × 10    ← добавить
    Люк × 2            флаг 0 (НЕ наследуется)  Вейдер × 1           ← добавить
Башня ← Кирпич красный × 20;  кирпичи (оба) ← ABS 2 г на 1 шт
Ожидаемый действующий состав модификации: Башня × 2 (из базы), Кирпич синий × 10, Вейдер × 1
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import config
from models import Base, Classificator, Product, BOMItem, SpecChange, UnitOfMeasure
from lego_classifier import LegoClassifier

engine = create_engine(os.getenv("LAB5_DB_URL", config.DATABASE_URL))
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()
lc = LegoClassifier(engine)
passed = failed = 0


def ok(title, condition, details=""):
    global passed, failed
    passed += bool(condition)
    failed += (not condition)
    print(f"{'✅' if condition else '❌'} {title}" + (f"\n     {details}" if details else ""))


def expect(title, result, expect_success):
    ok(title, result.get("success") == expect_success,
       f"ожидали: {'успех' if expect_success else 'отказ'}; ответ: {result.get('message', 'успех')}")


def cleanup():
    ids = [p.id for p in db.query(Product).filter(Product.артикул.like("TEST-L5-%")).all()]
    if ids:
        db.query(SpecChange).filter(SpecChange.изделие_id.in_(ids)).delete(synchronize_session=False)
        db.query(BOMItem).filter(BOMItem.изделие_id.in_(ids)).delete(synchronize_session=False)
        db.query(BOMItem).filter(BOMItem.компонент_id.in_(ids)).delete(synchronize_session=False)
        db.query(Product).filter(Product.id.in_(ids)).update({"базовое_изделие_id": None}, synchronize_session=False)
        db.query(Product).filter(Product.id.in_(ids)).delete(synchronize_session=False)
    db.query(UnitOfMeasure).filter(UnitOfMeasure.обозначение.like("TEST-%")).delete(synchronize_session=False)
    db.query(Classificator).filter(Classificator.название.like("ТЕСТ Л5%")).delete(synchronize_session=False)
    db.commit()


def product(name, sku, cls):
    p = Product(класс_id=cls, наименование=name, артикул=sku)
    db.add(p)
    db.commit()
    return p.id


def eff(pid):
    """Действующий состав: {компонент: (расход, источник)}"""
    return {r["компонент"]: (r["расход"], r["источник"]) for r in lc.get_effective_spec(db, pid)["строки"]}


def calc(pid):
    return {r["компонент"]: r["кол_на_1"] for r in lc.calc_bom(db, pid, 1)["строки"]}


def show_eff(pid, title):
    res = lc.get_effective_spec(db, pid)
    print(f"   Действующий состав «{title}»:")
    for r in res["строки"]:
        print(f"     {r['компонент']} × {r['расход']:g}   [{r['источник']}]")
    if res["исключено"]:
        print(f"     исключено: {', '.join(x['компонент'] for x in res['исключено'])}")


cleanup()
print("=== Подготовка ===")
pcs = lc.add_unit(db, "TEST-шт", "Штука (тест)")["unit_id"]
g = lc.add_unit(db, "TEST-г", "Грамм (тест)")["unit_id"]
cls = Classificator(название="ТЕСТ Л5 (временный)", тип_элемента="промежуточный")
db.add(cls)
db.commit()
SET = product("ТЕСТ Набор", "TEST-L5-SET", cls.id)
TOWER = product("ТЕСТ Башня", "TEST-L5-TOWER", cls.id)
RED = product("ТЕСТ Кирпич красный", "TEST-L5-RED", cls.id)
BLUE = product("ТЕСТ Кирпич синий", "TEST-L5-BLUE", cls.id)
LUKE = product("ТЕСТ Люк", "TEST-L5-LUKE", cls.id)
VADER = product("ТЕСТ Вейдер", "TEST-L5-VADER", cls.id)
ABS = product("ТЕСТ ABS", "TEST-L5-ABS", cls.id)
lc.add_bom_item(db, SET, TOWER, 2, ед_изм_id=pcs)
lc.add_bom_item(db, SET, RED, 10, ед_изм_id=pcs)
lc.add_bom_item(db, SET, LUKE, 2, ед_изм_id=pcs, флаг_базы=False)
lc.add_bom_item(db, TOWER, RED, 20, ед_изм_id=pcs)
lc.add_bom_item(db, RED, ABS, 2, ед_изм_id=g)
lc.add_bom_item(db, BLUE, ABS, 2, ед_изм_id=g)
print("Базовое изделие собрано: Башня × 2 (флаг 1), Кирпич красный × 10 (флаг 1), Люк × 2 (флаг 0)\n")

print("=== 1. Создание модификации ===")
r = lc.create_modification(db, SET, "ТЕСТ Набор — Тёмная сторона", "TEST-L5-DARK")
expect("Создать модификацию", r, True)
MOD = r["product_id"]
mod = db.get(Product, MOD)
ok("У модификации заполнено базовое_изделие_id = id базы", mod.базовое_изделие_id == SET)
ok("Класс модификации = класс базы", mod.класс_id == cls.id)
ok("Своих строк у модификации нет (ничего не скопировано)", lc.get_spec(db, MOD) == [])
expect("Модификация несуществующего изделия", lc.create_modification(db, 999999, "X"), False)
expect("Пустое наименование", lc.create_modification(db, SET, "  "), False)
expect("Повтор артикула", lc.create_modification(db, SET, "Y", "TEST-L5-DARK"), False)
show_eff(MOD, "Тёмная сторона (сразу после создания)")
e = eff(MOD)
ok("Сразу после создания: Башня и Кирпич красный — из базы; Люка нет (флаг 0)",
   set(e) == {"ТЕСТ Башня", "ТЕСТ Кирпич красный"} and all(v[1].startswith("из базы") for v in e.values()))

print("\n=== 2. Отличия модификации ===")
expect("Исключить Кирпич красный (расход 0)", lc.add_bom_item(db, MOD, RED, 0, ед_изм_id=pcs), True)
expect("Добавить Кирпич синий × 10", lc.add_bom_item(db, MOD, BLUE, 10, ед_изм_id=pcs), True)
expect("Добавить Вейдера × 1", lc.add_bom_item(db, MOD, VADER, 1, ед_изм_id=pcs), True)
expect("Исключить Люка (он не наследуется — исключать нечего)", lc.add_bom_item(db, MOD, LUKE, 0), False)
expect("Расход 0 у базового изделия", lc.add_bom_item(db, SET, VADER, 0), False)
show_eff(MOD, "Тёмная сторона")
e = eff(MOD)
ok("Итог: Башня × 2 (из базы), Кирпич синий × 10 (своя), Вейдер × 1 (своя)",
   e == {"ТЕСТ Башня": (2, "из базы: ТЕСТ Набор"), "ТЕСТ Кирпич синий": (10, "своя"), "ТЕСТ Вейдер": (1, "своя")},
   f"{e}")
ok("База не изменилась: Башня, Кирпич красный, Люк", set(eff(SET)) == {"ТЕСТ Башня", "ТЕСТ Кирпич красный", "ТЕСТ Люк"})

print("\n=== 3. Своя строка заменяет строку базы ===")
r = lc.add_bom_item(db, MOD, TOWER, 3, ед_изм_id=pcs)
expect("В модификации Башня × 3 (вместо 2 из базы)", r, True)
ok("Теперь Башня × 3 [своя]", eff(MOD)["ТЕСТ Башня"] == (3, "своя"))
lc.delete_bom_item(db, r["item_id"])
ok("Удалили свою строку → снова Башня × 2 [из базы]", eff(MOD)["ТЕСТ Башня"] == (2, "из базы: ТЕСТ Набор"))

print("\n=== 4. Изменение базы доходит до модификации автоматически ===")
tower_line = next(x for x in lc.get_spec(db, SET) if x["компонент"] == "ТЕСТ Башня")["id"]
lc.update_bom_item(db, tower_line, расход=4)
ok("В базе Башня 2 → 4: в модификации тоже 4, хотя её мы не трогали", eff(MOD)["ТЕСТ Башня"][0] == 4)
lc.update_bom_item(db, tower_line, расход=2)

print("\n=== 5. FIND_BOM и CALC_BOM для модификации ===")
tree = lc.find_bom(db, MOD, 1)
for row in tree["строки"]:
    print(f"     {'   ' * (row['уровень'] - 1)}{row['компонент']}: {row['кол_на_1']:g}"
          f"{'   (из базы)' if row['из_базы'] else ''}")
c_mod = calc(MOD)
c_set = calc(SET)
print(f"   CALC модификации: {c_mod}")
print(f"   CALC базы:        {c_set}")
ok("Модификация: кирпичей красных 40 (внутри башен — башня ведь не менялась)", c_mod["ТЕСТ Кирпич красный"] == 40)
ok("Модификация: синих 10, Вейдер 1, Люка нет", c_mod.get("ТЕСТ Кирпич синий") == 10
   and c_mod.get("ТЕСТ Вейдер") == 1 and "ТЕСТ Люк" not in c_mod)
ok("Модификация: ABS = 40 × 2 + 10 × 2 = 100 г", c_mod["ТЕСТ ABS"] == 100)
ok("База: красных 40 + 10 = 50, Люк 2, ABS 100", c_set["ТЕСТ Кирпич красный"] == 50
   and c_set["ТЕСТ Люк"] == 2 and c_set["ТЕСТ ABS"] == 100)

print("\n=== 6. Модификация модификации ===")
r = lc.create_modification(db, MOD, "ТЕСТ Набор — Тёмная сторона Deluxe", "TEST-L5-DELUXE")
expect("Создать модификацию от модификации", r, True)
DLX = r["product_id"]
expect("Deluxe ← Люк × 1", lc.add_bom_item(db, DLX, LUKE, 1, ед_изм_id=pcs), True)
show_eff(DLX, "Deluxe")
ok("Deluxe: Башня (из «Набор»), Кирпич синий и Вейдер (из «Тёмная сторона»), Люк (своя)",
   set(eff(DLX)) == {"ТЕСТ Башня", "ТЕСТ Кирпич синий", "ТЕСТ Вейдер", "ТЕСТ Люк"} and
   eff(DLX)["ТЕСТ Башня"][1] == "из базы: ТЕСТ Набор" and eff(DLX)["ТЕСТ Вейдер"][1] == "из базы: ТЕСТ Набор — Тёмная сторона")
mods = lc.get_modifications(db, SET)
ok("Список модификаций «Набора»: одна — Тёмная сторона (у неё 1 своя модификация)",
   len(mods) == 1 and mods[0]["id"] == MOD and mods[0]["модификаций"] == 1, f"{mods}")

print("\n=== 7. Защита от циклов учитывает модификации ===")
expect("Добавить в базу её же модификацию", lc.add_bom_item(db, SET, MOD, 1), False)

print("\n=== 8. Журнал ===")
for pid, title in [(SET, "Набор"), (MOD, "Тёмная сторона")]:
    rows = [x for x in lc.get_spec_changes(db, pid) if x["действие"] == "МОДИФИКАЦИЯ"]
    for x in rows:
        print(f"     {title}: [{x['действие']}] {x['описание']}")
    ok(f"В журнале «{title}» есть запись МОДИФИКАЦИЯ", len(rows) >= 1)

cleanup()
print(f"\n=== Итог: {passed} проверок прошло, {failed} не прошло. Тестовые данные удалены. ===")
