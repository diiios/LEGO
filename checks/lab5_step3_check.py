"""
Проверка шага 3 работы 5: FIND_BOM (дерево на всю глубину) и CALC_BOM (сводные нормы).
ЕИ — только подпись строки, пересчёта единиц нет.

Запуск (из папки проекта, venv активирован, база в Docker работает):
    python checks/lab5_step3_check.py

Создаёт ВРЕМЕННЫЕ классы «ТЕСТ Л5 …», единицы «TEST-г / TEST-шт / TEST-кг» и изделия TEST-L5-*,
проверяет расчёты и в конце всё удаляет. Твои данные не трогает.

Тестовая конструкция (на 1 набор):
    Набор
    ├── Башня × 2 шт
    │   └── Кирпич × 20 шт          ← ABS 23 г на 10 шт кирпича (т.е. 2.3 г/шт)
    └── Корпус × 2 шт               ← ABS 15 г на 1 шт корпуса
    ABS = 40 × 2.3 + 2 × 15 = 92 + 30 = 122 г
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
        db.query(Product).filter(Product.id.in_(ids)).delete(synchronize_session=False)
    db.query(UnitOfMeasure).filter(UnitOfMeasure.обозначение.like("TEST-%")).delete(synchronize_session=False)
    db.query(Classificator).filter(Classificator.название.like("ТЕСТ Л5%")).update(
        {"родительский_id": None}, synchronize_session=False)
    db.query(Classificator).filter(Classificator.название.like("ТЕСТ Л5%")).delete(synchronize_session=False)
    db.commit()


def node(name, parent=None):
    c = Classificator(название=name, тип_элемента="промежуточный", родительский_id=parent)
    db.add(c)
    db.commit()
    return c.id


def product(name, sku, cls):
    p = Product(класс_id=cls, наименование=name, артикул=sku)
    db.add(p)
    db.commit()
    return p.id


def calc_map(res):
    return {r["компонент"]: (r["кол_на_N"], r["ед_изм"]) for r in res["строки"]}


cleanup()
print("=== Подготовка ===")
g = lc.add_unit(db, "TEST-г", "Грамм (тест)")["unit_id"]
pcs = lc.add_unit(db, "TEST-шт", "Штука (тест)")["unit_id"]
kg = lc.add_unit(db, "TEST-кг", "Килограмм (тест)")["unit_id"]

root = node("ТЕСТ Л5 корень")
c_mat = node("ТЕСТ Л5 Материалы", root)
c_parts = node("ТЕСТ Л5 Детали", root)
c_asm = node("ТЕСТ Л5 Узлы", root)

SET = product("ТЕСТ Набор", "TEST-L5-SET", c_asm)
TOWER = product("ТЕСТ Башня", "TEST-L5-TOWER", c_asm)
BRICK = product("ТЕСТ Кирпич", "TEST-L5-BRICK", c_parts)
BODY = product("ТЕСТ Корпус", "TEST-L5-BODY", c_parts)
ABS = product("ТЕСТ ABS", "TEST-L5-ABS", c_mat)
print("Созданы ЕИ, классы (Материалы / Детали / Узлы) и 5 изделий\n")

print("=== 1. Спецификация ===")
expect("Набор ← Башня × 2 шт", lc.add_bom_item(db, SET, TOWER, 2, ед_изм_id=pcs), True)
expect("Набор ← Корпус × 2 шт", lc.add_bom_item(db, SET, BODY, 2, ед_изм_id=pcs), True)
expect("Башня ← Кирпич × 20 шт", lc.add_bom_item(db, TOWER, BRICK, 20, ед_изм_id=pcs), True)
expect("Кирпич ← ABS 23 г на 10 шт", lc.add_bom_item(db, BRICK, ABS, 23, для_количества=10, ед_изм_id=g), True)
expect("Корпус ← ABS 15 г", lc.add_bom_item(db, BODY, ABS, 15, ед_изм_id=g), True)

print("\n=== 2. FIND_BOM (дерево) на 10 наборов ===")
tree = lc.find_bom(db, SET, 10)
for r in tree["строки"]:
    print(f"     {'   ' * (r['уровень'] - 1)}{r['компонент']}: {r['кол_на_1']:g} {r['ед_изм']} на 1, "
          f"{r['кол_на_N']:g} на 10{'  (лист)' if r['лист'] else ''}")
rows = {r["путь"]: r for r in tree["строки"]}
ok("Кирпичей через башни на 1 набор: 2 × 20 = 40",
   rows["ТЕСТ Набор › ТЕСТ Башня › ТЕСТ Кирпич"]["кол_на_1"] == 40)
ok("ABS в кирпичах: 40 × 23 / 10 = 92 г",
   abs(rows["ТЕСТ Набор › ТЕСТ Башня › ТЕСТ Кирпич › ТЕСТ ABS"]["кол_на_1"] - 92) < 1e-6)
ok("ABS в корпусах: 2 × 15 = 30 г",
   rows["ТЕСТ Набор › ТЕСТ Корпус › ТЕСТ ABS"]["кол_на_1"] == 30)
ok("На 10 наборов кирпичей 400",
   rows["ТЕСТ Набор › ТЕСТ Башня › ТЕСТ Кирпич"]["кол_на_N"] == 400)
ok("Уровни: Башня 1, Кирпич 2, ABS 3", [r["уровень"] for r in tree["строки"]][:3] == [1, 2, 3])
ok("Башня — не лист, ABS — лист",
   not rows["ТЕСТ Набор › ТЕСТ Башня"]["лист"] and rows["ТЕСТ Набор › ТЕСТ Корпус › ТЕСТ ABS"]["лист"])
expect("FIND_BOM для несуществующего изделия", lc.find_bom(db, 999999), False)
expect("FIND_BOM с количеством 0", lc.find_bom(db, SET, 0), False)

print("\n=== 3. CALC_BOM (сводные нормы) на 10 наборов ===")
res = lc.calc_bom(db, SET, 10)
for r in res["строки"]:
    print(f"     {r['компонент']}: {r['кол_на_N']:g} {r['ед_изм']}  (вхождений в дерево: {r['вхождений']})")
m = calc_map(res)
ok("ABS: (92 + 30) × 10 = 1220 г", m["ТЕСТ ABS"] == (1220, "TEST-г"), f"{m['ТЕСТ ABS']}")
ok("Кирпич: 400 шт", m["ТЕСТ Кирпич"] == (400, "TEST-шт"))
ok("Промежуточная Башня тоже в списке: 20 шт", m.get("ТЕСТ Башня") == (20, "TEST-шт"))
ok("Всего 4 компонента", len(m) == 4)

print("\n=== 4. Отбор по классу ===")
only_mat = calc_map(lc.calc_bom(db, SET, 10, класс_id=c_mat))
ok("«Материалы» → только ABS", list(only_mat) == ["ТЕСТ ABS"], f"{only_mat}")
only_parts = calc_map(lc.calc_bom(db, SET, 1, класс_id=c_parts))
ok("«Детали» → Кирпич и Корпус", set(only_parts) == {"ТЕСТ Кирпич", "ТЕСТ Корпус"}, f"{only_parts}")
ok("Корень «ТЕСТ Л5 корень» → все 4 (подклассы учитываются)",
   len(calc_map(lc.calc_bom(db, SET, 1, класс_id=root))) == 4)
expect("Несуществующий класс", lc.calc_bom(db, SET, 1, класс_id=999999), False)

print("\n=== 5. Одинаковые компоненты из разных веток складываются ===")
expect("Набор ← Кирпич × 10 шт напрямую", lc.add_bom_item(db, SET, BRICK, 10, ед_изм_id=pcs), True)
m2 = calc_map(lc.calc_bom(db, SET, 1))
ok("Кирпич: 40 + 10 = 50", m2["ТЕСТ Кирпич"][0] == 50, f"{m2['ТЕСТ Кирпич']}")
ok("ABS: 50 × 2.3 + 30 = 145 г", abs(m2["ТЕСТ ABS"][0] - 145) < 1e-6, f"{m2['ТЕСТ ABS']}")

print("\n=== 6. Если договорённость «одна ЕИ на компонент» нарушена ===")
expect("Башня ← ABS 1 кг (другая ЕИ)", lc.add_bom_item(db, TOWER, ABS, 1, ед_изм_id=kg), True)
res3 = lc.calc_bom(db, SET, 1)
abs_rows = [r for r in res3["строки"] if r["компонент"] == "ТЕСТ ABS"]
ok("ABS выведен двумя строками (г и кг отдельно, не складываются)", len(abs_rows) == 2,
   f"{[(r['кол_на_1'], r['ед_изм']) for r in abs_rows]}")
ok("Есть предупреждение", any("разных ЕИ" in w for w in res3["предупреждения"]), f"{res3['предупреждения']}")

cleanup()
print(f"\n=== Итог: {passed} проверок прошло, {failed} не прошло. Тестовые данные удалены. ===")
