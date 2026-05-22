# init_db.py
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from models import (
    Base, Classificator, Theme, AgeCategory, PartType, Set, Part, Minifigure, 
    SetPart, SetMinifigure, Enumeration, EnumValue,
    Parameter, ParameterClass, Product, ParameterValue
)
from lego_classifier import LegoClassifier

engine = create_engine(config.DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def clear_database(db):
    """Очистка всех таблиц"""
    print("Очистка базы данных...")
    db.execute(text("TRUNCATE TABLE фигурки_в_наборе CASCADE"))
    db.execute(text("TRUNCATE TABLE состав_набора CASCADE"))
    db.execute(text("TRUNCATE TABLE мини_фигурка CASCADE"))
    db.execute(text("TRUNCATE TABLE деталь CASCADE"))
    db.execute(text("TRUNCATE TABLE набор CASCADE"))
    db.execute(text("TRUNCATE TABLE тип_детали CASCADE"))
    db.execute(text("TRUNCATE TABLE возрастная_категория CASCADE"))
    db.execute(text("TRUNCATE TABLE тематика CASCADE"))
    db.execute(text("TRUNCATE TABLE классификатор CASCADE"))
    db.commit()
    print("База данных очищена")


def load_test_data(db):
    """Загрузка тестовых данных"""
    print("Начинаем загрузку тестовых данных...")
    
    # =====================================================
    # 1. ЗАПОЛНЕНИЕ СПРАВОЧНИКОВ
    # =====================================================
    print("  Заполняем справочники...")
    
    # 1.1 Тематика наборов
    themes_data = [
        ("City", "Городская тематика"),
        ("Star Wars", "Звёздные войны"),
        ("Technic", "Техник"),
        ("Botanical collection", "Ботаническая коллекция"),
        ("Harry Potter", "Гарри Поттер"),
        ("Marvel", "Марвел"),
        ("Creator", "Творец")
    ]
    
    for name, desc in themes_data:
        node = Classificator(название=name, тип_элемента="тематика", родительский_id=None, порядок_сортировки=0)
        db.add(node)
        db.flush()
        db.add(Theme(id_классификатора=node.id, описание=desc))
    
    # 1.2 Возрастные категории
    age_data = [
        ("2-4 лет", 2, 4),
        ("4-6 лет", 4, 6),
        ("6-13 лет", 6, 13),
        ("14-18 лет", 14, 18),
        ("18+ лет", 18, 99)
    ]
    
    for name, min_age, max_age in age_data:
        node = Classificator(название=name, тип_элемента="возрастная_категория", родительский_id=None, порядок_сортировки=0)
        db.add(node)
        db.flush()
        db.add(AgeCategory(id_классификатора=node.id, минимальный_возраст=min_age, максимальный_возраст=max_age))
    
    db.commit()
    print("  Справочники заполнены")
    
    # =====================================================
    # 2. ПОСТРОЕНИЕ КЛАССИФИКАТОРА
    # =====================================================
    print("  Строим классификатор...")
    
    # Корневой элемент
    root = Classificator(название="Изделия бренда LEGO", тип_элемента="промежуточный", родительский_id=None, порядок_сортировки=1)
    db.add(root)
    db.flush()
    root_id = root.id
    
    # Основные категории
    sets_cat = Classificator(название="Наборы", тип_элемента="промежуточный", родительский_id=root_id, порядок_сортировки=1)
    db.add(sets_cat)
    db.flush()
    sets_id = sets_cat.id
    
    parts_cat = Classificator(название="Детали", тип_элемента="промежуточный", родительский_id=root_id, порядок_сортировки=2)
    db.add(parts_cat)
    db.flush()
    parts_id = parts_cat.id
    
    minifigs_cat = Classificator(название="Мини-фигурки", тип_элемента="промежуточный", родительский_id=root_id, порядок_сортировки=3)
    db.add(minifigs_cat)
    db.flush()
    minifigs_id = minifigs_cat.id
    
    # Подкатегории Наборов
    for name, order in [("Тематика City", 1), ("Тематика Star Wars", 2), ("Тематика Technic", 3)]:
        db.add(Classificator(название=name, тип_элемента="промежуточный", родительский_id=sets_id, порядок_сортировки=order))
    
    # Подкатегории Деталей
    bricks_node = Classificator(название="Кирпичи", тип_элемента="промежуточный", родительский_id=parts_id, порядок_сортировки=1)
    db.add(bricks_node)
    db.flush()
    bricks_id = bricks_node.id
    
    plates_node = Classificator(название="Плиты", тип_элемента="промежуточный", родительский_id=parts_id, порядок_сортировки=2)
    db.add(plates_node)
    db.flush()
    plates_id = plates_node.id
    
    tech_node = Classificator(название="Технические детали", тип_элемента="промежуточный", родительский_id=parts_id, порядок_сортировки=3)
    db.add(tech_node)
    
    special_node = Classificator(название="Специальные детали", тип_элемента="промежуточный", родительский_id=parts_id, порядок_сортировки=4)
    db.add(special_node)
    db.flush()
    special_id = special_node.id
    
    # Терминальные узлы (ОБЩИЕ типы деталей - без цвета)
    brick_2x4_type = Classificator(название="Кирпич 2x4", тип_элемента="терминальный", родительский_id=bricks_id, порядок_сортировки=1)
    db.add(brick_2x4_type)
    
    brick_2x2_type = Classificator(название="Кирпич 2x2", тип_элемента="терминальный", родительский_id=bricks_id, порядок_сортировки=2)
    db.add(brick_2x2_type)
    
    plate_1x2_type = Classificator(название="Плита 1x2", тип_элемента="терминальный", родительский_id=plates_id, порядок_сортировки=1)
    db.add(plate_1x2_type)
    
    plate_2x4_type = Classificator(название="Плита 2x4", тип_элемента="терминальный", родительский_id=plates_id, порядок_сортировки=2)
    db.add(plate_2x4_type)
    
    wheel_type = Classificator(название="Колесо", тип_элемента="терминальный", родительский_id=special_id, порядок_сортировки=1)
    db.add(wheel_type)
    
    db.commit()
    
    # Получаем ID созданных узлов
    brick_2x4_id = brick_2x4_type.id
    brick_2x2_id = brick_2x2_type.id
    plate_1x2_id = plate_1x2_type.id
    wheel_id = wheel_type.id
    
    print("  Классификатор построен")
    
    # =====================================================
    # 3. ТИПЫ ДЕТАЛЕЙ
    # =====================================================
    print("  Добавляем типы деталей...")
    
    part_type_ids = {}
    for pt_name in ["Кирпич", "Плита", "Техническая", "Специальная"]:
        node = Classificator(название=pt_name, тип_элемента="тип_детали", родительский_id=None, порядок_сортировки=0)
        db.add(node)
        db.flush()
        part_type = PartType(id_классификатора=node.id, уровень_иерархии=1)
        db.add(part_type)
        db.flush()
        part_type_ids[pt_name] = part_type.id
    
    db.commit()
    
    # =====================================================
    # 4. НАБОРЫ
    # =====================================================
    print("  Добавляем наборы...")
    
    star_wars_theme = db.query(Theme).join(Classificator).filter(Classificator.название == "Star Wars").first()
    city_theme = db.query(Theme).join(Classificator).filter(Classificator.название == "City").first()
    technic_theme = db.query(Theme).join(Classificator).filter(Classificator.название == "Technic").first()
    age_14 = db.query(AgeCategory).filter(AgeCategory.минимальный_возраст == 14).first()
    age_6 = db.query(AgeCategory).filter(AgeCategory.минимальный_возраст == 6).first()
    
    sets_data = [
        ("Звезда Смерти", "75159", 2020, 499.99, 4016, age_14.id, star_wars_theme.id, 1),
        ("Космический корабль", "75257", 2019, 159.99, 1351, age_6.id, star_wars_theme.id, 2),
        ("Полицейский участок", "60266", 2020, 129.99, 745, age_6.id, city_theme.id, 3),
        ("Внедорожник", "42110", 2019, 199.99, 2573, age_14.id, technic_theme.id, 4)
    ]
    
    set_objects = []
    for name, catalog, year, price, parts, age_id, theme_id, order in sets_data:
        node = Classificator(название=name, тип_элемента="набор", родительский_id=sets_id, порядок_сортировки=order)
        db.add(node)
        db.flush()
        new_set = Set(
            id_классификатора=node.id, номер_по_каталогу=catalog, год_выпуска=year, цена=price,
            количество_деталей=parts, id_возрастной_категории=age_id, id_тематики=theme_id
        )
        db.add(new_set)
        db.flush()
        set_objects.append(new_set)
    
    db.commit()
    print("  Наборы добавлены")
    
    # =====================================================
    # 5. ДЕТАЛИ (КАЖДАЯ СВЯЗАНА С ОТДЕЛЬНЫМ УЗЛОМ)
    # =====================================================
    print("  Добавляем детали...")
    
    brick_type_id = part_type_ids["Кирпич"]
    plate_type_id = part_type_ids["Плита"]
    special_type_id = part_type_ids["Специальная"]
    
    # Для КАЖДОЙ детали создаём свой узел в классификаторе
    parts_data = [
        # name, color, size, weight, part_type_id, parent_id (тип детали в классификаторе)
        ("Кирпич 2x4 красный", "Красный", "2x4", 2.5, brick_type_id, brick_2x4_id),
        ("Кирпич 2x4 синий", "Синий", "2x4", 2.5, brick_type_id, brick_2x4_id),
        ("Кирпич 2x2 зелёный", "Зелёный", "2x2", 1.2, brick_type_id, brick_2x2_id),
        ("Плита 1x2 белая", "Белый", "1x2", 0.8, plate_type_id, plate_1x2_id),
        ("Колесо чёрное", "Чёрный", "30x14", 5.0, special_type_id, wheel_id)
    ]
    
    part_objects = []
    for name, color, size, weight, ptype_id, parent_node_id in parts_data:
        # Создаём уникальный узел для каждой детали
        node = Classificator(название=name, тип_элемента="терминальный", родительский_id=parent_node_id, порядок_сортировки=0)
        db.add(node)
        db.flush()
        part = Part(
            id_классификатора=node.id, цвет=color, размер=size, вес=weight, id_типа=ptype_id
        )
        db.add(part)
        db.flush()
        part_objects.append(part)
    
    db.commit()
    print("  Детали добавлены")
    
    # =====================================================
    # 6. МИНИ-ФИГУРКИ
    # =====================================================
    print("  Добавляем мини-фигурки...")
    
    minifigs_data = [
        ("Люк Скайуокер", "Люк", "Star Wars", "SW001"),
        ("Дарт Вейдер", "Дарт Вейдер", "Star Wars", "SW002"),
        ("Полицейский", "Полицейский", "City", "CT001")
    ]
    
    minifig_objects = []
    for name, character, series, code in minifigs_data:
        node = Classificator(название=name, тип_элемента="терминальный", родительский_id=minifigs_id, порядок_сортировки=0)
        db.add(node)
        db.flush()
        mf = Minifigure(id_классификатора=node.id, персонаж=character, серия=series, уникальный_код=code)
        db.add(mf)
        db.flush()
        minifig_objects.append(mf)
    
    db.commit()
    print("  Мини-фигурки добавлены")
    
    # =====================================================
    # 7. СОСТАВ НАБОРОВ
    # =====================================================
    print("  Добавляем состав наборов...")
    
    # Получаем объекты по уникальным названиям
    red_brick = db.query(Part).join(Classificator).filter(Classificator.название == "Кирпич 2x4 красный").first()
    blue_brick = db.query(Part).join(Classificator).filter(Classificator.название == "Кирпич 2x4 синий").first()
    green_brick = db.query(Part).join(Classificator).filter(Classificator.название == "Кирпич 2x2 зелёный").first()
    white_plate = db.query(Part).join(Classificator).filter(Classificator.название == "Плита 1x2 белая").first()
    wheel = db.query(Part).join(Classificator).filter(Classificator.название == "Колесо чёрное").first()
    
    luke = db.query(Minifigure).filter(Minifigure.уникальный_код == "SW001").first()
    vader = db.query(Minifigure).filter(Minifigure.уникальный_код == "SW002").first()
    
    death_star = db.query(Set).join(Classificator).filter(Classificator.название == "Звезда Смерти").first()
    spaceship = db.query(Set).join(Classificator).filter(Classificator.название == "Космический корабль").first()
    
    # Звезда Смерти
    db.add(SetPart(id_набора=death_star.id, id_детали=red_brick.id, количество_штук=50))
    db.add(SetPart(id_набора=death_star.id, id_детали=blue_brick.id, количество_штук=30))
    db.add(SetPart(id_набора=death_star.id, id_детали=green_brick.id, количество_штук=40))
    db.add(SetPart(id_набора=death_star.id, id_детали=white_plate.id, количество_штук=100))
    db.add(SetMinifigure(id_набора=death_star.id, id_фигурки=luke.id, количество_штук=2))
    db.add(SetMinifigure(id_набора=death_star.id, id_фигурки=vader.id, количество_штук=1))
    
    # Космический корабль
    db.add(SetPart(id_набора=spaceship.id, id_детали=red_brick.id, количество_штук=20))
    db.add(SetPart(id_набора=spaceship.id, id_детали=green_brick.id, количество_штук=15))
    db.add(SetPart(id_набора=spaceship.id, id_детали=wheel.id, количество_штук=4))
    db.add(SetMinifigure(id_набора=spaceship.id, id_фигурки=luke.id, количество_штук=1))
    
    db.commit()

    print("  Состав наборов добавлен")

    # ========== ПАРАМЕТРЫ ДЛЯ СПРАВОЧНИКА (ЗАДАНИЕ 1.3) ==========
    print("  Добавляем параметры для справочника...")
    
    # Создаём экземпляр классификатора
    classifier = LegoClassifier(engine)
    
    # Получаем перечисление "Цвет детали" (создано ранее)
    enum_color = db.query(Enumeration).filter(Enumeration.name == "Цвет детали").first()
    
    # Создаём параметры
    вес_param = classifier.add_parameter(db, "вес", "Вес изделия", "REAL", "кг")
    длина_param = classifier.add_parameter(db, "длина", "Длина изделия", "REAL", "мм")
    цвет_param = classifier.add_parameter(db, "цвет", "Цвет изделия", "ENUM", перечисление_id=enum_color.id if enum_color else None)
    материал_param = classifier.add_parameter(db, "материал", "Материал изделия", "STRING")
    
    # Привязываем параметры к классу "Кирпич 2x4"
    brick_2x4 = db.query(Classificator).filter(Classificator.название == "Кирпич 2x4").first()
    if brick_2x4:
        if вес_param["success"]:
            classifier.add_param_to_class(db, brick_2x4.id, вес_param["param_id"], мин_значение=0, макс_значение=10)
        if длина_param["success"]:
            classifier.add_param_to_class(db, brick_2x4.id, длина_param["param_id"], мин_значение=0, макс_значение=100)
        if цвет_param["success"]:
            classifier.add_param_to_class(db, brick_2x4.id, цвет_param["param_id"])
        if материал_param["success"]:
            classifier.add_param_to_class(db, brick_2x4.id, материал_param["param_id"])
    
    # Создаём тестовые изделия
    classifier.add_product(db, brick_2x4.id, "Кирпич красный", "BR001")
    classifier.add_product(db, brick_2x4.id, "Кирпич синий", "BR002")
    
    # Устанавливаем значения параметров для изделий
    brick_red = db.query(Product).filter(Product.артикул == "BR001").first()
    brick_blue = db.query(Product).filter(Product.артикул == "BR002").first()
    
    # Получаем ParameterClass ID для каждого параметра
    if brick_2x4:
        вес_pc = db.query(ParameterClass).join(Parameter).filter(
            ParameterClass.класс_id == brick_2x4.id,
            Parameter.обозначение == "вес"
        ).first()
        длина_pc = db.query(ParameterClass).join(Parameter).filter(
            ParameterClass.класс_id == brick_2x4.id,
            Parameter.обозначение == "длина"
        ).first()
        цвет_pc = db.query(ParameterClass).join(Parameter).filter(
            ParameterClass.класс_id == brick_2x4.id,
            Parameter.обозначение == "цвет"
        ).first()
        
        if brick_red and вес_pc:
            classifier.set_product_param_value(db, brick_red.id, вес_pc.id, 2.5)
        if brick_red and длина_pc:
            classifier.set_product_param_value(db, brick_red.id, длина_pc.id, 50.0)
        if brick_red and цвет_pc and enum_color:
            # Находим ID значения "Красный" в перечислении
            red_val = db.query(EnumValue).filter(
                EnumValue.enumeration_id == enum_color.id,
                EnumValue.value == "Красный"
            ).first()
            if red_val:
                classifier.set_product_param_value(db, brick_red.id, цвет_pc.id, red_val.id)
        
        if brick_blue and вес_pc:
            classifier.set_product_param_value(db, brick_blue.id, вес_pc.id, 2.5)
        if brick_blue and длина_pc:
            classifier.set_product_param_value(db, brick_blue.id, длина_pc.id, 50.0)
        if brick_blue and цвет_pc and enum_color:
            blue_val = db.query(EnumValue).filter(
                EnumValue.enumeration_id == enum_color.id,
                EnumValue.value == "Синий"
            ).first()
            if blue_val:
                classifier.set_product_param_value(db, brick_blue.id, цвет_pc.id, blue_val.id)
    
    db.commit()
    print("  Параметры и изделия добавлены")
    
    print("\n" + "="*50)
    print("ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО ЗАГРУЖЕНЫ!")
    print("="*50)
    
    print(f"\nСтатистика:")
    print(f"  - Категорий: {db.query(Classificator).count()}")
    print(f"  - Наборов: {db.query(Set).count()}")
    print(f"  - Деталей: {db.query(Part).count()}")
    print(f"  - Мини-фигурок: {db.query(Minifigure).count()}")
    
    print("  Тестовые перечисления добавлены")


def main():
    db = SessionLocal()
    try:
        clear_database(db)
        load_test_data(db)
    except Exception as e:
        print(f"Ошибка: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()