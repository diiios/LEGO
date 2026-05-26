# lego_classifier.py
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
from datetime import datetime

from models import (Classificator, Theme, AgeCategory, PartType, Set, Part, Minifigure,
                    SetPart, SetMinifigure, Enumeration, EnumValue, Parameter, ParameterClass,
                    Product, ParameterValue, HOType, HORole, HOParameter, Subject, HOOperation,
                    HORoleAssignment, HOParameterValue, HOItem)

class LegoClassifier:
    def __init__(self, engine):
        self.engine = engine
    
    def check_unique_code(self, db: Session, code: str, exclude_id: Optional[int] = None) -> bool:
        """Проверка уникальности названия"""
        query = db.query(Classificator).filter(Classificator.название == code)
        if exclude_id:
            query = query.filter(Classificator.id != exclude_id)
        return query.count() == 0
    
    def check_cycle(self, db: Session, node_id: int, new_parent_id: int) -> bool:
        """Проверка на циклы при перемещении"""
        if new_parent_id is None:
            return False
        
        # Рекурсивный CTE запрос для PostgreSQL
        sql = text("""
            WITH RECURSIVE ancestors(id) AS (
                SELECT CAST(:new_parent_id AS INTEGER)
                UNION ALL
                SELECT родительский_id FROM классификатор 
                INNER JOIN ancestors ON классификатор.id = ancestors.id
                WHERE родительский_id IS NOT NULL
            )
            SELECT COUNT(*) FROM ancestors WHERE id = CAST(:node_id AS INTEGER)
        """)
        result = db.execute(sql, {"new_parent_id": new_parent_id, "node_id": node_id})
        return result.scalar() > 0
    
    def get_max_sort_order(self, db: Session, parent_id: Optional[int]) -> int:
        """Получение максимального порядка сортировки"""
        max_order = db.query(func.coalesce(func.max(Classificator.порядок_сортировки), 0)).filter(
            Classificator.родительский_id == parent_id
        ).scalar()
        return max_order or 0
    
    def add_node(self, db: Session, name: str, node_type: str, parent_id: Optional[int] = None,
                 base_ei: Optional[int] = None, sort_order: Optional[int] = None) -> Dict[str, Any]:
        """Добавление новой вершины"""
        if not self.check_unique_code(db, name):
            return {"success": False, "message": "Узел с таким именем уже существует", "node_id": None}
        
        if sort_order is None:
            sort_order = self.get_max_sort_order(db, parent_id) + 1
        
        try:
            new_node = Classificator(
                название=name,
                тип_элемента=node_type,
                родительский_id=parent_id,
                порядок_сортировки=sort_order,
                базовая_ед_измерения=base_ei
            )
            db.add(new_node)
            db.commit()
            db.refresh(new_node)
            return {"success": True, "message": "Узел успешно добавлен", "node_id": new_node.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}", "node_id": None}
    
    def move_node(self, db: Session, node_id: int, new_parent_id: Optional[int]) -> Dict[str, Any]:
        """Перемещение вершины"""
        node = db.query(Classificator).filter(Classificator.id == node_id).first()
        if not node:
            return {"success": False, "message": "Узел не найден"}
        
        if self.check_cycle(db, node_id, new_parent_id):
            return {"success": False, "message": "Невозможно переместить: это создаст цикл"}
        
        try:
            node.родительский_id = new_parent_id
            db.commit()
            return {"success": True, "message": "Узел успешно перемещен"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def delete_node(self, db: Session, node_id: int) -> Dict[str, Any]:
        """Удаление вершины"""
        # Проверка на наличие потомков
        children_count = db.query(Classificator).filter(Classificator.родительский_id == node_id).count()
        if children_count > 0:
            return {"success": False, "message": "Невозможно удалить: узел имеет потомков"}
        
        try:
            node = db.query(Classificator).filter(Classificator.id == node_id).first()
            if node:
                db.delete(node)
                db.commit()
                return {"success": True, "message": "Узел успешно удален"}
            return {"success": False, "message": "Узел не найден"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def reorder_children(self, db: Session, parent_id: int, ordered_child_ids: List[int]) -> Dict[str, Any]:
        """Изменение порядка потомков"""
        try:
            for idx, child_id in enumerate(ordered_child_ids, 1):
                child = db.query(Classificator).filter(
                    Classificator.id == child_id,
                    Classificator.родительский_id == parent_id
                ).first()
                if not child:
                    return {"success": False, "message": f"Узел {child_id} не является потомком узла {parent_id}"}
                child.порядок_сортировки = idx
            db.commit()
            return {"success": True, "message": "Порядок потомков успешно изменен"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def set_base_unit(self, db: Session, node_id: int, base_ei_id: int) -> Dict[str, Any]:
        """Установка базовой единицы измерения"""
        try:
            node = db.query(Classificator).filter(Classificator.id == node_id).first()
            if node:
                node.базовая_ед_измерения = base_ei_id
                db.commit()
                return {"success": True, "message": "Единица измерения успешно установлена"}
            return {"success": False, "message": "Узел не найден"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def get_descendants(self, db: Session, node_id: int) -> List[Dict[str, Any]]:
        """Поиск всех потомков"""
        sql = text("""
            WITH RECURSIVE descendants AS (
                SELECT id, название, тип_элемента, родительский_id, 0 as уровень, порядок_сортировки
                FROM классификатор WHERE id = :node_id
                UNION ALL
                SELECT c.id, c.название, c.тип_элемента, c.родительский_id, d.уровень + 1, c.порядок_сортировки
                FROM классификатор c INNER JOIN descendants d ON c.родительский_id = d.id
            )
            SELECT id, название, тип_элемента, родительский_id, уровень, порядок_сортировки
            FROM descendants WHERE id != :node_id ORDER BY уровень, порядок_сортировки, название
        """)
        result = db.execute(sql, {"node_id": node_id})
        return [dict(row._mapping) for row in result]
    
    def get_ancestors(self, db: Session, node_id: int) -> List[Dict[str, Any]]:
        """Поиск всех родителей"""
        sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT id, название, тип_элемента, родительский_id, 0 as уровень
                FROM классификатор WHERE id = :node_id
                UNION ALL
                SELECT c.id, c.название, c.тип_элемента, c.родительский_id, a.уровень + 1
                FROM классификатор c INNER JOIN ancestors a ON c.id = a.родительский_id
            )
            SELECT id, название, тип_элемента, родительский_id, уровень
            FROM ancestors WHERE id != :node_id ORDER BY уровень
        """)
        result = db.execute(sql, {"node_id": node_id})
        return [dict(row._mapping) for row in result]
    
    def get_terminal_descendants(self, db: Session, node_id: int) -> List[Dict[str, Any]]:
        """Поиск терминальных классов"""
        sql = text("""
            WITH RECURSIVE descendants AS (
                SELECT id, название, тип_элемента, родительский_id
                FROM классификатор WHERE id = :node_id
                UNION ALL
                SELECT c.id, c.название, c.тип_элемента, c.родительский_id
                FROM классификатор c INNER JOIN descendants d ON c.родительский_id = d.id
            )
            SELECT id, название, тип_элемента, родительский_id
            FROM descendants WHERE тип_элемента IN ('терминальный', 'набор') ORDER BY название
        """)
        result = db.execute(sql, {"node_id": node_id})
        return [dict(row._mapping) for row in result]
    
    def detect_cycles(self, db: Session) -> List[Dict[str, Any]]:
        """Диагностика циклов во всем классификаторе"""
        # Упрощенная проверка - ищем узлы, у которых родитель ссылается на потомка
        sql = text("""
            WITH RECURSIVE tree(id, root_id, path, depth) AS (
                SELECT id, id, название::text, 0 FROM классификатор
                UNION ALL
                SELECT tree.id, c.родительский_id, tree.path || ' -> ' || c.название, tree.depth + 1
                FROM tree JOIN классификатор c ON c.id = tree.root_id
                WHERE c.родительский_id IS NOT NULL AND tree.depth < 20
            )
            SELECT DISTINCT tree.id, к.название, tree.path
            FROM tree JOIN классификатор к ON к.id = tree.id
            WHERE tree.root_id = tree.id AND tree.depth > 0
        """)
        result = db.execute(sql)
        return [{"node_id": row[0], "node_name": row[1], "path": row[2]} for row in result]
    
    def add_set(self, db: Session, name: str, catalog_number: str, year: int, price: float,
                parts_count: int, age_category_id: int, theme_id: int, parent_id: Optional[int] = None) -> Dict[str, Any]:
        """Добавление набора"""
        node_result = self.add_node(db, name, 'набор', parent_id)
        if not node_result["success"]:
            return node_result
        
        try:
            new_set = Set(
                id_классификатора=node_result["node_id"],
                номер_по_каталогу=catalog_number,
                год_выпуска=year,
                цена=price,
                количество_деталей=parts_count,
                id_возрастной_категории=age_category_id,
                id_тематики=theme_id
            )
            db.add(new_set)
            db.commit()
            db.refresh(new_set)
            return {"success": True, "message": "Набор успешно добавлен", "product_id": new_set.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}", "product_id": None}
    
    def _serialize_part(self, part: Part) -> Dict[str, Any]:
        """Словарь детали с названием типа (не только id)."""
        type_name = None
        if part.part_type and part.part_type.classificator:
            type_name = part.part_type.classificator.название
        return {
            "id": part.id,
            "name": part.classificator.название if part.classificator else "",
            "part_type_id": part.id_типа,
            "type_name": type_name,
        }

    def _parts_query(self, db: Session):
        return db.query(Part).options(
            joinedload(Part.classificator),
            joinedload(Part.part_type).joinedload(PartType.classificator),
        )

    def add_part(self, db: Session, name: str, part_type_id: int) -> Dict[str, Any]:
        """Добавление детали"""
        existing_node = db.query(Classificator).filter(Classificator.название == name).first()
        if existing_node:
            if db.query(Part).filter(Part.id_классификатора == existing_node.id).first():
                return {"success": False, "message": "Деталь с таким именем уже существует", "product_id": None}
            node_id = existing_node.id
        else:
            node_result = self.add_node(db, name, "терминальный", None)
            if not node_result["success"]:
                return node_result
            node_id = node_result["node_id"]
        
        try:
            new_part = Part(
                id_классификатора=node_id,
                id_типа=part_type_id
            )
            db.add(new_part)
            db.commit()
            db.refresh(new_part)
            return {"success": True, "message": f"Деталь '{name}' добавлена", "product_id": new_part.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def add_minifigure(self, db: Session, name: str, character: str, series: str, unique_code: str) -> Dict[str, Any]:
        """Добавление мини-фигурки"""
        node_result = self.add_node(db, name, "терминальный", None)
        if not node_result["success"]:
            return node_result
        
        try:
            new_minifigure = Minifigure(
                id_классификатора=node_result["node_id"],
                персонаж=character,
                серия=series,
                уникальный_код=unique_code
            )
            db.add(new_minifigure)
            db.commit()
            db.refresh(new_minifigure)
            return {"success": True, "message": f"Мини-фигурка '{name}' добавлена", "product_id": new_minifigure.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def get_set_contents(self, db: Session, set_id: int) -> List[Dict[str, Any]]:
        """Получение состава набора"""
        sql = text("""
            SELECT 'Изделие' as item_type, и.id as item_id, и.наименование as item_name,
                   сн.количество_штук as quantity, NULL as color, и.артикул as sku
            FROM набор н
            INNER JOIN состав_набора сн ON сн.id_набора = н.id
            INNER JOIN изделие и ON и.id = сн.id_детали
            WHERE н.id = :set_id
            UNION ALL
            SELECT 'Мини-фигурка' as item_type, мф.id as item_id, кл.название as item_name,
                   фвн.количество_штук as quantity, NULL as color, мф.уникальный_код as sku
            FROM набор н
            INNER JOIN фигурки_в_наборе фвн ON фвн.id_набора = н.id
            INNER JOIN мини_фигурка мф ON мф.id = фвн.id_фигурки
            INNER JOIN классификатор кл ON кл.id = мф.id_классификатора
            WHERE н.id = :set_id
        """)
        result = db.execute(sql, {"set_id": set_id})
        return [dict(row._mapping) for row in result]

    def add_set_product_item(self, db: Session, set_id: int, product_id: int, quantity: int) -> Dict[str, Any]:
        if quantity <= 0:
            return {"success": False, "message": "Количество должно быть больше 0"}
        if not db.query(Set).filter(Set.id == set_id).first():
            return {"success": False, "message": "Набор не найден"}
        if not db.query(Product).filter(Product.id == product_id).first():
            return {"success": False, "message": "Изделие не найдено"}
        item = db.query(SetPart).filter(SetPart.id_набора == set_id, SetPart.id_детали == product_id).first()
        if item:
            item.количество_штук = quantity
        else:
            db.add(SetPart(id_набора=set_id, id_детали=product_id, количество_штук=quantity))
        db.commit()
        return {"success": True, "message": "Позиция состава сохранена"}

    def delete_set_product_item(self, db: Session, set_id: int, product_id: int) -> Dict[str, Any]:
        deleted = db.query(SetPart).filter(SetPart.id_набора == set_id, SetPart.id_детали == product_id).delete()
        db.commit()
        if not deleted:
            return {"success": False, "message": "Позиция состава не найдена"}
        return {"success": True, "message": "Позиция состава удалена"}
    
    def search_by_theme(self, db: Session, theme_name: str) -> List[Dict[str, Any]]:
        """Поиск по тематике"""
        sql = text("""
            SELECT кл.название as set_name, н.номер_по_каталогу as catalog_number,
                   н.год_выпуска as year, н.цена as price, тема_кл.название as theme_name
            FROM набор н
            JOIN классификатор кл ON кл.id = н.id_классификатора
            JOIN тематика т ON т.id = н.id_тематики
            JOIN классификатор тема_кл ON тема_кл.id = т.id_классификатора
            WHERE тема_кл.название LIKE '%' || :theme_name || '%'
            ORDER BY н.год_выпуска DESC
        """)
        result = db.execute(sql, {"theme_name": theme_name})
        return [dict(row._mapping) for row in result]
    
    def search_by_age(self, db: Session, age: int) -> List[Dict[str, Any]]:
        """Поиск по возрасту"""
        sql = text("""
            SELECT кл.название as set_name, н.номер_по_каталогу as catalog_number,
                   вк.минимальный_возраст as min_age, вк.максимальный_возраст as max_age, н.цена as price
            FROM набор н
            JOIN классификатор кл ON кл.id = н.id_классификатора
            JOIN возрастная_категория вк ON вк.id = н.id_возрастной_категории
            WHERE :age BETWEEN вк.минимальный_возраст AND вк.максимальный_возраст
            ORDER BY вк.минимальный_возраст
        """)
        result = db.execute(sql, {"age": age})
        return [dict(row._mapping) for row in result]
    
    def search_by_part_type(self, db: Session, type_name: str) -> List[Dict[str, Any]]:
        """Поиск по типу детали"""
        sql = text("""
            SELECT кл.название as part_name, тип_кл.название as type_name
            FROM деталь д
            JOIN классификатор кл ON кл.id = д.id_классификатора
            JOIN тип_детали тд ON тд.id = д.id_типа
            JOIN классификатор тип_кл ON тип_кл.id = тд.id_классификатора
            WHERE тип_кл.название LIKE '%' || :type_name || '%'
            ORDER BY кл.название
        """)
        result = db.execute(sql, {"type_name": type_name})
        return [dict(row._mapping) for row in result]
    
    def get_all_categories(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех категорий"""
        categories = db.query(Classificator).order_by(Classificator.id).all()
        return [{
            "id": c.id,
            "name": c.название,
            "node_type": c.тип_элемента,
            "parent_id": c.родительский_id,
            "sort_order": c.порядок_сортировки
        } for c in categories]
    
    def get_all_sets(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех наборов"""
        sets = db.query(Set).join(Classificator, Classificator.id == Set.id_классификатора).all()
        return [{
            "id": s.id,
            "name": s.classificator.название,
            "catalog_number": s.номер_по_каталогу,
            "year": s.год_выпуска,
            "price": s.цена,
            "parts_count": s.количество_деталей
        } for s in sets]
    
    def get_all_parts(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех деталей"""
        parts = self._parts_query(db).all()
        return [self._serialize_part(p) for p in parts]

    def filter_parts(
        self,
        db: Session,
        part_type_id: Optional[int] = None,
        color: Optional[str] = None,
        name_contains: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Фильтр деталей по типу и названию. Цвет/размер/вес задаются параметрами изделий."""
        q = self._parts_query(db)
        if part_type_id is not None:
            q = q.filter(Part.id_типа == part_type_id)
        q = q.join(Classificator, Classificator.id == Part.id_классификатора)
        if name_contains:
            q = q.filter(Classificator.название.ilike(f"%{name_contains.strip()}%"))
        parts = q.order_by(Classificator.название).all()
        return [self._serialize_part(p) for p in parts]

    def remove_anomalous_parts(self, db: Session) -> Dict[str, Any]:
        """Удаление ошибочных деталей (нереалистичный вес и т.п.)."""
        from models import SetPart
        anomalies = db.query(Part).filter(Part.вес > 500).all()
        removed = []
        for part in anomalies:
            name = part.classificator.название if part.classificator else f"id={part.id}"
            db.query(SetPart).filter(SetPart.id_детали == part.id).delete(synchronize_session=False)
            cls = part.classificator
            db.delete(part)
            if cls:
                db.delete(cls)
            removed.append(name)
        if removed:
            db.commit()
        return {
            "success": True,
            "removed_count": len(removed),
            "removed_names": removed,
            "message": f"Удалено ошибочных деталей: {len(removed)}" if removed else "Ошибочных деталей не найдено",
        }
    
    def get_all_minifigures(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех мини-фигурок"""
        minifigures = db.query(Minifigure).join(Classificator, Classificator.id == Minifigure.id_классификатора).all()
        return [{
            "id": m.id,
            "name": m.classificator.название,
            "character": m.персонаж,
            "series": m.серия,
            "unique_code": m.уникальный_код
        } for m in minifigures]
    
    def get_all_themes(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех тематик"""
        themes = db.query(Theme).join(Classificator, Classificator.id == Theme.id_классификатора).all()
        return [{
            "id": t.id,
            "name": t.classificator.название,
            "description": t.описание
        } for t in themes]
    
    def get_all_age_categories(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех возрастных категорий"""
        age_cats = db.query(AgeCategory).join(Classificator, Classificator.id == AgeCategory.id_классификатора).all()
        return [{
            "id": a.id,
            "name": a.classificator.название,
            "min_age": a.минимальный_возраст,
            "max_age": a.максимальный_возраст
        } for a in age_cats]
    
    def get_all_part_types(self, db: Session) -> List[Dict[str, Any]]:
        """Получение всех типов деталей"""
        part_types = db.query(PartType).join(Classificator, Classificator.id == PartType.id_классификатора).all()
        return [{
            "id": p.id,
            "name": p.classificator.название,
            "hierarchy_level": p.уровень_иерархии
        } for p in part_types]
    
    def add_theme(self, db: Session, name: str, description: str) -> Dict[str, Any]:
        """Добавление тематики"""
        node_result = self.add_node(db, name, "тематика", None)
        if not node_result["success"]:
            return node_result
        
        try:
            new_theme = Theme(
                id_классификатора=node_result["node_id"],
                описание=description
            )
            db.add(new_theme)
            db.commit()
            return {"success": True, "message": f"Тематика '{name}' добавлена", "node_id": node_result["node_id"]}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def add_age_category(self, db: Session, name: str, min_age: int, max_age: int) -> Dict[str, Any]:
        """Добавление возрастной категории"""
        node_result = self.add_node(db, name, "возрастная_категория", None)
        if not node_result["success"]:
            return node_result
        
        try:
            new_age_cat = AgeCategory(
                id_классификатора=node_result["node_id"],
                минимальный_возраст=min_age,
                максимальный_возраст=max_age
            )
            db.add(new_age_cat)
            db.commit()
            return {"success": True, "message": f"Возрастная категория '{name}' добавлена", "node_id": node_result["node_id"]}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
    def add_part_type(self, db: Session, name: str, hierarchy_level: int) -> Dict[str, Any]:
        """Добавление типа детали"""
        node_result = self.add_node(db, name, "тип_детали", None)
        if not node_result["success"]:
            return node_result
        
        try:
            new_part_type = PartType(
                id_классификатора=node_result["node_id"],
                уровень_иерархии=hierarchy_level
            )
            db.add(new_part_type)
            db.commit()
            db.refresh(new_part_type)
            return {
                "success": True,
                "message": f"Тип детали '{name}' добавлен",
                "node_id": node_result["node_id"],
                "product_id": new_part_type.id,
            }
        except Exception as e:
            db.rollback()
            return {"success": False, "message": f"Ошибка: {str(e)}"}
    
        # ========== ПЕРЕЧИСЛЕНИЯ (ЗАДАНИЕ 1.2) ==========

    def add_enumeration(self, db: Session, name: str, description: str = None) -> Dict[str, Any]:
        """Создать новое перечисление"""
        exists = db.query(Enumeration).filter(Enumeration.name == name).first()
        if exists:
            return {"success": False, "message": f"Перечисление '{name}' уже существует"}
        try:
            enum = Enumeration(name=name, description=description)
            db.add(enum)
            db.commit()
            db.refresh(enum)
            return {"success": True, "message": "Перечисление создано", "enum_id": enum.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_all_enumerations(self, db: Session) -> List[Dict[str, Any]]:
        """Получить все перечисления с количеством значений"""
        enums = db.query(Enumeration).all()
        result = []
        for e in enums:
            values_count = db.query(EnumValue).filter(EnumValue.enumeration_id == e.id).count()
            result.append({
                "id": e.id,
                "name": e.name,
                "description": e.description,
                "created_at": e.created_at,
                "values_count": values_count
            })
        return result

    def get_enumeration_by_id(self, db: Session, enum_id: int) -> Dict[str, Any]:
        """Получить перечисление по ID"""
        enum = db.query(Enumeration).filter(Enumeration.id == enum_id).first()
        if not enum:
            return {"success": False, "message": "Перечисление не найдено"}
        return {
            "success": True,
            "id": enum.id,
            "name": enum.name,
            "description": enum.description,
            "created_at": enum.created_at
        }

    def update_enumeration(self, db: Session, enum_id: int, name: str = None, description: str = None) -> Dict[str, Any]:
        """Обновить перечисление"""
        enum = db.query(Enumeration).filter(Enumeration.id == enum_id).first()
        if not enum:
            return {"success": False, "message": "Перечисление не найдено"}
        try:
            if name is not None:
                enum.name = name
            if description is not None:
                enum.description = description
            db.commit()
            return {"success": True, "message": "Перечисление обновлено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def delete_enumeration(self, db: Session, enum_id: int) -> Dict[str, Any]:
        """Удалить перечисление (каскадно удалит все значения)"""
        enum = db.query(Enumeration).filter(Enumeration.id == enum_id).first()
        if not enum:
            return {"success": False, "message": "Перечисление не найдено"}
        try:
            db.delete(enum)
            db.commit()
            return {"success": True, "message": "Перечисление удалено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    # ----- Значения перечислений -----

    def add_enum_value(self, db: Session, enum_id: int, value: str, sort_order: int = None, extra_data: dict = None) -> Dict[str, Any]:
        """Добавить значение в перечисление"""
        enum = db.query(Enumeration).filter(Enumeration.id == enum_id).first()
        if not enum:
            return {"success": False, "message": "Перечисление не найдено"}
        if sort_order is None:
            max_order = db.query(func.coalesce(func.max(EnumValue.sort_order), 0)).filter(EnumValue.enumeration_id == enum_id).scalar()
            sort_order = max_order + 1
        try:
            ev = EnumValue(enumeration_id=enum_id, value=value, sort_order=sort_order, extra_data=extra_data)
            db.add(ev)
            db.commit()
            db.refresh(ev)
            return {"success": True, "message": "Значение добавлено", "value_id": ev.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_enum_values(self, db: Session, enum_id: int) -> List[Dict[str, Any]]:
        """Получить все значения перечисления (сортировка по sort_order)"""
        values = db.query(EnumValue).filter(EnumValue.enumeration_id == enum_id).order_by(EnumValue.sort_order).all()
        return [{
            "id": v.id, 
            "enumeration_id": v.enumeration_id,
            "value": v.value, 
            "sort_order": v.sort_order, 
            "extra_data": v.extra_data
        } for v in values]

    def update_enum_value(self, db: Session, value_id: int, value: str = None, sort_order: int = None, extra_data: dict = None) -> Dict[str, Any]:
        """Обновить значение перечисления"""
        ev = db.query(EnumValue).filter(EnumValue.id == value_id).first()
        if not ev:
            return {"success": False, "message": "Значение не найдено"}
        try:
            if value is not None:
                ev.value = value
            if sort_order is not None:
                ev.sort_order = sort_order
            if extra_data is not None:
                ev.extra_data = extra_data
            db.commit()
            return {"success": True, "message": "Значение обновлено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def reorder_enum_values(self, db: Session, enum_id: int, ordered_ids: List[int]) -> Dict[str, Any]:
        """Изменить порядок значений перечисления"""
        # Проверка, что все ID принадлежат этому перечислению
        for idx, vid in enumerate(ordered_ids, start=1):
            ev = db.query(EnumValue).filter(EnumValue.id == vid, EnumValue.enumeration_id == enum_id).first()
            if not ev:
                return {"success": False, "message": f"Значение {vid} не принадлежит перечислению {enum_id}"}
        try:
            for idx, vid in enumerate(ordered_ids, start=1):
                db.query(EnumValue).filter(EnumValue.id == vid).update({"sort_order": idx})
            db.commit()
            return {"success": True, "message": "Порядок значений изменён"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def delete_enum_value(self, db: Session, value_id: int) -> Dict[str, Any]:
        """Удалить значение перечисления"""
        ev = db.query(EnumValue).filter(EnumValue.id == value_id).first()
        if not ev:
            return {"success": False, "message": "Значение не найдено"}
        try:
            db.delete(ev)
            db.commit()
            return {"success": True, "message": "Значение удалено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}
    
    # ========== ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ (ЗАДАНИЕ 1.4) ==========

    # --- Типы ХО ---
    def add_ho_type(self, db: Session, название: str, родительский_id: int = None) -> Dict[str, Any]:
        """Создать новый тип ХО (возможно, с наследованием)"""
        # Проверка на дублирование названия
        exists = db.query(HOType).filter(HOType.название == название).first()
        if exists:
            return {"success": False, "message": f"Тип ХО с названием '{название}' уже существует"}
        
        try:
            new_type = HOType(название=название, родительский_id=родительский_id)
            db.add(new_type)
            db.commit()
            db.refresh(new_type)
            # Наследуем роли и параметры от родителя
            if родительский_id:
                parent = db.query(HOType).filter(HOType.id == родительский_id).first()
                if parent:
                    for role in parent.roles:
                        self.add_role_to_ho_type(db, new_type.id, role.название, role.допустимый_класс_СХД)
                    for hp in parent.parameters:
                        self.add_parameter_to_ho_type(db, new_type.id, hp.параметр_id, hp.порядковый_номер, hp.обязательный)
            return {"success": True, "message": "Тип ХО создан", "type_id": new_type.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_all_ho_types(self, db: Session) -> List[Dict[str, Any]]:
        """Получить все типы ХО (деревом)"""
        types = db.query(HOType).all()
        return [{"id": t.id, "название": t.название, "родительский_id": t.родительский_id, "created_at": t.created_at} for t in types]

    # --- Роли ---
    def add_role_to_ho_type(self, db: Session, тип_хо_id: int, название: str, допустимый_класс_СХД: int = None) -> Dict[str, Any]:
        """Добавить допустимую роль для типа ХО"""
        # Проверка существования типа ХО
        ho_type = db.query(HOType).filter(HOType.id == тип_хо_id).first()
        if not ho_type:
            return {"success": False, "message": f"Тип ХО с id {тип_хо_id} не найден"}
        
        # Проверка на дублирование роли
        exists = db.query(HORole).filter(
            HORole.тип_хо_id == тип_хо_id,
            HORole.название == название
        ).first()
        if exists:
            return {"success": False, "message": f"Роль '{название}' уже существует для типа ХО '{ho_type.название}'"}
        
        try:
            role = HORole(тип_хо_id=тип_хо_id, название=название, допустимый_класс_СХД=допустимый_класс_СХД)
            db.add(role)
            db.commit()
            db.refresh(role)
            return {"success": True, "message": "Роль добавлена", "role_id": role.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_roles_of_ho_type(self, db: Session, тип_хо_id: int) -> List[Dict[str, Any]]:
        """Получить список ролей для типа ХО"""
        roles = db.query(HORole).filter(HORole.тип_хо_id == тип_хо_id).all()
        return [{
            "id": r.id,
            "тип_хо_id": r.тип_хо_id,
            "название": r.название,
            "допустимый_класс_СХД": r.допустимый_класс_СХД
        } for r in roles]

    # --- Параметры для ХО ---
    def add_parameter_to_ho_type(self, db: Session, тип_хо_id: int, параметр_id: int,
                             порядковый_номер: int = None, обязательный: bool = False) -> Dict[str, Any]:
        """Привязать существующий параметр (из 1.3) к типу ХО"""
        # Проверка существования типа ХО
        ho_type = db.query(HOType).filter(HOType.id == тип_хо_id).first()
        if not ho_type:
            return {"success": False, "message": f"Тип ХО с id {тип_хо_id} не найден"}
        
        # Проверка существования параметра
        param = db.query(Parameter).filter(Parameter.id == параметр_id).first()
        if not param:
            return {"success": False, "message": f"Параметр с id {параметр_id} не найден"}
        
        # Проверка на дублирование привязки
        exists = db.query(HOParameter).filter(
            HOParameter.тип_хо_id == тип_хо_id,
            HOParameter.параметр_id == параметр_id
        ).first()
        if exists:
            return {"success": False, "message": f"Параметр '{param.обозначение}' уже привязан к типу ХО '{ho_type.название}'"}
        
        if порядковый_номер is None:
            max_order = db.query(func.coalesce(func.max(HOParameter.порядковый_номер), 0)).filter(
                HOParameter.тип_хо_id == тип_хо_id
            ).scalar()
            порядковый_номер = max_order + 1
        try:
            hp = HOParameter(тип_хо_id=тип_хо_id, параметр_id=параметр_id,
                            порядковый_номер=порядковый_номер, обязательный=1 if обязательный else 0)
            db.add(hp)
            db.commit()
            db.refresh(hp)
            return {"success": True, "message": "Параметр привязан к типу ХО", "hoparam_id": hp.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_ho_type_parameters(self, db: Session, тип_хо_id: int) -> List[Dict[str, Any]]:
        """Получить параметры для типа ХО (с учётом наследования)"""
        # Собираем все параметры по иерархии типов
        type_ids = []
        current_id = тип_хо_id
        while current_id:
            type_ids.append(current_id)
            parent = db.query(HOType).filter(HOType.id == current_id).first()
            current_id = parent.родительский_id if parent else None
        params = db.query(HOParameter).filter(HOParameter.тип_хо_id.in_(type_ids)).all()
        result = []
        for hp in params:
            param = db.query(Parameter).filter(Parameter.id == hp.параметр_id).first()
            result.append({
                "hoparam_id": hp.id,
                "параметр_id": param.id,
                "обозначение": param.обозначение,
                "полное_имя": param.полное_имя,
                "тип_параметра": param.тип_параметра,
                "единица_измерения": param.единица_измерения,
                "порядковый_номер": hp.порядковый_номер,
                "обязательный": hp.обязательный
            })
        result.sort(key=lambda x: x["порядковый_номер"])
        return result

    # --- Субъекты (контрагенты) ---
    def add_subject(self, db: Session, наименование: str, инн: str = None, контактное_лицо: str = None, телефон: str = None) -> Dict[str, Any]:
        """Добавить нового субъекта хозяйственной деятельности"""
        try:
            subj = Subject(наименование=наименование, инн=инн, контактное_лицо=контактное_лицо, телефон=телефон)
            db.add(subj)
            db.commit()
            db.refresh(subj)
            return {"success": True, "message": "Субъект добавлен", "subject_id": subj.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_all_subjects(self, db: Session) -> List[Dict[str, Any]]:
        subjects = db.query(Subject).all()
        return [{"id": s.id, "наименование": s.наименование, "инн": s.инн, "контактное_лицо": s.контактное_лицо, "телефон": s.телефон} for s in subjects]

    # --- Экземпляры ХО ---
    def create_ho_operation(self, db: Session, тип_хо_id: int, номер_документа: str, дата: datetime) -> Dict[str, Any]:
        """Создать экземпляр ХО. Автоматически создаются заготовки для параметров и ролей."""
        # Проверка существования типа ХО
        ho_type = db.query(HOType).filter(HOType.id == тип_хо_id).first()
        if not ho_type:
            return {"success": False, "message": f"Тип ХО с id {тип_хо_id} не найден"}
        
        # Проверка на дублирование номера документа
        exists = db.query(HOOperation).filter(HOOperation.номер_документа == номер_документа).first()
        if exists:
            return {"success": False, "message": f"Операция с номером документа '{номер_документа}' уже существует"}
        
        try:
            op = HOOperation(тип_хо_id=тип_хо_id, номер_документа=номер_документа, дата=дата, сумма=0.0)
            db.add(op)
            db.flush()

            # Создать заготовки параметров ХО (со значениями NULL)
            ho_params = self.get_ho_type_parameters(db, тип_хо_id)
            for hp in ho_params:
                pv = HOParameterValue(операция_id=op.id, параметр_хо_id=hp["hoparam_id"])
                db.add(pv)

            # Создать заготовки ролей (без назначенных субъектов)
            roles = self.get_roles_of_ho_type(db, тип_хо_id)
            for r in roles:
                ra = HORoleAssignment(операция_id=op.id, роль_хо_id=r["id"])
                db.add(ra)

            db.commit()
            db.refresh(op)
            return {"success": True, "message": "ХО создана", "operation_id": op.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def assign_actor_to_role(self, db: Session, операция_id: int, роль_хо_id: int, субъект_хо_id: int) -> Dict[str, Any]:
        """Назначить конкретного субъекта на роль в ХО"""
        # Проверка существования операции
        operation = db.query(HOOperation).filter(HOOperation.id == операция_id).first()
        if not operation:
            return {"success": False, "message": f"Операция с id {операция_id} не найдена"}
        
        # Проверка существования роли
        role = db.query(HORole).filter(HORole.id == роль_хо_id).first()
        if not role:
            return {"success": False, "message": f"Роль с id {роль_хо_id} не найдена"}
        
        # Проверка существования субъекта
        subject = db.query(Subject).filter(Subject.id == субъект_хо_id).first()
        if not subject:
            return {"success": False, "message": f"Субъект с id {субъект_хо_id} не найден"}
        
        # Проверка, что роль существует для данной операции
        assignment = db.query(HORoleAssignment).filter(
            HORoleAssignment.операция_id == операция_id,
            HORoleAssignment.роль_хо_id == роль_хо_id
        ).first()
        if not assignment:
            return {"success": False, "message": "Роль не найдена в данной операции"}
        
        try:
            assignment.субъект_хо_id = субъект_хо_id
            db.commit()
            return {"success": True, "message": f"Субъект '{subject.наименование}' назначен на роль '{role.название}'"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def write_ho_parameter_value(self, db: Session, операция_id: int, параметр_хо_id: int, value: Any) -> Dict[str, Any]:
        """Записать значение параметра для ХО (с валидацией типа)"""
        pv = db.query(HOParameterValue).filter(
            HOParameterValue.операция_id == операция_id,
            HOParameterValue.параметр_хо_id == параметр_хо_id
        ).first()
        if not pv:
            return {"success": False, "message": "Параметр не найден для данной операции"}

        # Получить описание параметра из HOParameter -> Parameter
        hp = db.query(HOParameter).filter(HOParameter.id == параметр_хо_id).first()
        if not hp:
            return {"success": False, "message": "Ошибка привязки параметра"}
        param = db.query(Parameter).filter(Parameter.id == hp.параметр_id).first()
        if not param:
            return {"success": False, "message": "Параметр не найден"}

        # Валидация (аналогично 1.3, но без ограничений мин/макс, т.к. они на уровне ParameterClass, а здесь их нет)
        validated = self._validate_param_value_for_ho(db, param, value)  # отдельный метод (см. ниже)
        if not validated["success"]:
            return validated

        # Заполняем поля
        try:
            pv.значение_число = validated.get("число")
            pv.значение_строка = validated.get("строка")
            pv.значение_дата = validated.get("дата")
            pv.значение_перечисление_id = validated.get("перечисление_id")
            db.commit()
            return {"success": True, "message": "Значение параметра сохранено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def _validate_param_value_for_ho(self, db: Session, param: Parameter, value: Any) -> Dict:
        """Вспомогательная валидация для параметров ХО (без ограничений)"""
        if param.тип_параметра == 'REAL':
            try:
                num_val = float(value)
            except:
                return {"success": False, "message": f"Значение '{value}' не является числом"}
            return {"success": True, "число": num_val}
        elif param.тип_параметра == 'INTEGER':
            try:
                int_val = int(value)
            except:
                return {"success": False, "message": f"Значение '{value}' не является целым числом"}
            return {"success": True, "число": int_val}
        elif param.тип_параметра == 'STRING':
            return {"success": True, "строка": str(value)}
        elif param.тип_параметра == 'DATETIME':
            try:
                if isinstance(value, datetime):
                    dt_val = value
                else:
                    dt_val = datetime.fromisoformat(str(value))
            except:
                return {"success": False, "message": f"Значение '{value}' не является датой"}
            return {"success": True, "дата": dt_val}
        elif param.тип_параметра == 'ENUM':
            if not param.перечисление_id:
                return {"success": False, "message": "Для параметра-перечисления не указано перечисление"}
            enum_value = db.query(EnumValue).filter(
                EnumValue.id == value,
                EnumValue.enumeration_id == param.перечисление_id
            ).first()
            if not enum_value:
                return {"success": False, "message": f"Значение с ID {value} не найдено в перечислении"}
            return {"success": True, "перечисление_id": enum_value.id}
        return {"success": False, "message": f"Неизвестный тип параметра: {param.тип_параметра}"}

    def add_ho_item(self, db: Session, операция_id: int, изделие_id: int, количество: float, цена: float) -> Dict[str, Any]:
        """Добавить товарную позицию в ХО (автоматически пересчитать сумму операции)"""
        # Проверка корректности количества
        if количество <= 0:
            return {"success": False, "message": "Количество должно быть положительным числом"}
        
        # Проверка корректности цены
        if цена < 0:
            return {"success": False, "message": "Цена не может быть отрицательной"}
        
        # Проверка существования операции
        operation = db.query(HOOperation).filter(HOOperation.id == операция_id).first()
        if not operation:
            return {"success": False, "message": f"Операция с id {операция_id} не найдена"}
        
        # Проверка существования изделия
        product = db.query(Product).filter(Product.id == изделие_id).first()
        if not product:
            return {"success": False, "message": f"Изделие с id {изделие_id} не найдено"}
        
        try:
            сумма = количество * цена
            item = HOItem(операция_id=операция_id, изделие_id=изделие_id,
                        количество=количество, цена=цена, сумма=сумма)
            db.add(item)
            total = db.query(func.sum(HOItem.сумма)).filter(HOItem.операция_id == операция_id).scalar() or 0
            db.query(HOOperation).filter(HOOperation.id == операция_id).update({"сумма": total})
            db.commit()
            return {"success": True, "message": "Позиция добавлена", "item_id": item.id, "сумма_операции": total}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_ho_operation_full(self, db: Session, операция_id: int) -> Dict[str, Any]:
        """Получить полную информацию о ХО: данные, параметры с значениями, роли с субъектами, позиции"""
        op = db.query(HOOperation).filter(HOOperation.id == операция_id).first()
        if not op:
            return {}

        # Основные данные
        result = {
            "id": op.id,
            "тип_хо_id": op.тип_хо_id,
            "тип_название": op.ho_type.название if op.ho_type else None,
            "номер_документа": op.номер_документа,
            "дата": op.дата.isoformat(),
            "сумма": op.сумма,
            "роли": [],
            "параметры": [],
            "позиции": []
        }

        # Роли
        for ra in op.role_assignments:
            role_name = ra.role.название if ra.role else None
            subject_name = ra.subject.наименование if ra.subject else None
            result["роли"].append({
                "роль": role_name,
                "субъект": subject_name,
                "субъект_id": ra.субъект_хо_id
            })

        # Параметры
        for pv in op.parameter_values:
            hp = pv.ho_parameter
            param = hp.parameter if hp else None
            value_display = None
            if pv.значение_число is not None:
                value_display = pv.значение_число
            elif pv.значение_строка is not None:
                value_display = pv.значение_строка
            elif pv.значение_дата is not None:
                value_display = pv.значение_дата.isoformat()
            elif pv.значение_перечисление_id is not None:
                ev = pv.enum_value
                value_display = ev.value if ev else None
            result["параметры"].append({
                "обозначение": param.обозначение if param else None,
                "полное_имя": param.полное_имя if param else None,
                "тип": param.тип_параметра if param else None,
                "значение": value_display
            })

        # Позиции
        for item in op.items:
            prod = item.product
            result["позиции"].append({
                "изделие": prod.наименование if prod else None,
                "количество": item.количество,
                "цена": item.цена,
                "сумма": item.сумма
            })

        return result

    def filter_ho_operations(self, db: Session, тип_хо_id: int = None,
                                дата_от: datetime = None, дата_до: datetime = None,
                                сумма_мин: float = None, сумма_макс: float = None) -> List[Dict[str, Any]]:
        """Фильтрация ХО по типу, дате, сумме"""
        query = db.query(HOOperation)
        if тип_хо_id:
            query = query.filter(HOOperation.тип_хо_id == тип_хо_id)
        if дата_от:
            query = query.filter(HOOperation.дата >= дата_от)
        if дата_до:
            query = query.filter(HOOperation.дата <= дата_до)
        if сумма_мин is not None:
            query = query.filter(HOOperation.сумма >= сумма_мин)
        if сумма_макс is not None:
            query = query.filter(HOOperation.сумма <= сумма_макс)
        ops = query.all()
        return [{
            "id": o.id,
            "номер_документа": o.номер_документа,
            "дата": o.дата.isoformat(),
            "сумма": o.сумма,
            "тип_хо_id": o.тип_хо_id,
            "тип_название": o.ho_type.название if o.ho_type else None
        } for o in ops]
        
    def clear_database(self, db: Session):
        """Полная очистка БД с перезапуском последовательностей (сброс ID)"""

        # Получаем список всех таблиц в правильном порядке (сначала зависимые)
        tables = [
            # Задание 1.4 (ХО) - самые зависимые
            "позиция_хо",                 # зависит от хозяйственная_операция, изделие
            "значение_параметра_хо",      # зависит от хозяйственная_операция, параметр_хо
            "роль_в_хо",                  # зависит от хозяйственная_операция, роль_хо, субъект_хоз_деятельности
            "хозяйственная_операция",     # зависит от классификатор_хо
            "параметр_хо",                # зависит от классификатор_хо, параметр
            "роль_хо",                    # зависит от классификатор_хо
            "классификатор_хо",           # корневая для ХО
            "субъект_хоз_деятельности",   # независимая
            
            # Задание 1.3
            "значение_параметра",         # зависит от параметр_класса, изделие
            "изделие",                    # зависит от классификатор
            "параметр_класса",            # зависит от классификатор, параметр
            "параметр",                   # независимая
            
            # Задание 1.2
            "значение_перечисления",      # зависит от перечисление
            "перечисление",               # независимая
            
            # Задание 1.1
            "фигурки_в_наборе",           # зависит от набор, мини_фигурка
            "состав_набора",              # зависит от набор, деталь
            "мини_фигурка",               # зависит от классификатор
            "деталь",                     # зависит от классификатор
            "набор",                      # зависит от классификатор
            "тип_детали",                 # зависит от классификатор
            "возрастная_категория",       # зависит от классификатор
            "тематика",                   # зависит от классификатор
            "классификатор",              # корневая
        ]

        # Очищаем таблицы
        for table in tables:
            try:
                db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            except Exception as e:
                print(f"  Предупреждение: не удалось очистить таблицу {table}: {e}")

        # Сбрасываем последовательности (счётчики ID)
        sequences = [
            # Задание 1.4
            "классификатор_хо_id_seq",
            "роль_хо_id_seq",
            "параметр_хо_id_seq",
            "субъект_хоз_деятельности_id_seq",
            "хозяйственная_операция_id_seq",
            "роль_в_хо_id_seq",
            "значение_параметра_хо_id_seq",
            "позиция_хо_id_seq",
            # Задание 1.3
            "параметр_id_seq",
            "параметр_класса_id_seq",
            "изделие_id_seq",
            "значение_параметра_id_seq",
            # Задание 1.2
            "перечисление_id_seq",
            "значение_перечисления_id_seq",
            # Задание 1.1
            "классификатор_id_seq",
            "тематика_id_seq",
            "возрастная_категория_id_seq",
            "тип_детали_id_seq",
            "набор_id_seq",
            "деталь_id_seq",
            "мини_фигурка_id_seq",
        ]

        for seq in sequences:
            try:
                db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
            except Exception:
                pass  # последовательность может не существовать

        db.commit()
        print("База данных очищена, последовательности сброшены")
    
    def load_test_data(self, db: Session) -> Dict[str, Any]:
        """Загрузка тестовых данных"""
        self.clear_database(db)
        
        # 1. Тематика
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
            self.add_theme(db, name, desc)
        
        # 2. Возрастные категории
        age_data = [
            ("2-4 лет", 2, 4),
            ("4-6 лет", 4, 6),
            ("6-13 лет", 6, 13),
            ("14-18 лет", 14, 18),
            ("18+ лет", 18, 99)
        ]
        for name, min_age, max_age in age_data:
            self.add_age_category(db, name, min_age, max_age)
        
        # 3. Корневой элемент
        root_result = self.add_node(db, "Изделия бренда LEGO", "промежуточный", None, sort_order=1)
        root_id = root_result["node_id"]
        
        # 4. Основные категории
        sets_result = self.add_node(db, "Наборы", "промежуточный", root_id, sort_order=1)
        parts_result = self.add_node(db, "Детали", "промежуточный", root_id, sort_order=2)
        minifigs_result = self.add_node(db, "Мини-фигурки", "промежуточный", root_id, sort_order=3)
        
        sets_id = sets_result["node_id"]
        parts_id = parts_result["node_id"]

        #  добавили
        minifigs_id = minifigs_result["node_id"]
        # конец добавления
        
        # 5. Подкатегории наборов
        self.add_node(db, "Тематика City", "промежуточный", sets_id, sort_order=1)
        self.add_node(db, "Тематика Star Wars", "промежуточный", sets_id, sort_order=2)
        self.add_node(db, "Тематика Technic", "промежуточный", sets_id, sort_order=3)
        
        # 6. Подкатегории деталей
        bricks_id = self.add_node(db, "Кирпичи", "промежуточный", parts_id, sort_order=1)["node_id"]
        plates_id = self.add_node(db, "Плиты", "промежуточный", parts_id, sort_order=2)["node_id"]
        self.add_node(db, "Технические детали", "промежуточный", parts_id, sort_order=3)
        special_id = self.add_node(db, "Специальные детали", "промежуточный", parts_id, sort_order=4)["node_id"]
        
        # 7. Терминальные узлы деталей
        brick_2x4_id = self.add_node(db, "Кирпич 2x4", "терминальный", bricks_id, sort_order=1)["node_id"]
        brick_2x2_id = self.add_node(db, "Кирпич 2x2", "терминальный", bricks_id, sort_order=2)["node_id"]
        plate_1x2_id = self.add_node(db, "Плита 1x2", "терминальный", plates_id, sort_order=1)["node_id"]
        self.add_node(db, "Плита 2x4", "терминальный", plates_id, sort_order=2)
        wheel_id = self.add_node(db, "Колесо", "терминальный", special_id, sort_order=1)["node_id"]

        #  добавили
        
        # Терминальный узел (класс) для мини-фигурок
        mf_class_result = self.add_node(db, "Мини-фигурка", "терминальный", minifigs_id, sort_order=1)
        if mf_class_result["success"]:
            minifigure_class_id = mf_class_result["node_id"]
        else:
            # если узел уже существует (например, после повторной загрузки данных)
            existing = db.query(Classificator).filter(Classificator.название == "Мини-фигурка", Classificator.родительский_id == minifigs_id).first()
            minifigure_class_id = existing.id if existing else None

        # конец добавления


        # 8. Типы деталей
        brick_type = self.add_part_type(db, "Кирпич", 1)
        plate_type = self.add_part_type(db, "Плита", 1)
        self.add_part_type(db, "Техническая", 1)
        special_type = self.add_part_type(db, "Специальная", 1)
        
        brick_type_id = brick_type["product_id"]
        plate_type_id = plate_type["product_id"]
        special_type_id = special_type["product_id"]
        
        # 9. Получение ID справочников
        star_wars_theme = db.query(Theme).join(Classificator).filter(Classificator.название == "Star Wars").first()
        city_theme = db.query(Theme).join(Classificator).filter(Classificator.название == "City").first()
        technic_theme = db.query(Theme).join(Classificator).filter(Classificator.название == "Technic").first()
        
        age_14 = db.query(AgeCategory).filter(AgeCategory.минимальный_возраст == 14).first()
        age_6 = db.query(AgeCategory).filter(AgeCategory.минимальный_возраст == 6).first()

        # ========== ПЕРЕЧИСЛЕНИЯ ==========
        print("  Добавляем тестовые перечисления...")
        enum_part_type = self.add_enumeration(db, "Тип детали", "Типы деталей LEGO")
        if enum_part_type["success"]:
            enum_id = enum_part_type["enum_id"]
            self.add_enum_value(db, enum_id, "Кирпич", 1)
            self.add_enum_value(db, enum_id, "Плита", 2)
            self.add_enum_value(db, enum_id, "Техническая", 3)
            self.add_enum_value(db, enum_id, "Специальная", 4)

        enum_color_result = self.add_enumeration(db, "Цвет", "Цвета изделий LEGO")
        color_values = {}
        if enum_color_result["success"]:
            enum_color_id = enum_color_result["enum_id"]
            for order, value in enumerate(["Красный", "Синий", "Зелёный", "Белый", "Чёрный", "Жёлтый", "Серый"], start=1):
                created = self.add_enum_value(db, enum_color_id, value, order)
                if created["success"]:
                    color_values[value] = created["value_id"]
        else:
            enum_color_id = None

        enum_rarity = self.add_enumeration(db, "Редкость", "Редкость мини-фигурок")
        if enum_rarity["success"]:
            enum_rarity_id = enum_rarity["enum_id"]          # ← было: enum_id
            self.add_enum_value(db, enum_rarity_id, "Common", 1)
            self.add_enum_value(db, enum_rarity_id, "Rare", 2)
            self.add_enum_value(db, enum_rarity_id, "Exclusive", 3)
        else:
            # если уже было
            existing_enum = db.query(Enumeration).filter(Enumeration.name == "Редкость").first()
            enum_rarity_id = existing_enum.id if existing_enum else None
        db.commit()
        print("  Тестовые перечисления добавлены")

        # ========== ПАРАМЕТРЫ И СПРАВОЧНИК ИЗДЕЛИЙ (ЗАДАНИЕ 1.3) ==========
        print("  Создаём параметры и изделия...")
        params = {}
        for code, full_name, param_type, unit, enum_id in [
            ("вес", "Вес изделия", "REAL", "г", None),
            ("длина", "Длина изделия", "REAL", "мм", None),
            ("ширина", "Ширина изделия", "REAL", "мм", None),
            ("высота", "Высота изделия", "REAL", "мм", None),
            ("цвет", "Цвет изделия", "ENUM", None, enum_color_id),
            ("материал", "Материал изделия", "STRING", None, None),
            ("дата_ввода", "Дата ввода в каталог", "DATETIME", None, None),
        ]:
            result = self.add_parameter(db, code, full_name, param_type, unit, enum_id)
            if result["success"]:
                params[code] = result["param_id"]

        class_specs = {
            brick_2x4_id: {
                "params": [("вес", 0, 20, "3.0"), ("длина", 0, 100, "31.8"), ("ширина", 0, 100, "15.8"), ("высота", 0, 100, "9.6"), ("цвет", None, None, None), ("материал", None, None, "ABS-пластик")],
                "products": [
                    ("Кирпич 2x4", "BR-2X4-RED", {"вес": 3.5, "длина": 31.8, "ширина": 15.8, "высота": 9.6, "цвет": "Красный", "материал": "ABS-пластик"}),
                    ("Кирпич 2x4", "BR-2X4-BLU", {"вес": 2.5, "длина": 31.8, "ширина": 15.8, "высота": 9.6, "цвет": "Синий", "материал": "ABS-пластик"}),
                    ("Кирпич 2x4", "BR-2X4-YEL", {"вес": 3.1, "длина": 31.8, "ширина": 15.8, "высота": 9.6, "цвет": "Жёлтый", "материал": "ABS-пластик"}),
                ],
            },
            brick_2x2_id: {
                "params": [("вес", 0, 20, "1.5"), ("длина", 0, 100, "15.8"), ("ширина", 0, 100, "15.8"), ("высота", 0, 100, "9.6"), ("цвет", None, None, None), ("материал", None, None, "ABS-пластик")],
                "products": [
                    ("Кирпич 2x2", "BR-2X2-GRN", {"вес": 1.2, "длина": 15.8, "ширина": 15.8, "высота": 9.6, "цвет": "Зелёный", "материал": "ABS-пластик"}),
                    ("Кирпич 2x2", "BR-2X2-BLK", {"вес": 1.4, "длина": 15.8, "ширина": 15.8, "высота": 9.6, "цвет": "Чёрный", "материал": "ABS-пластик"}),
                ],
            },
            plate_1x2_id: {
                "params": [("вес", 0, 10, "0.8"), ("длина", 0, 100, "15.8"), ("ширина", 0, 100, "7.8"), ("высота", 0, 100, "3.2"), ("цвет", None, None, None), ("материал", None, None, "ABS-пластик")],
                "products": [
                    ("Плита 1x2", "PL-1X2-WHT", {"вес": 0.8, "длина": 15.8, "ширина": 7.8, "высота": 3.2, "цвет": "Белый", "материал": "ABS-пластик"}),
                    ("Плита 1x2", "PL-1X2-GRY", {"вес": 0.9, "длина": 15.8, "ширина": 7.8, "высота": 3.2, "цвет": "Серый", "материал": "ABS-пластик"}),
                ],
            },
            wheel_id: {
                "params": [("вес", 0, 50, "5.0"), ("диаметр", 0, 100, "30"), ("ширина", 0, 100, "14"), ("цвет", None, None, None), ("материал", None, None, "Резина")],
                "products": [
                    ("Колесо", "WH-30-BLK", {"вес": 5.0, "диаметр": 30, "ширина": 14, "цвет": "Чёрный", "материал": "Резина"}),
                    ("Колесо", "WH-30-GRY", {"вес": 4.8, "диаметр": 30, "ширина": 14, "цвет": "Серый", "материал": "Резина"}),
                ],
            },
        }
        if "диаметр" not in params:
            result = self.add_parameter(db, "диаметр", "Диаметр изделия", "REAL", "мм")
            if result["success"]:
                params["диаметр"] = result["param_id"]

        product_ids = {}
        for class_id, spec in class_specs.items():
            for code, min_value, max_value, default_value in spec["params"]:
                if code in params:
                    self.add_param_to_class(db, class_id, params[code], min_value, max_value, default_value, обязательный=(code in {"вес", "цвет"}))
            param_class_map = {cp["обозначение"]: cp["param_class_id"] for cp in self.get_class_parameters(db, class_id, include_inherited=False)}
            for name, sku, values in spec["products"]:
                product = self.add_product(db, class_id, name, sku)
                if not product["success"] or not product["product_id"]:
                    continue
                product_ids[sku] = product["product_id"]
                for code, value in values.items():
                    if code not in param_class_map:
                        continue
                    if code == "цвет":
                        value = color_values.get(value)
                    if value is not None:
                        self.set_product_param_value(db, product["product_id"], param_class_map[code], value)
                        # minifigure_products[sku] = prod_res["product_id"]
        # Параметр "редкость" для мини-фигурок
        if enum_rarity_id:
            rarity_param = self.add_parameter(db, "редкость", "Редкость мини-фигурки", "ENUM", перечисление_id=enum_rarity_id)
            if rarity_param["success"] and minifigure_class_id:
                self.add_param_to_class(db, minifigure_class_id, rarity_param["param_id"], обязательный=True)

        db.commit()
        print("  Параметры и изделия добавлены")
        
        # 10. Добавление наборов
        self.add_set(db, "Звезда Смерти", "75159", 2020, 499.99, 4016, age_14.id, star_wars_theme.id, sets_id)
        self.add_set(db, "Космический корабль", "75257", 2019, 159.99, 1351, age_6.id, star_wars_theme.id, sets_id)
        self.add_set(db, "Полицейский участок", "60266", 2020, 129.99, 745, age_6.id, city_theme.id, sets_id)
        self.add_set(db, "Внедорожник", "42110", 2019, 199.99, 2573, age_14.id, technic_theme.id, sets_id)
        
                # 11. Добавление типов деталей без жёстких характеристик
        self.add_part(db, "Кирпич 2x4", brick_type_id)
        self.add_part(db, "Кирпич 2x2", brick_type_id)
        self.add_part(db, "Плита 1x2", plate_type_id)
        self.add_part(db, "Колесо", special_type_id)
        
                # 12. Добавление мини-фигурок
        minifigure_products = {}
        if minifigure_class_id:
            # Найдём param_class_id для параметра "редкость"
            param_class = db.query(ParameterClass).join(Parameter).filter(
                ParameterClass.класс_id == minifigure_class_id,
                Parameter.обозначение == "редкость"
            ).first()
            
            mf_data = [
                ("Люк Скайуокер", "MF-SW001", "Rare"),
                ("Дарт Вейдер", "MF-SW002", "Exclusive"),
                ("Полицейский", "MF-CT001", "Common"),
            ]
            for name, sku, rarity in mf_data:
                prod_res = self.add_product(db, minifigure_class_id, name, sku)
                if prod_res["success"] and prod_res["product_id"] and param_class and enum_rarity_id:
                    rarity_val = db.query(EnumValue).filter(
                        EnumValue.enumeration_id == enum_rarity_id,
                        EnumValue.value == rarity
                    ).first()
                    if rarity_val:
                        self.set_product_param_value(db, prod_res["product_id"], param_class.id, rarity_val.id)
                        # ДОБАВЬТЕ ЭТУ СТРОКУ:
                        minifigure_products[sku] = prod_res["product_id"]
        
        # 13. Добавление связей набор-деталь и мини-фигурка
        death_star = db.query(Set).join(Classificator).filter(Classificator.название == "Звезда Смерти").first()
        spaceship = db.query(Set).join(Classificator).filter(Classificator.название == "Космический корабль").first()
        
        # Связи для Звезды Смерти (детали)
        db.add(SetPart(id_набора=death_star.id, id_детали=product_ids["BR-2X4-RED"], количество_штук=50))
        db.add(SetPart(id_набора=death_star.id, id_детали=product_ids["BR-2X4-BLU"], количество_штук=30))
        db.add(SetPart(id_набора=death_star.id, id_детали=product_ids["BR-2X2-GRN"], количество_штук=40))
        db.add(SetPart(id_набора=death_star.id, id_детали=product_ids["PL-1X2-WHT"], количество_штук=100))
        
        # Мини-фигурки в Звезду Смерти
        luke_product_id = minifigure_products.get("MF-SW001")
        vader_product_id = minifigure_products.get("MF-SW002")
        if luke_product_id:
            db.add(SetPart(id_набора=death_star.id, id_детали=luke_product_id, количество_штук=2))
        if vader_product_id:
            db.add(SetPart(id_набора=death_star.id, id_детали=vader_product_id, количество_штук=1))
        
        # Связи для Космического корабля (детали)
        db.add(SetPart(id_набора=spaceship.id, id_детали=product_ids["BR-2X4-YEL"], количество_штук=20))
        db.add(SetPart(id_набора=spaceship.id, id_детали=product_ids["BR-2X2-GRN"], количество_штук=15))
        db.add(SetPart(id_набора=spaceship.id, id_детали=product_ids["WH-30-BLK"], количество_штук=4))
        
        # Мини-фигурка в Космический корабль
        if luke_product_id:
            db.add(SetPart(id_набора=spaceship.id, id_детали=luke_product_id, количество_штук=1))
        
        db.commit()

        # ========== ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ (ЗАДАНИЕ 1.4) ==========
        print("  Добавляем тестовые данные для ХО...")

        # 1. Типы ХО
        # Тип "Отгрузка" (корневой)
        otgruzka = self.add_ho_type(db, "Отгрузка")
        if otgruzka["success"]:
            otgruzka_id = otgruzka["type_id"]
            # Роли для отгрузки
            self.add_role_to_ho_type(db, otgruzka_id, "Отправитель")
            self.add_role_to_ho_type(db, otgruzka_id, "Получатель")
            self.add_role_to_ho_type(db, otgruzka_id, "Плательщик")

        # Тип "Поступление" (корневой)
        postuplenie = self.add_ho_type(db, "Поступление")
        if postuplenie["success"]:
            postuplenie_id = postuplenie["type_id"]
            self.add_role_to_ho_type(db, postuplenie_id, "Поставщик")
            self.add_role_to_ho_type(db, postuplenie_id, "Получатель")

        # 2. Субъекты (контрагенты)
        self.add_subject(db, "ООО 'Поставщик'", инн="1234567890", контактное_лицо="Иванов И.И.", телефон="+7(123)456-78-90")
        self.add_subject(db, "Склад №1")
        self.add_subject(db, "ООО 'Покупатель'", инн="0987654321", контактное_лицо="Петров П.П.", телефон="+7(123)456-78-91")
        self.add_subject(db, "Транспортная компания", инн="1122334455")

        # Получаем ID созданных субъектов для использования в операциях
        subjects = {s["наименование"]: s["id"] for s in self.get_all_subjects(db)}

        # 3. Создаём экземпляры операций
        # Операция отгрузки
        if otgruzka["success"]:
            op1 = self.create_ho_operation(db, otgruzka_id, "ТТН-001", datetime(2025, 5, 15))
            if op1["success"]:
                op_id = op1["operation_id"]
                # Назначаем участников на роли
                roles = self.get_roles_of_ho_type(db, otgruzka_id)
                role_map = {r["название"]: r["id"] for r in roles}
                if "Отправитель" in role_map and "ООО 'Поставщик'" in subjects:
                    self.assign_actor_to_role(db, op_id, role_map["Отправитель"], subjects["ООО 'Поставщик'"])
                if "Получатель" in role_map and "Склад №1" in subjects:
                    self.assign_actor_to_role(db, op_id, role_map["Получатель"], subjects["Склад №1"])
                if "Плательщик" in role_map and "ООО 'Покупатель'" in subjects:
                    self.assign_actor_to_role(db, op_id, role_map["Плательщик"], subjects["ООО 'Покупатель'"])

                # Добавляем позиции (товары)
                # Получаем существующие изделия (кирпичи)
                brick_red = db.query(Product).filter(Product.артикул == "BR-2X4-RED").first()
                brick_blue = db.query(Product).filter(Product.артикул == "BR-2X4-BLU").first()
                if brick_red:
                    self.add_ho_item(db, op_id, brick_red.id, 100, 50.0)
                if brick_blue:
                    self.add_ho_item(db, op_id, brick_blue.id, 50, 55.0)

        # Операция поступления
        if postuplenie["success"]:
            op2 = self.create_ho_operation(db, postuplenie_id, "ПО-001", datetime(2025, 5, 16))
            if op2["success"]:
                op_id = op2["operation_id"]
                roles = self.get_roles_of_ho_type(db, postuplenie_id)
                role_map = {r["название"]: r["id"] for r in roles}
                if "Поставщик" in role_map and "ООО 'Поставщик'" in subjects:
                    self.assign_actor_to_role(db, op_id, role_map["Поставщик"], subjects["ООО 'Поставщик'"])
                if "Получатель" in role_map and "Склад №1" in subjects:
                    self.assign_actor_to_role(db, op_id, role_map["Получатель"], subjects["Склад №1"])

                # Добавляем позицию
                brick_red = db.query(Product).filter(Product.артикул == "BR-2X4-RED").first()
                if brick_red:
                    self.add_ho_item(db, op_id, brick_red.id, 200, 48.0)

        db.commit()
        print("  Тестовые данные для ХО добавлены")
        
        return {"success": True, "message": "Тестовые данные успешно загружены"}
    

        # ========== ПАРАМЕТРЫ (ЗАДАНИЕ 1.3) ==========

    # ----- Управление параметрами -----
    
    def add_parameter(self, db: Session, обозначение: str, полное_имя: str,
                      тип_параметра: str, единица_измерения: str = None,
                      перечисление_id: int = None) -> Dict[str, Any]:
        """Создать новый параметр"""
        # Проверка типа
        valid_types = ['REAL', 'INTEGER', 'STRING', 'DATETIME', 'ENUM']
        if тип_параметра not in valid_types:
            return {"success": False, "message": f"Недопустимый тип. Допустимы: {valid_types}"}
        
        # Для ENUM обязательно указать перечисление
        if тип_параметра == 'ENUM' and not перечисление_id:
            return {"success": False, "message": "Для типа ENUM необходимо указать перечисление_id"}
        
        # Проверка уникальности
        exists = db.query(Parameter).filter(Parameter.обозначение == обозначение).first()
        if exists:
            return {"success": False, "message": f"Параметр с обозначением '{обозначение}' уже существует"}
        
        try:
            new_param = Parameter(
                обозначение=обозначение,
                полное_имя=полное_имя,
                единица_измерения=единица_измерения,
                тип_параметра=тип_параметра,
                перечисление_id=перечисление_id
            )
            db.add(new_param)
            db.commit()
            db.refresh(new_param)
            return {"success": True, "message": "Параметр создан", "param_id": new_param.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_all_parameters(self, db: Session) -> List[Dict[str, Any]]:
        """Получить все параметры"""
        params = db.query(Parameter).all()
        result = []
        for p in params:
            result.append({
                "id": p.id,
                "обозначение": p.обозначение,
                "полное_имя": p.полное_имя,
                "единица_измерения": p.единица_измерения,
                "тип_параметра": p.тип_параметра,
                "перечисление_id": p.перечисление_id
            })
        return result

    # ----- Привязка параметров к классам -----

    def add_param_to_class(self, db: Session, класс_id: int, параметр_id: int,
                           мин_значение: float = None, макс_значение: float = None,
                           значение_по_умолчанию: str = None, обязательный: bool = False) -> Dict[str, Any]:
        """Привязать параметр к классу изделий"""
        # Проверка существования класса
        class_node = db.query(Classificator).filter(Classificator.id == класс_id).first()
        if not class_node:
            return {"success": False, "message": "Класс не найден"}
        
        # Проверка существования параметра
        param = db.query(Parameter).filter(Parameter.id == параметр_id).first()
        if not param:
            return {"success": False, "message": "Параметр не найден"}
        
        # Проверка дублирования
        exists = db.query(ParameterClass).filter(
            ParameterClass.класс_id == класс_id,
            ParameterClass.параметр_id == параметр_id
        ).first()
        if exists:
            return {"success": False, "message": "Параметр уже привязан к этому классу"}
        
        # Валидация ограничений
        if param.тип_параметра not in ('REAL', 'INTEGER') and (мин_значение is not None or макс_значение is not None):
            return {"success": False, "message": "Ограничения (мин/макс) можно задавать только для численных параметров"}
        
        if мин_значение is not None and макс_значение is not None and мин_значение >= макс_значение:
            return {"success": False, "message": "Минимальное значение должно быть меньше максимального"}
        
        # Определяем порядковый номер
        max_order = db.query(func.coalesce(func.max(ParameterClass.порядковый_номер), 0)).filter(
            ParameterClass.класс_id == класс_id
        ).scalar()
        
        try:
            new_pc = ParameterClass(
                класс_id=класс_id,
                параметр_id=параметр_id,
                порядковый_номер=max_order + 1,
                мин_значение=мин_значение,
                макс_значение=макс_значение,
                значение_по_умолчанию=значение_по_умолчанию,
                обязательный=1 if обязательный else 0
            )
            db.add(new_pc)
            db.commit()
            db.refresh(new_pc)
            return {"success": True, "message": "Параметр привязан к классу", "param_class_id": new_pc.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_class_parameters(self, db: Session, класс_id: int, include_inherited: bool = True) -> List[Dict[str, Any]]:
        """Получить все параметры класса (с учётом наследования, если нужно)"""
        result = []
        class_ids = [класс_id]
        
        if include_inherited:
            # Получаем всех предков
            ancestors = self.get_ancestors(db, класс_id)
            class_ids.extend([a["id"] for a in ancestors])
        
        # Получаем все ParameterClass для этих классов
        param_classes = db.query(ParameterClass).filter(ParameterClass.класс_id.in_(class_ids)).all()
        
        for pc in param_classes:
            param = db.query(Parameter).filter(Parameter.id == pc.параметр_id).first()
            result.append({
                "param_class_id": pc.id,
                "параметр_id": param.id,
                "обозначение": param.обозначение,
                "полное_имя": param.полное_имя,
                "тип_параметра": param.тип_параметра,
                "единица_измерения": param.единица_измерения,
                "перечисление_id": param.перечисление_id,
                "мин_значение": pc.мин_значение,
                "макс_значение": pc.макс_значение,
                "значение_по_умолчанию": pc.значение_по_умолчанию,
                "обязательный": pc.обязательный,
                "порядковый_номер": pc.порядковый_номер,
                "класс_источник": pc.класс_id
            })
        
        # Сортируем по порядковому номеру
        result.sort(key=lambda x: x["порядковый_номер"])
        return result

    # ----- Управление изделиями -----

    def add_product(self, db: Session, класс_id: int, наименование: str, артикул: str = None) -> Dict[str, Any]:
        """Создать новое изделие"""
        # Проверка существования класса
        class_node = db.query(Classificator).filter(Classificator.id == класс_id).first()
        if not class_node:
            return {"success": False, "message": "Класс не найден"}
        
        # Проверка уникальности артикула
        if артикул:
            exists = db.query(Product).filter(Product.артикул == артикул).first()
            if exists:
                return {"success": False, "message": f"Изделие с артикулом '{артикул}' уже существует"}
        
        try:
            new_product = Product(
                класс_id=класс_id,
                наименование=наименование,
                артикул=артикул
            )
            db.add(new_product)
            db.commit()
            db.refresh(new_product)
            return {"success": True, "message": "Изделие создано", "product_id": new_product.id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_all_products(self, db: Session) -> List[Dict[str, Any]]:
        """Получить все изделия"""
        products = db.query(Product).all()
        result = []
        for p in products:
            class_node = db.query(Classificator).filter(Classificator.id == p.класс_id).first()
            result.append({
                "id": p.id,
                "наименование": p.наименование,
                "артикул": p.артикул,
                "класс_id": p.класс_id,
                "класс_название": class_node.название if class_node else None,
                "created_at": p.created_at
            })
        return result

    # ----- Работа со значениями параметров -----

    def _validate_param_value(self, db: Session, param: Parameter, param_class: ParameterClass, value: Any) -> Dict:
        """Валидация значения параметра (внутренний метод)"""
        if param.тип_параметра == 'REAL':
            try:
                num_val = float(value)
            except (ValueError, TypeError):
                return {"success": False, "message": f"Значение '{value}' не является числом"}
            if param_class.мин_значение is not None and num_val < param_class.мин_значение:
                return {"success": False, "message": f"Значение {num_val} меньше минимального {param_class.мин_значение}"}
            if param_class.макс_значение is not None and num_val > param_class.макс_значение:
                return {"success": False, "message": f"Значение {num_val} больше максимального {param_class.макс_значение}"}
            return {"success": True, "число": num_val}
        
        elif param.тип_параметра == 'INTEGER':
            try:
                int_val = int(value)
            except (ValueError, TypeError):
                return {"success": False, "message": f"Значение '{value}' не является целым числом"}
            if param_class.мин_значение is not None and int_val < param_class.мин_значение:
                return {"success": False, "message": f"Значение {int_val} меньше минимального {param_class.мин_значение}"}
            if param_class.макс_значение is not None and int_val > param_class.макс_значение:
                return {"success": False, "message": f"Значение {int_val} больше максимального {param_class.макс_значение}"}
            return {"success": True, "число": int_val}
        
        elif param.тип_параметра == 'STRING':
            return {"success": True, "строка": str(value)}
        
        elif param.тип_параметра == 'DATETIME':
            try:
                if isinstance(value, datetime):
                    dt_val = value
                else:
                    dt_val = datetime.fromisoformat(str(value))
            except:
                return {"success": False, "message": f"Значение '{value}' не является датой"}
            return {"success": True, "дата": dt_val}
        
        elif param.тип_параметра == 'ENUM':
            if not param.перечисление_id:
                return {"success": False, "message": "Для параметра-перечисления не указано перечисление"}
            enum_value = db.query(EnumValue).filter(
                EnumValue.id == value,
                EnumValue.enumeration_id == param.перечисление_id
            ).first()
            if not enum_value:
                return {"success": False, "message": f"Значение с ID {value} не найдено в перечислении"}
            return {"success": True, "перечисление_id": enum_value.id}
        
        return {"success": False, "message": f"Неизвестный тип параметра: {param.тип_параметра}"}

    def set_product_param_value(self, db: Session, product_id: int, param_class_id: int, value: Any) -> Dict[str, Any]:
        """Установить значение параметра для изделия"""
        # Проверка существования изделия
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"success": False, "message": "Изделие не найдено"}
        
        # Получаем информацию о привязке параметра
        param_class = db.query(ParameterClass).filter(ParameterClass.id == param_class_id).first()
        if not param_class:
            return {"success": False, "message": "Привязка параметра к классу не найдена"}
        
        param = db.query(Parameter).filter(Parameter.id == param_class.параметр_id).first()
        
        # Проверка, что класс изделия соответствует или наследует класс параметра
        if product.класс_id != param_class.класс_id:
            ancestors = self.get_ancestors(db, product.класс_id)
            ancestor_ids = [a["id"] for a in ancestors]
            if param_class.класс_id not in ancestor_ids:
                return {"success": False, "message": "Параметр не принадлежит классу изделия или его предкам"}
        
        # Валидация значения
        validated = self._validate_param_value(db, param, param_class, value)
        if not validated["success"]:
            return validated
        
        # Сохраняем или обновляем значение
        existing = db.query(ParameterValue).filter(
            ParameterValue.изделие_id == product_id,
            ParameterValue.параметр_класса_id == param_class_id
        ).first()
        
        try:
            if existing:
                existing.значение_число = validated.get("число")
                existing.значение_строка = validated.get("строка")
                existing.значение_дата = validated.get("дата")
                existing.значение_перечисление_id = validated.get("перечисление_id")
            else:
                new_val = ParameterValue(
                    изделие_id=product_id,
                    параметр_класса_id=param_class_id,
                    значение_число=validated.get("число"),
                    значение_строка=validated.get("строка"),
                    значение_дата=validated.get("дата"),
                    значение_перечисление_id=validated.get("перечисление_id")
                )
                db.add(new_val)
            db.commit()
            return {"success": True, "message": "Значение сохранено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def delete_product_param_value(self, db: Session, product_id: int, param_class_id: int) -> Dict[str, Any]:
        """Удалить значение параметра у изделия (отвязать)."""
        existing = db.query(ParameterValue).filter(
            ParameterValue.изделие_id == product_id,
            ParameterValue.параметр_класса_id == param_class_id
        ).first()
        if not existing:
            return {"success": True, "message": "Значение не было задано"}
        try:
            db.delete(existing)
            db.commit()
            return {"success": True, "message": "Значение параметра удалено"}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_product_params_with_values(self, db: Session, product_id: int) -> List[Dict[str, Any]]:
        """Получить все параметры изделия с их значениями"""
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return []
        
        # Получаем все параметры класса (с наследованием)
        class_params = self.get_class_parameters(db, product.класс_id, include_inherited=True)
        
        result = []
        for cp in class_params:
            param_value = db.query(ParameterValue).filter(
                ParameterValue.изделие_id == product_id,
                ParameterValue.параметр_класса_id == cp["param_class_id"]
            ).first()
            
            value_display = None
            if param_value:
                if cp["тип_параметра"] == 'REAL' or cp["тип_параметра"] == 'INTEGER':
                    value_display = param_value.значение_число
                elif cp["тип_параметра"] == 'STRING':
                    value_display = param_value.значение_строка
                elif cp["тип_параметра"] == 'DATETIME':
                    value_display = param_value.значение_дата.isoformat() if param_value.значение_дата else None
                elif cp["тип_параметра"] == 'ENUM':
                    if param_value.значение_перечисление_id:
                        enum_val = db.query(EnumValue).filter(EnumValue.id == param_value.значение_перечисление_id).first()
                        value_display = enum_val.value if enum_val else None
            
            raw_value = None
            if param_value:
                if cp["тип_параметра"] in ('REAL', 'INTEGER'):
                    raw_value = param_value.значение_число
                elif cp["тип_параметра"] == 'STRING':
                    raw_value = param_value.значение_строка
                elif cp["тип_параметра"] == 'DATETIME' and param_value.значение_дата:
                    raw_value = param_value.значение_дата.isoformat()
                elif cp["тип_параметра"] == 'ENUM':
                    raw_value = param_value.значение_перечисление_id

            result.append({
                "param_class_id": cp["param_class_id"],
                "обозначение": cp["обозначение"],
                "полное_имя": cp["полное_имя"],
                "тип_параметра": cp["тип_параметра"],
                "единица_измерения": cp["единица_измерения"],
                "перечисление_id": cp.get("перечисление_id"),
                "значение": value_display,
                "raw_value": raw_value,
                "значение_по_умолчанию": cp["значение_по_умолчанию"],
                "обязательный": cp["обязательный"],
                "мин_значение": cp.get("мин_значение"),
                "макс_значение": cp.get("макс_значение"),
            })
        
        return result
    
    # ----- Фильтрация изделий по параметрам -----

    def filter_products(self, db: Session, class_ids: List[int] = None,
                        param_filters: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Фильтрация изделий по классам и параметрам
        
        param_filters пример:
        [
            {"param_code": "вес", "operator": ">", "value": 10},
            {"param_code": "цвет", "operator": "=", "value": 5},
            {"operator": "between", "min": 100, "max": 200}
        ]
        """
        # Фильтрация по классам (включая потомков)
        all_class_ids = None
        if class_ids:
            all_class_ids = set(class_ids)
            for cid in class_ids:
                descendants = self.get_descendants(db, cid)
                all_class_ids.update([d["id"] for d in descendants])

        matching_ids = None

        def _apply_param_filter(pf: Dict) -> set:
            param = db.query(Parameter).filter(Parameter.обозначение == pf.get("param_code")).first()
            if not param:
                return set()

            param_class_ids = [
                row[0] for row in db.query(ParameterClass.id).filter(
                    ParameterClass.параметр_id == param.id
                ).all()
            ]
            if not param_class_ids:
                return set()

            q = db.query(Product.id).join(
                ParameterValue, ParameterValue.изделие_id == Product.id
            ).filter(ParameterValue.параметр_класса_id.in_(param_class_ids))

            if all_class_ids is not None:
                q = q.filter(Product.класс_id.in_(all_class_ids))

            op = pf.get("operator")
            if op == "=":
                if param.тип_параметра in ('REAL', 'INTEGER'):
                    q = q.filter(ParameterValue.значение_число == pf["value"])
                elif param.тип_параметра == 'STRING':
                    q = q.filter(ParameterValue.значение_строка == pf["value"])
                elif param.тип_параметра == 'ENUM':
                    q = q.filter(ParameterValue.значение_перечисление_id == pf["value"])
            elif op == ">":
                q = q.filter(ParameterValue.значение_число > pf["value"])
            elif op == "<":
                q = q.filter(ParameterValue.значение_число < pf["value"])
            elif op == "between":
                q = q.filter(ParameterValue.значение_число.between(pf["min"], pf["max"]))

            return {row[0] for row in q.distinct().all()}

        for pf in (param_filters or []):
            ids = _apply_param_filter(pf)
            if matching_ids is None:
                matching_ids = ids
            else:
                matching_ids &= ids

        if matching_ids is not None:
            if not matching_ids:
                return []
            query = db.query(Product).filter(Product.id.in_(matching_ids))
        else:
            query = db.query(Product)
            if all_class_ids is not None:
                query = query.filter(Product.класс_id.in_(all_class_ids))

        products = query.all()
        out = []
        for p in products:
            class_node = db.query(Classificator).filter(Classificator.id == p.класс_id).first()
            out.append({
                "id": p.id,
                "наименование": p.наименование,
                "артикул": p.артикул,
                "класс_id": p.класс_id,
                "класс_название": class_node.название if class_node else None,
            })
        return out
    
    # lego_classifier.py - добавить в класс LegoClassifier

    def build_category_tree(self, db: Session, root_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Построение дерева классификатора
        
        Args:
            db: сессия БД
            root_id: ID корневого узла (если None - строим от всех корневых узлов)
        
        Returns:
            Список узлов с вложенными детьми
        """
        # Получаем все категории
        categories = self.get_all_categories(db)
        
        # Создаем словарь для быстрого доступа по ID
        nodes_dict = {}
        for cat in categories:
            nodes_dict[cat["id"]] = {
                "id": cat["id"],
                "name": cat["name"],
                "node_type": cat["node_type"],
                "parent_id": cat["parent_id"],
                "sort_order": cat["sort_order"],
                "children": []
            }
        
        # Строим дерево
        trees = []
        for cat_id, node in nodes_dict.items():
            parent_id = node["parent_id"]
            if parent_id is None:
                # Корневой узел
                if root_id is None or cat_id == root_id:
                    trees.append(node)
            else:
                # Добавляем в детей родителя
                if parent_id in nodes_dict:
                    nodes_dict[parent_id]["children"].append(node)
    
        # Сортируем детей по sort_order
        def sort_children(node):
            node["children"].sort(key=lambda x: x["sort_order"])
            for child in node["children"]:
                sort_children(child)
        
        for tree in trees:
            sort_children(tree)
            
        return trees

    def build_category_tree_with_products(self, db: Session, include_products: bool = True) -> List[Dict[str, Any]]:
        """
        Построение дерева классификатора с включением изделий (наборы, детали, фигурки)
        
        Args:
            db: сессия БД
            include_products: включать ли изделия в дерево
        """
        # Получаем все категории
        categories = self.get_all_categories(db)
        
        # Создаем словарь узлов
        nodes_dict = {}
        for cat in categories:
            nodes_dict[cat["id"]] = {
                "id": cat["id"],
                "name": cat["name"],
                "node_type": cat["node_type"],
                "parent_id": cat["parent_id"],
                "sort_order": cat["sort_order"],
                "children": [],
                "products": []  # будет содержать изделия
            }
        
        # Если нужно включить изделия
        if include_products:
            # Добавляем наборы
            sets = self.get_all_sets(db)
            for s in sets:
                # Находим родительский узел для набора
                set_node = db.query(Classificator).filter(
                    Classificator.название == s["name"]
                ).first()
                if set_node and set_node.родительский_id:
                    parent_id = set_node.родительский_id
                    if parent_id in nodes_dict:
                        nodes_dict[parent_id]["products"].append({
                            "id": s["id"],
                            "name": s["name"],
                            "type": "set",
                            "catalog_number": s["catalog_number"],
                            "price": s["price"]
                        })
            
            # Добавляем детали
            parts = self.get_all_parts(db)
            for p in parts:
                part_node = db.query(Classificator).filter(
                    Classificator.название == p["name"]
                ).first()
                if part_node and part_node.родительский_id:
                    parent_id = part_node.родительский_id
                    if parent_id in nodes_dict:
                        nodes_dict[parent_id]["products"].append({
                            "id": p["id"],
                            "name": p["name"],
                            "type": "part",
                            "part_type": p.get("type_name")
                        })
            
            # Добавляем мини-фигурки (теперь это изделия класса «Мини-фигурка»)
            mf_class = db.query(Classificator).filter(
                Classificator.название == "Мини-фигурка"
            ).first()
            if mf_class and mf_class.родительский_id in nodes_dict:
                mf_products = db.query(Product).filter(
                    Product.класс_id == mf_class.id
                ).all()
                for mf in mf_products:
                    nodes_dict[mf_class.родительский_id]["products"].append({
                        "id": mf.id,
                        "name": mf.наименование,
                        "type": "minifigure",
                    })
        
        # Строим дерево
        trees = []
        for cat_id, node in nodes_dict.items():
            parent_id = node["parent_id"]
            if parent_id is None:
                trees.append(node)
            else:
                if parent_id in nodes_dict:
                    nodes_dict[parent_id]["children"].append(node)
        
        # Сортируем
        def sort_node(node):
            node["children"].sort(key=lambda x: x["sort_order"])
            node["products"].sort(key=lambda x: x["name"])
            for child in node["children"]:
                sort_node(child)
        
        for tree in trees:
            sort_node(tree)
        
        return trees
