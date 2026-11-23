
"""
Полное восстановление демонстрационной базы LEGO.
ВНИМАНИЕ: удаляет ВСЕ существующие записи!

Запуск:
    python reload_demo_data.py --confirm-reset-all-data
"""
import argparse

from main import SessionLocal, classifier, install_bom_schema
from main import install_routing_schema, install_config_schema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-reset-all-data",
        action="store_true",
        help="Подтверждение полного удаления всех данных"
    )
    args = parser.parse_args()

    if not args.confirm_reset_all_data:
        parser.error(
            "Операция удаляет все данные. "
            "Добавьте --confirm-reset-all-data"
        )

    print("Установка схем и функций...")
    install_bom_schema()
    install_routing_schema()
    install_config_schema()

    with SessionLocal() as db:
        print("Очистка и загрузка демонстрационной базы ПР1–ПР7...")
        result = classifier.load_test_data(db)
        print(result)

    print("Готово. Проверьте /cfg/functions, /cfg/templates, /cfg/orders")


if __name__ == "__main__":
    main()
