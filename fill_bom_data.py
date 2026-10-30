# fill_bom_data.py
"""
Задание 5. Заполнение базы демонстрационными данными материальных спецификаций (BOM)
БЕЗ очистки существующих данных.

Запуск (из папки LEGO, при запущенном PostgreSQL):
    python fill_bom_data.py           — добавить данные, если спецификаций ещё нет
    python fill_bom_data.py --force   — добавить недостающие данные, даже если спецификации уже есть
"""
import sys

import main
from bom_service import load_bom_test_data
from models import Base, BOMItem, Classificator, Product, SpecChange

main.engine.echo = False


def run():
    Base.metadata.create_all(bind=main.engine)
    main.install_bom_schema()
    with main.SessionLocal() as db:
        if db.query(Classificator).count() == 0:
            print("База пуста — загружаю полный набор тестовых данных (задания 1–5)...")
            main.classifier.load_test_data(db)
        elif db.query(Product).filter(Product.артикул == "SET-42110-LITE").first() and "--force" not in sys.argv:
            print("Спецификации уже заполнены. Для дозаполнения запустите с ключом --force,")
            print("для полной перезагрузки нажмите «Тестовые данные» в интерфейсе администратора.")
            return
        else:
            print("Добавляю данные спецификаций в существующую базу...")
            load_bom_test_data(db, main.classifier)
        print(f"Готово: изделий {db.query(Product).count()}, "
              f"позиций спецификаций {db.query(BOMItem).count()}, "
              f"модификаций {db.query(Product).filter(Product.базовое_изделие_id.isnot(None)).count()}, "
              f"записей в журнале изменений {db.query(SpecChange).count()}.")


if __name__ == "__main__":
    run()
