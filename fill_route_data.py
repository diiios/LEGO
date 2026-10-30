# fill_route_data.py
"""
Задание 6. Заполнение базы демонстрационными данными маршрутной технологии
БЕЗ очистки существующих данных (поверх данных заданий 1–5).

Запуск (из папки LEGO, при запущенном PostgreSQL):
    python fill_route_data.py
"""
import main
from models import Base, BOMItem, Classificator, Product
from routing_models import InputResource, ProductOperation, TypicalProcess, WorkCenter
from routing_seed import load_routing_test_data
from routing_service import routing_service

main.engine.echo = False


def run():
    Base.metadata.create_all(bind=main.engine)
    main.install_bom_schema()
    main.install_routing_schema()
    with main.SessionLocal() as db:
        if db.query(Classificator).count() == 0:
            print("База пуста — загружаю полный набор тестовых данных (задания 1–6)...")
            main.classifier.load_test_data(db)
        elif db.query(TypicalProcess).count():
            print("Данные маршрутной технологии уже есть. Для полной перезагрузки нажмите")
            print("«Тестовые данные» в интерфейсе администратора.")
            return
        else:
            if not db.query(BOMItem).count():
                print("Сначала нужны спецификации задания 5: запустите python fill_bom_data.py")
                return
            print("Добавляю маршрутную технологию в существующую базу...")
            routing_service.flyweights.invalidate()
            load_routing_test_data(db, main.classifier)
        print(f"Готово: ГРЦ {db.query(WorkCenter).count()}, типовых ТП {db.query(TypicalProcess).count()}, "
              f"изделий-операций {db.query(ProductOperation).count()}, "
              f"входных ресурсов {db.query(InputResource).count()}, "
              f"изделий с маршрутом {db.query(ProductOperation.изделие_id).distinct().count()} из {db.query(Product).count()}.")


if __name__ == "__main__":
    run()
