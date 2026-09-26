"""
Проверка шага 2 работы 5: строки спецификации, проверка циклов, журнал изменений.

Запуск (из папки проекта, с активированным venv, база в Docker должна работать):
    python checks/lab5_step2_check.py

Скрипт создаёт ВРЕМЕННЫЙ класс «ТЕСТ Л5» и тестовые изделия с артикулами TEST-L5-*,
выполняет проверки и в конце всё это удаляет. Твои данные он не трогает.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import config
from models import Base, Classificator, Product, BOMItem, SpecChange
from lego_classifier import LegoClassifier

DB_URL = os.getenv("LAB5_DB_URL", config.DATABASE_URL)
engine = create_engine(DB_URL)
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()
lc = LegoClassifier(engine)

TEST_CLASS = "ТЕСТ Л5 (временный)"
passed = failed = 0


def check(title, result, expect_success):
    """Сравнить результат метода с ожидаемым (успех или отказ)"""
    global passed, failed
    ok = result.get("success") == expect_success
    passed += ok
    failed += (not ok)
    mark = "✅" if ok else "❌"
    expect = "успех" if expect_success else "отказ"
    print(f"{mark} {title}\n     ожидали: {expect}; ответ: {result.get('message')}")


def cleanup():
    """Удалить всё тестовое (в правильном порядке, чтобы не мешали внешние ключи)"""
    test_ids = [p.id for p in db.query(Product).filter(Product.артикул.like("TEST-L5-%")).all()]
    if test_ids:
        db.query(SpecChange).filter(SpecChange.изделие_id.in_(test_ids)).delete(synchronize_session=False)
        db.query(BOMItem).filter(BOMItem.изделие_id.in_(test_ids)).delete(synchronize_session=False)
        db.query(BOMItem).filter(BOMItem.компонент_id.in_(test_ids)).delete(synchronize_session=False)
        db.query(Product).filter(Product.id.in_(test_ids)).update({"базовое_изделие_id": None}, synchronize_session=False)
        db.query(Product).filter(Product.id.in_(test_ids)).delete(synchronize_session=False)
    db.query(Classificator).filter(Classificator.название == TEST_CLASS).delete(synchronize_session=False)
    db.commit()


def new_product(name, sku, cls_id, base_id=None):
    p = Product(класс_id=cls_id, наименование=name, артикул=sku, базовое_изделие_id=base_id)
    db.add(p)
    db.commit()
    return p.id


def show_spec(pid, title):
    print(f"\n   Состав «{title}»:")
    rows = lc.get_spec(db, pid)
    if not rows:
        print("     (пусто)")
    for r in rows:
        base = "база" if r["флаг_базы"] else "только это изделие"
        print(f"     {r['номер']}. {r['компонент']} × {r['расход']:g} на {r['для_количества']:g}  [{base}]  (строка id {r['id']})")


cleanup()  # на случай, если прошлый запуск оборвался
print("=== Подготовка: временный класс и изделия ===")
cls = Classificator(название=TEST_CLASS, тип_элемента="терминальный")
db.add(cls)
db.commit()
A = new_product("ТЕСТ Набор", "TEST-L5-A", cls.id)
B = new_product("ТЕСТ Узел", "TEST-L5-B", cls.id)
C = new_product("ТЕСТ Деталь", "TEST-L5-C", cls.id)
M = new_product("ТЕСТ Набор — модификация", "TEST-L5-M", cls.id, base_id=A)
print(f"Набор A={A}, Узел B={B}, Деталь C={C}, Модификация M={M} (база — A)\n")

print("=== 1. Нормальное добавление ===")
r = lc.add_bom_item(db, A, B, 2)
check("Набор ← Узел × 2", r, True)
item_AB = r.get("item_id")
check("Узел ← Деталь × 20", lc.add_bom_item(db, B, C, 20), True)
check("Набор ← Деталь × 5 (только для набора, флаг базы 0)", lc.add_bom_item(db, A, C, 5, флаг_базы=False), True)
show_spec(A, "ТЕСТ Набор")
show_spec(B, "ТЕСТ Узел")

print("\n=== 2. Защиты ===")
check("Повтор: Набор ← Узел ещё раз", lc.add_bom_item(db, A, B, 1), False)
check("Сам в себя: Набор ← Набор", lc.add_bom_item(db, A, A, 1), False)
check("Цикл: Деталь ← Набор (деталь уже внутри набора через узел)", lc.add_bom_item(db, C, A, 1), False)
check("Цикл через модификацию: Набор ← его модификация", lc.add_bom_item(db, A, M, 1), False)
check("Отрицательный расход", lc.add_bom_item(db, C, B, -1), False)
check("«Для количества» = 0", lc.add_bom_item(db, M, B, 1, для_количества=0), False)
check("Расход 0 у обычного изделия", lc.add_bom_item(db, B, A, 0), False)
check("Несуществующий компонент", lc.add_bom_item(db, A, 999999, 1), False)

print("\n=== 3. Модификация может исключить компонент базы (расход 0) ===")
check("Модификация ← Узел × 0", lc.add_bom_item(db, M, B, 0), True)

print("\n=== 4. Изменение и удаление ===")
check("Изменить Набор ← Узел: 2 → 3", lc.update_bom_item(db, item_AB, расход=3), True)
check("Изменить без изменений", lc.update_bom_item(db, item_AB, расход=3), True)
check("Изменить расход на отрицательный", lc.update_bom_item(db, item_AB, расход=-5), False)
item_BC = lc.get_spec(db, B)[0]["id"]
check("Удалить строку Узел ← Деталь", lc.delete_bom_item(db, item_BC), True)
check("Удалить несуществующую строку", lc.delete_bom_item(db, 999999), False)
show_spec(A, "ТЕСТ Набор")
show_spec(B, "ТЕСТ Узел")

print("\n=== 5. Журнал изменений ===")
for pid, name in [(A, "ТЕСТ Набор"), (B, "ТЕСТ Узел"), (M, "Модификация")]:
    print(f"   {name}:")
    for ch in db.query(SpecChange).filter(SpecChange.изделие_id == pid).order_by(SpecChange.id).all():
        line = f"     [{ch.действие}] {ch.описание}"
        if ch.было:
            line += f" | было: {ch.было}"
        if ch.стало:
            line += f" | стало: {ch.стало}"
        print(line)

cleanup()
print(f"\n=== Итог: {passed} проверок прошло, {failed} не прошло. Тестовые данные удалены. ===")
