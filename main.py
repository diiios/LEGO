# main.py
from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional, Dict, Any

from config import config
from models import Base, Classificator, Theme, AgeCategory, PartType, Set, Part, Minifigure, Product, ParameterClass, Parameter, HOOperation
from schemas import *
from lego_classifier import LegoClassifier

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates



# Create engine
engine = create_engine(config.DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI app
app = FastAPI(
    title="Lego Classifier API",
    description="API для управления классификатором Lego на PostgreSQL",
    version="2.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def landing(request: Request):
    """Стартовая страница — выбор роли"""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/user")
def user_ui(request: Request):
    """Интерфейс пользователя (просмотр и фильтрация)"""
    return templates.TemplateResponse("user.html", {"request": request})


@app.get("/admin")
def admin_ui(request: Request):
    """Интерфейс администратора (CRUD)"""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/app")
def get_ui(request: Request):
    """Обратная совместимость — перенаправление в админку"""
    return templates.TemplateResponse("admin.html", {"request": request})

# Initialize classifier
classifier = LegoClassifier(engine)

@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("""
            DO $$
            DECLARE r record;
            BEGIN
                FOR r IN
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid = 'состав_набора'::regclass
                      AND contype = 'f'
                      AND pg_get_constraintdef(oid) LIKE '%REFERENCES "%деталь"%'
                LOOP
                    EXECUTE format('ALTER TABLE "состав_набора" DROP CONSTRAINT %I', r.conname);
                END LOOP;
                DELETE FROM "состав_набора" сн
                WHERE NOT EXISTS (
                    SELECT 1 FROM "изделие" и WHERE и.id = сн."id_детали"
                );
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'состав_набора'::regclass
                      AND contype = 'f'
                      AND pg_get_constraintdef(oid) LIKE '%REFERENCES "%изделие"%'
                ) THEN
                    ALTER TABLE "состав_набора"
                    ADD CONSTRAINT "состав_набора_id_детали_fkey"
                    FOREIGN KEY ("id_детали") REFERENCES "изделие"(id) ON DELETE CASCADE;
                END IF;
            END $$;
        """))
    """Инициализация при запуске"""
    print("Запуск Lego Classifier API на PostgreSQL...")
    # Загружаем тестовые данные если база пуста
    with SessionLocal() as db:
        count = db.query(Classificator).count()
        if count == 0:
            print("База данных пуста, загружаем тестовые данные...")
            classifier.load_test_data(db)

@app.get("/api", tags=["🏠 Главная"])
def root():
    return {
        "message": "Lego Classifier API",
        "version": "2.0.0",
        "database": "PostgreSQL",
        "docs": "/docs",
        "user_ui": "/user",
        "admin_ui": "/admin",
    }

# ==================== CATEGORIES ====================

@app.get("/categories", tags=["📂 Классификатор"], response_model=List[Dict[str, Any]])
def get_categories(db: Session = Depends(get_db)):
    """Получить все категории"""
    return classifier.get_all_categories(db)

@app.post("/categories", tags=["📂 Классификатор"], response_model=OperationResult)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    """Создать новую категорию"""
    result = classifier.add_node(db, data.name, "промежуточный", data.parent_id, sort_order=data.sort_order)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/categories/subcategory", tags=["📂 Классификатор"], response_model=OperationResult)
def create_subcategory(data: SubcategoryCreate, db: Session = Depends(get_db)):
    """Создать подкатегорию"""
    parent_id = None
    if data.parent_name:
        parent = db.query(Classificator).filter(Classificator.название == data.parent_name).first()
        if not parent:
            raise HTTPException(status_code=404, detail=f"Родительская категория '{data.parent_name}' не найдена")
        parent_id = parent.id
    
    result = classifier.add_node(db, data.child_name, "промежуточный", parent_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.put("/categories/{node_id}/move", tags=["📂 Классификатор"], response_model=OperationResult)
def move_category(node_id: int, data: MoveNode, db: Session = Depends(get_db)):
    """Переместить категорию"""
    result = classifier.move_node(db, node_id, data.new_parent_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/categories/{node_id}", tags=["📂 Классификатор"], response_model=OperationResult)
def delete_category(node_id: int, db: Session = Depends(get_db)):
    """Удалить категорию"""
    result = classifier.delete_node(db, node_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.put("/categories/{parent_id}/reorder", tags=["📂 Классификатор"], response_model=OperationResult)
def reorder_children(parent_id: int, data: ReorderChildren, db: Session = Depends(get_db)):
    """Изменить порядок потомков"""
    result = classifier.reorder_children(db, parent_id, data.ordered_child_ids)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.put("/categories/{node_id}/base-unit", tags=["📂 Классификатор"], response_model=OperationResult)
def set_base_unit(node_id: int, data: SetBaseUnit, db: Session = Depends(get_db)):
    """Установить единицу измерения"""
    result = classifier.set_base_unit(db, node_id, data.base_ei_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/categories/{node_id}/descendants", tags=["📂 Классификатор"])
def get_descendants(node_id: int, db: Session = Depends(get_db)):
    """Получить всех потомков узла"""
    return classifier.get_descendants(db, node_id)

@app.get("/categories/{node_id}/ancestors", tags=["📂 Классификатор"])
def get_ancestors(node_id: int, db: Session = Depends(get_db)):
    """Получить всех родителей узла"""
    return classifier.get_ancestors(db, node_id)

@app.get("/categories/{node_id}/terminals", tags=["📂 Классификатор"])
def get_terminal_descendants(node_id: int, db: Session = Depends(get_db)):
    """Получить терминальные классы"""
    return classifier.get_terminal_descendants(db, node_id)

@app.get("/cycles", tags=["📂 Классификатор"])
def detect_cycles(db: Session = Depends(get_db)):
    """Диагностика циклов"""
    return classifier.detect_cycles(db)

# ==================== SEARCH ====================

@app.get("/search/theme", tags=["🔍 Поиск"], response_model=List[SetSearchResult])
def search_by_theme(theme: str = Query(..., description="Название тематики"), db: Session = Depends(get_db)):
    """Поиск наборов по тематике"""
    return classifier.search_by_theme(db, theme)

@app.get("/search/age", tags=["🔍 Поиск"], response_model=List[AgeSearchResult])
def search_by_age(age: int = Query(..., description="Возраст"), db: Session = Depends(get_db)):
    """Поиск наборов по возрасту"""
    return classifier.search_by_age(db, age)

@app.get("/search/part-type", tags=["🔍 Поиск"], response_model=List[PartSearchResult])
def search_by_part_type(part_type: str = Query(..., description="Тип детали"), db: Session = Depends(get_db)):
    """Поиск деталей по типу"""
    return classifier.search_by_part_type(db, part_type)

# ==================== SETS ====================

@app.get("/sets", tags=["🧩 Наборы"], response_model=List[Dict[str, Any]])
def get_all_sets(db: Session = Depends(get_db)):
    """Получить все наборы"""
    return classifier.get_all_sets(db)

@app.post("/sets", tags=["🧩 Наборы"], response_model=OperationResult)
def create_set(data: SetCreate, db: Session = Depends(get_db)):
    """Создать набор"""
    result = classifier.add_set(
        db, data.name, data.catalog_number, data.year, data.price,
        data.parts_count, data.age_category_id, data.theme_id, data.parent_id
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/sets/{set_id}/contents", tags=["🧩 Наборы"])
def get_set_contents(set_id: int, db: Session = Depends(get_db)):
    """Получить состав набора"""
    return classifier.get_set_contents(db, set_id)

@app.post("/sets/{set_id}/contents", tags=["🧩 Наборы"], response_model=OperationResult)
def add_set_content_item(set_id: int, data: SetProductItemCreate, db: Session = Depends(get_db)):
    """Добавить или обновить изделие в составе набора"""
    result = classifier.add_set_product_item(db, set_id, data.product_id, data.quantity)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/sets/{set_id}/contents/{product_id}", tags=["🧩 Наборы"], response_model=OperationResult)
def delete_set_content_item(set_id: int, product_id: int, db: Session = Depends(get_db)):
    """Удалить изделие из состава набора"""
    result = classifier.delete_set_product_item(db, set_id, product_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result

# ==================== PARTS ====================

@app.get("/parts", tags=["🔧 Детали"], response_model=List[Dict[str, Any]])
def get_all_parts(db: Session = Depends(get_db)):
    """Получить все детали"""
    return classifier.get_all_parts(db)

@app.post("/parts/filter", tags=["🔧 Детали"], response_model=List[Dict[str, Any]])
def filter_parts(data: PartFilter, db: Session = Depends(get_db)):
    """Фильтр деталей по типу и названию"""
    return classifier.filter_parts(
        db,
        part_type_id=data.part_type_id,
        name_contains=data.name_contains,
    )

@app.post("/parts/cleanup-anomalies", tags=["🔧 Детали"], response_model=Dict[str, Any])
def cleanup_anomalous_parts(db: Session = Depends(get_db)):
    """Удалить детали с нереалистичными данными (например, вес > 500 г)"""
    return classifier.remove_anomalous_parts(db)

@app.post("/parts", tags=["🔧 Детали"], response_model=OperationResult)
def create_part(data: PartCreate, db: Session = Depends(get_db)):
    result = classifier.add_part(db, data.name, data.part_type_id, data.parent_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/parts/{part_id}", tags=["🔧 Детали"])
def get_part(part_id: int, db: Session = Depends(get_db)):
    part = classifier._parts_query(db).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Деталь не найдена")
    result = classifier._serialize_part(part)
    # Добавляем parent_id из узла классификатора
    result["parent_id"] = part.classificator.родительский_id if part.classificator else None
    return result

@app.put("/parts/{part_id}", tags=["🔧 Детали"], response_model=OperationResult)
def update_part(part_id: int, data: PartCreate, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Деталь не найдена")
    try:
        part.classificator.название = data.name
        part.id_типа = data.part_type_id
        if data.parent_id is not None:
            part.classificator.родительский_id = data.parent_id
        db.commit()
        return {"success": True, "message": "Деталь обновлена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==================== MINIFIGURES ====================

@app.get("/minifigures", tags=["🧸 Мини-фигурки"], response_model=List[Dict[str, Any]])
def get_all_minifigures(db: Session = Depends(get_db)):
    """Получить все мини-фигурки"""
    return classifier.get_all_minifigures(db)

@app.post("/minifigures", tags=["🧸 Мини-фигурки"], response_model=OperationResult)
def create_minifigure(data: MinifigureCreate, db: Session = Depends(get_db)):
    """Создать мини-фигурку"""
    result = classifier.add_minifigure(db, data.name, data.character, data.series, data.unique_code)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/minifigures/{mf_id}", tags=["🧸 Мини-фигурки"])
def get_minifigure(mf_id: int, db: Session = Depends(get_db)):
    """Получить мини-фигурку по ID"""
    mf = db.query(Minifigure).filter(Minifigure.id == mf_id).first()
    if not mf:
        raise HTTPException(status_code=404, detail="Мини-фигурка не найдена")
    return {
        "id": mf.id,
        "name": mf.classificator.название,
        "character": mf.персонаж,
        "series": mf.серия,
        "unique_code": mf.уникальный_код,
    }

@app.put("/minifigures/{mf_id}", tags=["🧸 Мини-фигурки"], response_model=OperationResult)
def update_minifigure(mf_id: int, data: MinifigureCreate, db: Session = Depends(get_db)):
    """Обновить мини-фигурку"""
    mf = db.query(Minifigure).filter(Minifigure.id == mf_id).first()
    if not mf:
        raise HTTPException(status_code=404, detail="Мини-фигурка не найдена")
    try:
        mf.classificator.название = data.name
        mf.персонаж = data.character
        mf.серия = data.series
        mf.уникальный_код = data.unique_code
        db.commit()
        return {"success": True, "message": "Мини-фигурка обновлена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==================== DIRECTORIES ====================

@app.get("/themes", tags=["📚 Справочники"], response_model=List[ThemeResponse])
def get_themes(db: Session = Depends(get_db)):
    """Получить все тематики"""
    return classifier.get_all_themes(db)

@app.post("/themes", tags=["📚 Справочники"], response_model=OperationResult)
def create_theme(data: ThemeCreate, db: Session = Depends(get_db)):
    """Создать тематику"""
    result = classifier.add_theme(db, data.name, data.description)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/age-categories", tags=["📚 Справочники"], response_model=List[AgeCategoryResponse])
def get_age_categories(db: Session = Depends(get_db)):
    """Получить все возрастные категории"""
    return classifier.get_all_age_categories(db)

@app.post("/age-categories", tags=["📚 Справочники"], response_model=OperationResult)
def create_age_category(data: AgeCategoryCreate, db: Session = Depends(get_db)):
    """Создать возрастную категорию"""
    result = classifier.add_age_category(db, data.name, data.min_age, data.max_age)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/part-types", tags=["📚 Справочники"], response_model=List[PartTypeResponse])
def get_part_types(db: Session = Depends(get_db)):
    """Получить все типы деталей"""
    return classifier.get_all_part_types(db)

@app.post("/part-types", tags=["📚 Справочники"], response_model=OperationResult)
def create_part_type(data: PartTypeCreate, db: Session = Depends(get_db)):
    """Создать тип детали"""
    result = classifier.add_part_type(db, data.name, data.hierarchy_level)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# ==================== UTILITIES ====================

@app.post("/test-data", tags=["🛠️ Сервисные"])
def load_test_data(db: Session = Depends(get_db)):
    """Загрузить тестовые данные"""
    result = classifier.load_test_data(db)
    return result

@app.delete("/clear", tags=["🛠️ Сервисные"])
def clear_database(db: Session = Depends(get_db)):
    """Очистить базу данных"""
    classifier.clear_database(db)
    return {"success": True, "message": "База данных очищена"}

@app.post("/reset-database", tags=["🛠️ Сервисные"])
def reset_database():
    """Полностью пересоздаёт базу данных (только для разработки!)"""
    import psycopg2
    from config import config
    
    try:
        # Подключаемся к базе 'postgres' (административной) без использования SQLAlchemy
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database="postgres"
        )
        conn.autocommit = True  # Обязательно для DROP DATABASE
        cursor = conn.cursor()
        
        # Закрываем все соединения с нашей БД
        cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{config.DB_NAME}'
            AND pid <> pg_backend_pid()
        """)
        
        # Удаляем и создаём базу заново
        cursor.execute(f"DROP DATABASE IF EXISTS {config.DB_NAME}")
        cursor.execute(f"CREATE DATABASE {config.DB_NAME}")
        
        cursor.close()
        conn.close()
        
        return {"success": True, "message": f"База данных {config.DB_NAME} пересоздана. Перезапустите приложение."}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ==================== ENUMERATIONS ====================

@app.post("/enumerations", tags=["🔢 Перечисления"], response_model=OperationResult)
def create_enumeration(data: EnumerationCreate, db: Session = Depends(get_db)):
    """Создать новое перечисление"""
    result = classifier.add_enumeration(db, data.name, data.description)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/enumerations", tags=["🔢 Перечисления"], response_model=List[EnumerationResponse])
def get_enumerations(db: Session = Depends(get_db)):
    """Получить все перечисления"""
    return classifier.get_all_enumerations(db)

@app.get("/enumerations/{enum_id}", tags=["🔢 Перечисления"], response_model=EnumerationResponse)
def get_enumeration(enum_id: int, db: Session = Depends(get_db)):
    """Получить перечисление по ID"""
    result = classifier.get_enumeration_by_id(db, enum_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result

@app.put("/enumerations/{enum_id}", tags=["🔢 Перечисления"], response_model=OperationResult)
def update_enumeration(enum_id: int, data: EnumerationCreate, db: Session = Depends(get_db)):
    """Обновить перечисление"""
    result = classifier.update_enumeration(db, enum_id, data.name, data.description)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/enumerations/{enum_id}", tags=["🔢 Перечисления"], response_model=OperationResult)
def delete_enumeration(enum_id: int, db: Session = Depends(get_db)):
    """Удалить перечисление"""
    result = classifier.delete_enumeration(db, enum_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# ----- Значения перечислений -----

@app.post("/enumerations/{enum_id}/values", tags=["🔢 Перечисления"], response_model=OperationResult)
def create_enum_value(enum_id: int, data: EnumValueCreate, db: Session = Depends(get_db)):
    """Добавить значение в перечисление"""
    result = classifier.add_enum_value(db, enum_id, data.value, data.sort_order, data.extra_data)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/enumerations/{enum_id}/values", tags=["🔢 Перечисления"], response_model=List[EnumValueResponse])
def get_enum_values(enum_id: int, db: Session = Depends(get_db)):
    """Получить все значения перечисления"""
    return classifier.get_enum_values(db, enum_id)

@app.put("/enum-values/{value_id}", tags=["🔢 Перечисления"], response_model=OperationResult)
def update_enum_value(value_id: int, data: EnumValueCreate, db: Session = Depends(get_db)):
    """Обновить значение перечисления"""
    result = classifier.update_enum_value(db, value_id, data.value, data.sort_order, data.extra_data)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.put("/enumerations/{enum_id}/values/reorder", tags=["🔢 Перечисления"], response_model=OperationResult)
def reorder_enum_values(enum_id: int, data: EnumValueReorder, db: Session = Depends(get_db)):
    """Изменить порядок значений перечисления"""
    result = classifier.reorder_enum_values(db, enum_id, data.ordered_ids)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/enum-values/{value_id}", tags=["🔢 Перечисления"], response_model=OperationResult)
def delete_enum_value(value_id: int, db: Session = Depends(get_db)):
    """Удалить значение перечисления"""
    result = classifier.delete_enum_value(db, value_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# ==================== PARAMETERS (ЗАДАНИЕ 1.3) ====================

@app.post("/parameters", tags=["⚙️ Параметры"], response_model=OperationResult)
def create_parameter(data: ParameterCreate, db: Session = Depends(get_db)):
    """Создать новый параметр"""
    result = classifier.add_parameter(
        db, data.обозначение, data.полное_имя,
        data.тип_параметра, data.единица_измерения, data.перечисление_id
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/parameters", tags=["⚙️ Параметры"], response_model=List[ParameterResponse])
def get_parameters(db: Session = Depends(get_db)):
    """Получить все параметры"""
    return classifier.get_all_parameters(db)

@app.delete("/parameters/{parameter_id}", tags=["⚙️ Параметры"], response_model=OperationResult)
def delete_parameter(parameter_id: int, db: Session = Depends(get_db)):
    """Удалить параметр (только если он не привязан ни к одному классу)"""
    # Проверяем, существует ли параметр
    param = db.query(Parameter).filter(Parameter.id == parameter_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Параметр не найден")
    
    # Проверяем, не привязан ли параметр к каким-либо классам
    param_class_count = db.query(ParameterClass).filter(ParameterClass.параметр_id == parameter_id).count()
    if param_class_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Невозможно удалить параметр: он привязан к {param_class_count} классам"
        )
    
    try:
        db.delete(param)
        db.commit()
        return {"success": True, "message": f"Параметр '{param.обозначение}' удалён", "param_id": parameter_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==================== CLASS PARAMETERS ====================

@app.get("/classes/{class_id}/parameters", tags=["⚙️ Параметры"], response_model=List[Dict[str, Any]])
def get_class_parameters(class_id: int, include_inherited: bool = True, db: Session = Depends(get_db)):
    """Получить параметры класса (с наследованием)"""
    return classifier.get_class_parameters(db, class_id, include_inherited)

@app.post("/classes/{class_id}/parameters", tags=["⚙️ Параметры"], response_model=OperationResult)
def add_param_to_class(class_id: int, data: ParameterClassCreate, db: Session = Depends(get_db)):
    """Привязать параметр к классу"""
    result = classifier.add_param_to_class(
        db, class_id, data.параметр_id,
        data.мин_значение, data.макс_значение,
        data.значение_по_умолчанию, data.обязательный
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/classes/parameters/{param_class_id}", tags=["⚙️ Параметры"], response_model=OperationResult)
def remove_param_from_class(param_class_id: int, db: Session = Depends(get_db)):
    """Удалить привязку параметра к классу"""
    param_class = db.query(ParameterClass).filter(ParameterClass.id == param_class_id).first()
    if not param_class:
        raise HTTPException(status_code=404, detail="Привязка параметра к классу не найдена")
    
    try:
        db.delete(param_class)
        db.commit()
        return {"success": True, "message": "Параметр отвязан от класса", "param_class_id": param_class_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==================== PRODUCTS ====================

@app.post("/products", tags=["🏷️ Изделия"], response_model=OperationResult)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    """Создать новое изделие"""
    result = classifier.add_product(db, data.класс_id, data.наименование, data.артикул)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/products", tags=["🏷️ Изделия"], response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    """Получить все изделия"""
    return classifier.get_all_products(db)

@app.get("/products/{product_id}", tags=["🏷️ Изделия"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Получить изделие по ID"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Изделие не найдено")
    class_name = product.class_node.название if product.class_node else None
    return {
        "id": product.id,
        "наименование": product.наименование,
        "артикул": product.артикул,
        "класс_id": product.класс_id,
        "класс_название": class_name,
    }

@app.put("/products/{product_id}", tags=["🏷️ Изделия"], response_model=OperationResult)
def update_product(product_id: int, data: ProductCreate, db: Session = Depends(get_db)):
    """Обновить изделие"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Изделие не найдено")
    try:
        product.наименование = data.наименование
        product.артикул = data.артикул
        product.класс_id = data.класс_id
        db.commit()
        return {"success": True, "message": "Изделие обновлено"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/products/{product_id}/values", tags=["🏷️ Изделия"], response_model=List[Dict[str, Any]])
def get_product_values(product_id: int, db: Session = Depends(get_db)):
    """Получить все значения параметров изделия"""
    return classifier.get_product_params_with_values(db, product_id)

@app.post("/products/{product_id}/values", tags=["🏷️ Изделия"], response_model=OperationResult)
def set_product_value(product_id: int, data: ParameterValueCreate, db: Session = Depends(get_db)):
    """Установить значение параметра для изделия"""
    result = classifier.set_product_param_value(db, product_id, data.param_class_id, data.value)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/products/{product_id}/values/{param_class_id}", tags=["🏷️ Изделия"], response_model=OperationResult)
def delete_product_value(product_id: int, param_class_id: int, db: Session = Depends(get_db)):
    """Удалить значение параметра у изделия"""
    result = classifier.delete_product_param_value(db, product_id, param_class_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/products/filter", tags=["🏷️ Изделия"])
def filter_products(data: ProductFilter, db: Session = Depends(get_db)):
    """Фильтрация изделий по классам и параметрам"""
    param_filters = []
    if data.param_filters:
        param_filters = [pf.dict() for pf in data.param_filters]
    result = classifier.filter_products(db, data.class_ids, param_filters)
    return result

# ==================== ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ (ЗАДАНИЕ 1.4) ====================

# Типы ХО
@app.post("/ho-types", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def create_ho_type(data: HOTypeCreate, db: Session = Depends(get_db)):
    result = classifier.add_ho_type(db, data.название, data.родительский_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/ho-types", tags=["📦 Хозяйственные операции"], response_model=List[HOTypeResponse])
def get_ho_types(db: Session = Depends(get_db)):
    return classifier.get_all_ho_types(db)

# Роли ХО
@app.post("/ho-types/{type_id}/roles", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def add_role_to_ho_type(type_id: int, data: HORoleCreate, db: Session = Depends(get_db)):
    result = classifier.add_role_to_ho_type(db, type_id, data.название, data.допустимый_класс_СХД)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/ho-types/{type_id}/roles", tags=["📦 Хозяйственные операции"], response_model=List[HORoleResponse])
def get_roles_of_ho_type(type_id: int, db: Session = Depends(get_db)):
    return classifier.get_roles_of_ho_type(db, type_id)

# Параметры для ХО
@app.post("/ho-types/{type_id}/parameters", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def add_parameter_to_ho_type(type_id: int, data: HOParameterCreate, db: Session = Depends(get_db)):
    result = classifier.add_parameter_to_ho_type(db, type_id, data.параметр_id, data.порядковый_номер, data.обязательный)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/ho-types/{type_id}/parameters", tags=["📦 Хозяйственные операции"], response_model=List[Dict[str, Any]])
def get_ho_type_parameters(type_id: int, db: Session = Depends(get_db)):
    return classifier.get_ho_type_parameters(db, type_id)

# Субъекты
@app.post("/subjects", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    result = classifier.add_subject(db, data.наименование, data.инн, data.контактное_лицо, data.телефон)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/subjects", tags=["📦 Хозяйственные операции"], response_model=List[SubjectResponse])
def get_subjects(db: Session = Depends(get_db)):
    return classifier.get_all_subjects(db)

# Экземпляры ХО
@app.post("/ho-operations", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def create_ho_operation(data: HOOperationCreate, db: Session = Depends(get_db)):
    result = classifier.create_ho_operation(db, data.тип_хо_id, data.номер_документа, data.дата)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.put("/ho-operations/{op_id}/actors", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def assign_actor(op_id: int, data: HORoleAssignmentCreate, db: Session = Depends(get_db)):
    result = classifier.assign_actor_to_role(db, op_id, data.роль_хо_id, data.субъект_хо_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/ho-operations/{op_id}/values", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def set_ho_parameter_value(op_id: int, data: HOParameterValueCreate, db: Session = Depends(get_db)):
    result = classifier.write_ho_parameter_value(db, op_id, data.параметр_хо_id, data.value)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/ho-operations/{op_id}/items", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def add_ho_item(op_id: int, data: HOItemCreate, db: Session = Depends(get_db)):
    result = classifier.add_ho_item(db, op_id, data.изделие_id, data.количество, data.цена)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/ho-operations/{op_id}", tags=["📦 Хозяйственные операции"], response_model=Dict[str, Any])
def get_ho_operation_full(op_id: int, db: Session = Depends(get_db)):
    return classifier.get_ho_operation_full(db, op_id)

@app.post("/ho-operations/filter", tags=["📦 Хозяйственные операции"], response_model=List[Dict[str, Any]])
def filter_ho_operations(filters: HOFilter, db: Session = Depends(get_db)):
    return classifier.filter_ho_operations(db, filters.тип_хо_id, filters.дата_от, filters.дата_до, filters.сумма_мин, filters.сумма_макс)

@app.get("/categories/tree", tags=["📂 Классификатор"])
def get_category_tree(
    include_products: bool = False, 
    db: Session = Depends(get_db)
):
    """
    Получить дерево классификатора
    
    Args:
        include_products: включать ли изделия (наборы, детали, фигурки) в дерево
    """
    if include_products:
        return classifier.build_category_tree_with_products(db)
    else:
        return classifier.build_category_tree(db)

@app.get("/categories/tree/{node_id}", tags=["📂 Классификатор"])
def get_subtree(node_id: int, db: Session = Depends(get_db)):
    """Получить поддерево от указанного узла"""
    # Получаем узел
    node = db.query(Classificator).filter(Classificator.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Узел не найден")
    
    # Строим дерево от этого узла
    trees = classifier.build_category_tree(db, root_id=node_id)
    return trees[0] if trees else None

@app.get("/sets")
def get_all_sets(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return classifier.get_all_sets(db, skip, limit)

@app.delete("/sets/{set_id}")
def delete_set(set_id: int, db: Session = Depends(get_db)):
    set_obj = db.query(Set).filter(Set.id == set_id).first()
    if not set_obj:
        raise HTTPException(404, "Set not found")
    db.delete(set_obj)
    db.commit()
    return {"success": True}

@app.get("/ho-operations")
def list_ho_operations(db: Session = Depends(get_db)):
    ops = db.query(HOOperation).order_by(HOOperation.дата.desc()).all()
    return [{"id": o.id, "номер": o.номер_документа, "дата": o.дата, "сумма": o.сумма} for o in ops]

# ==================== UPDATE AND DELETE FOR ALL ENTITIES ====================

# UPDATE Category
@app.put("/categories/{node_id}", tags=["📂 Классификатор"], response_model=OperationResult)
def update_category(node_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    """Обновить категорию"""
    node = db.query(Classificator).filter(Classificator.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    # Проверка уникальности имени
    existing = db.query(Classificator).filter(
        Classificator.название == data.name,
        Classificator.id != node_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Категория с таким именем уже существует")
    
    try:
        node.название = data.name
        if data.sort_order is not None:
            node.порядок_сортировки = data.sort_order
        db.commit()
        return {"success": True, "message": "Категория обновлена", "node_id": node_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE Set
@app.put("/sets/{set_id}", tags=["🧩 Наборы"], response_model=OperationResult)
def update_set(set_id: int, data: SetCreate, db: Session = Depends(get_db)):
    """Обновить набор"""
    set_obj = db.query(Set).filter(Set.id == set_id).first()
    if not set_obj:
        raise HTTPException(status_code=404, detail="Набор не найден")
    
    try:
        set_obj.номер_по_каталогу = data.catalog_number
        set_obj.год_выпуска = data.year
        set_obj.цена = data.price
        set_obj.количество_деталей = data.parts_count
        set_obj.id_возрастной_категории = data.age_category_id
        set_obj.id_тематики = data.theme_id
        # Обновляем название в классификаторе
        set_obj.classificator.название = data.name
        db.commit()
        return {"success": True, "message": "Набор обновлен", "product_id": set_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE Set (уже есть, но добавим возврат)
@app.delete("/sets/{set_id}", tags=["🧩 Наборы"], response_model=OperationResult)
def delete_set(set_id: int, db: Session = Depends(get_db)):
    """Удалить набор"""
    set_obj = db.query(Set).filter(Set.id == set_id).first()
    if not set_obj:
        raise HTTPException(status_code=404, detail="Набор не найден")
    try:
        db.delete(set_obj)
        db.commit()
        return {"success": True, "message": "Набор удален"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE Part
@app.delete("/parts/{part_id}", tags=["🔧 Детали"], response_model=OperationResult)
def delete_part(part_id: int, db: Session = Depends(get_db)):
    """Удалить деталь"""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Деталь не найдена")
    try:
        node = part.classificator
        db.delete(part)
        if node:
            db.delete(node)
        db.commit()
        return {"success": True, "message": "Деталь удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE Minifigure
@app.delete("/minifigures/{mf_id}", tags=["🧸 Мини-фигурки"], response_model=OperationResult)
def delete_minifigure(mf_id: int, db: Session = Depends(get_db)):
    """Удалить мини-фигурку"""
    mf = db.query(Minifigure).filter(Minifigure.id == mf_id).first()
    if not mf:
        raise HTTPException(status_code=404, detail="Мини-фигурка не найдена")
    try:
        db.delete(mf)
        db.commit()
        return {"success": True, "message": "Мини-фигурка удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE Theme
@app.put("/themes/{theme_id}", tags=["📚 Справочники"], response_model=OperationResult)
def update_theme(theme_id: int, data: ThemeCreate, db: Session = Depends(get_db)):
    """Обновить тематику"""
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Тематика не найдена")
    try:
        theme.classificator.название = data.name
        theme.описание = data.description
        db.commit()
        return {"success": True, "message": "Тематика обновлена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE Theme
@app.delete("/themes/{theme_id}", tags=["📚 Справочники"], response_model=OperationResult)
def delete_theme(theme_id: int, db: Session = Depends(get_db)):
    """Удалить тематику"""
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Тематика не найдена")
    try:
        db.delete(theme)
        db.commit()
        return {"success": True, "message": "Тематика удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE AgeCategory
@app.put("/age-categories/{cat_id}", tags=["📚 Справочники"], response_model=OperationResult)
def update_age_category(cat_id: int, data: AgeCategoryCreate, db: Session = Depends(get_db)):
    """Обновить возрастную категорию"""
    cat = db.query(AgeCategory).filter(AgeCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    try:
        cat.classificator.название = data.name
        cat.минимальный_возраст = data.min_age
        cat.максимальный_возраст = data.max_age
        db.commit()
        return {"success": True, "message": "Возрастная категория обновлена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE AgeCategory
@app.delete("/age-categories/{cat_id}", tags=["📚 Справочники"], response_model=OperationResult)
def delete_age_category(cat_id: int, db: Session = Depends(get_db)):
    """Удалить возрастную категорию"""
    cat = db.query(AgeCategory).filter(AgeCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    try:
        db.delete(cat)
        db.commit()
        return {"success": True, "message": "Возрастная категория удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE PartType
# @app.put("/part-types/{type_id}", tags=["📚 Справочники"], response_model=OperationResult)
# def update_part_type(type_id: int, data: PartTypeCreate, db: Session = Depends(get_db)):
#     """Обновить тип детали"""
#     pt = db.query(PartType).filter(PartType.id == type_id).first()
#     if not pt:
#         raise HTTPException(status_code=404, detail="Тип детали не найден")
#     try:
#         pt.classificator.название = data.name
#         pt.уровень_иерархии = data.hierarchy_level
#         db.commit()
#         return {"success": True, "message": "Тип детали обновлен"}
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=400, detail=str(e))
@app.put("/part-types/{type_id}", tags=["📚 Справочники"], response_model=OperationResult)
def update_part_type(type_id: int, data: PartTypeCreate, db: Session = Depends(get_db)):
    result = classifier.update_part_type(db, type_id, data.name, data.hierarchy_level)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# DELETE PartType
@app.delete("/part-types/{type_id}", tags=["📚 Справочники"], response_model=OperationResult)
def delete_part_type(type_id: int, db: Session = Depends(get_db)):
    """Удалить тип детали"""
    pt = db.query(PartType).filter(PartType.id == type_id).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Тип детали не найден")
    try:
        db.delete(pt)
        db.commit()
        return {"success": True, "message": "Тип детали удален"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE Parameter
@app.put("/parameters/{param_id}", tags=["⚙️ Параметры"], response_model=OperationResult)
def update_parameter(param_id: int, data: ParameterCreate, db: Session = Depends(get_db)):
    """Обновить параметр"""
    param = db.query(Parameter).filter(Parameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Параметр не найден")
    try:
        param.обозначение = data.обозначение
        param.полное_имя = data.полное_имя
        param.тип_параметра = data.тип_параметра
        param.единица_измерения = data.единица_измерения
        param.перечисление_id = data.перечисление_id
        db.commit()
        return {"success": True, "message": "Параметр обновлен"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE Parameter (уже есть, оставляем)

# DELETE Product
@app.delete("/products/{product_id}", tags=["🏷️ Изделия"], response_model=OperationResult)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Удалить изделие"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Изделие не найдено")
    try:
        db.delete(product)
        db.commit()
        return {"success": True, "message": "Изделие удалено"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE HOType
@app.put("/ho-types/{type_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def update_ho_type(type_id: int, data: HOTypeCreate, db: Session = Depends(get_db)):
    """Обновить тип ХО"""
    ho_type = db.query(HOType).filter(HOType.id == type_id).first()
    if not ho_type:
        raise HTTPException(status_code=404, detail="Тип ХО не найден")
    try:
        ho_type.название = data.название
        ho_type.родительский_id = data.родительский_id
        db.commit()
        return {"success": True, "message": "Тип ХО обновлен"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE HOType
@app.delete("/ho-types/{type_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def delete_ho_type(type_id: int, db: Session = Depends(get_db)):
    """Удалить тип ХО"""
    ho_type = db.query(HOType).filter(HOType.id == type_id).first()
    if not ho_type:
        raise HTTPException(status_code=404, detail="Тип ХО не найден")
    try:
        db.delete(ho_type)
        db.commit()
        return {"success": True, "message": "Тип ХО удален"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE HORole
@app.put("/ho-roles/{role_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def update_ho_role(role_id: int, data: HORoleCreate, db: Session = Depends(get_db)):
    """Обновить роль ХО"""
    role = db.query(HORole).filter(HORole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    try:
        role.название = data.название
        role.допустимый_класс_СХД = data.допустимый_класс_СХД
        db.commit()
        return {"success": True, "message": "Роль обновлена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE HORole
@app.delete("/ho-roles/{role_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def delete_ho_role(role_id: int, db: Session = Depends(get_db)):
    """Удалить роль ХО"""
    role = db.query(HORole).filter(HORole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    try:
        db.delete(role)
        db.commit()
        return {"success": True, "message": "Роль удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# UPDATE Subject
@app.put("/subjects/{subject_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def update_subject(subject_id: int, data: SubjectCreate, db: Session = Depends(get_db)):
    """Обновить субъекта"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Субъект не найден")
    try:
        subject.наименование = data.наименование
        subject.инн = data.инн
        subject.контактное_лицо = data.контактное_лицо
        subject.телефон = data.телефон
        db.commit()
        return {"success": True, "message": "Субъект обновлен"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE Subject
@app.delete("/subjects/{subject_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    """Удалить субъекта"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Субъект не найден")
    try:
        db.delete(subject)
        db.commit()
        return {"success": True, "message": "Субъект удален"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# DELETE HOOperation
@app.delete("/ho-operations/{op_id}", tags=["📦 Хозяйственные операции"], response_model=OperationResult)
def delete_ho_operation(op_id: int, db: Session = Depends(get_db)):
    """Удалить операцию"""
    op = db.query(HOOperation).filter(HOOperation.id == op_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    try:
        db.delete(op)
        db.commit()
        return {"success": True, "message": "Операция удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# GET single Set (for editing)
@app.get("/sets/{set_id}", tags=["🧩 Наборы"], response_model=dict)
def get_set(set_id: int, db: Session = Depends(get_db)):
    """Получить набор по ID"""
    set_obj = db.query(Set).filter(Set.id == set_id).first()
    if not set_obj:
        raise HTTPException(status_code=404, detail="Набор не найден")
    return {
        "id": set_obj.id,
        "name": set_obj.classificator.название,
        "catalog_number": set_obj.номер_по_каталогу,
        "year": set_obj.год_выпуска,
        "price": set_obj.цена,
        "parts_count": set_obj.количество_деталей,
        "age_category_id": set_obj.id_возрастной_категории,
        "theme_id": set_obj.id_тематики
    }

# GET single Parameter (for editing)
@app.get("/parameters/{param_id}", tags=["⚙️ Параметры"], response_model=dict)
def get_parameter(param_id: int, db: Session = Depends(get_db)):
    """Получить параметр по ID"""
    param = db.query(Parameter).filter(Parameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Параметр не найден")
    return {
        "id": param.id,
        "обозначение": param.обозначение,
        "полное_имя": param.полное_имя,
        "тип_параметра": param.тип_параметра,
        "единица_измерения": param.единица_измерения,
        "перечисление_id": param.перечисление_id
    }
