# bom_service.py
"""
Задание 5. Сервис ведения материальных спецификаций изделий (Bill of materials).

Управляющий класс BOMService инкапсулирует бизнес-логику:
ведение справочника единиц измерения, формирование и редактирование
спецификаций, управление изменениями, создание модификаций,
поиск полного состава (FIND_BOM) и расчёт сводных норм (CALC_BOM).
Тяжёлые рекурсивные операции выполняются хранимыми функциями PostgreSQL (bom_sql.py).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import BOMItem, Classificator, Product, SpecChange, UnitOfMeasure

PRODUCT_KINDS = ["МАТЕРИАЛ", "КОМПЛЕКТУЮЩЕЕ", "ДЕТАЛЬ", "УЗЕЛ", "КОМПЛЕКС"]
PRODUCT_KIND_TITLES = {
    "МАТЕРИАЛ": "Материал",
    "КОМПЛЕКТУЮЩЕЕ": "Комплектующее (покупное)",
    "ДЕТАЛЬ": "Деталь",
    "УЗЕЛ": "Сборочная единица (узел)",
    "КОМПЛЕКС": "Комплекс (набор)",
}
POSITION_KINDS = ["БАЗА", "ДОБАВЛЕНИЕ", "ЗАМЕНА", "ИСКЛЮЧЕНИЕ"]


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v:g}"


class BOMService:
    """Управляющий класс «СервисСпецификаций»"""

    # ------------------------------------------------------------------ ЕИ
    def get_units(self, db: Session) -> List[Dict[str, Any]]:
        return [
            {"id": u.id, "код": u.код, "наименование": u.наименование, "обозначение": u.обозначение}
            for u in db.query(UnitOfMeasure).order_by(UnitOfMeasure.id).all()
        ]

    def add_unit(self, db: Session, код: str, наименование: str, обозначение: str) -> Dict[str, Any]:
        код, наименование, обозначение = (код or "").strip(), (наименование or "").strip(), (обозначение or "").strip()
        if not код or not наименование or not обозначение:
            return {"success": False, "message": "Заполните код, наименование и обозначение"}
        if db.query(UnitOfMeasure).filter((UnitOfMeasure.код == код) | (UnitOfMeasure.обозначение == обозначение)).first():
            return {"success": False, "message": "Единица с таким кодом или обозначением уже существует"}
        u = UnitOfMeasure(код=код, наименование=наименование, обозначение=обозначение)
        db.add(u)
        db.commit()
        return {"success": True, "message": f"Единица «{обозначение}» добавлена", "unit_id": u.id}

    def update_unit(self, db: Session, unit_id: int, код: str, наименование: str, обозначение: str) -> Dict[str, Any]:
        u = db.get(UnitOfMeasure, unit_id)
        if not u:
            return {"success": False, "message": "Единица измерения не найдена"}
        dup = db.query(UnitOfMeasure).filter(
            ((UnitOfMeasure.код == код) | (UnitOfMeasure.обозначение == обозначение)) & (UnitOfMeasure.id != unit_id)
        ).first()
        if dup:
            return {"success": False, "message": "Единица с таким кодом или обозначением уже существует"}
        u.код, u.наименование, u.обозначение = код, наименование, обозначение
        db.commit()
        return {"success": True, "message": "Единица измерения обновлена"}

    def delete_unit(self, db: Session, unit_id: int) -> Dict[str, Any]:
        u = db.get(UnitOfMeasure, unit_id)
        if not u:
            return {"success": False, "message": "Единица измерения не найдена"}
        used = db.query(BOMItem).filter(BOMItem.ед_изм_id == unit_id).count()
        if used:
            return {"success": False, "message": f"Единица используется в {used} позициях спецификаций"}
        db.delete(u)
        db.commit()
        return {"success": True, "message": "Единица измерения удалена"}

    # ------------------------------------------------------------- изделия
    def _unit_map(self, db: Session) -> Dict[int, str]:
        return {u.id: u.обозначение for u in db.query(UnitOfMeasure).all()}

    def _product_dict(self, db: Session, p: Product, units: Dict[int, str] = None) -> Dict[str, Any]:
        units = units if units is not None else self._unit_map(db)
        own_cnt = db.query(BOMItem).filter(BOMItem.изделие_id == p.id).count()
        mods = db.query(Product).filter(Product.базовое_изделие_id == p.id).count()
        base = db.get(Product, p.базовое_изделие_id) if p.базовое_изделие_id else None
        cls = db.get(Classificator, p.класс_id)
        return {
            "id": p.id,
            "наименование": p.наименование,
            "артикул": p.артикул,
            "класс_id": p.класс_id,
            "класс_название": cls.название if cls else None,
            "тип_изделия": p.тип_изделия,
            "тип_изделия_название": PRODUCT_KIND_TITLES.get(p.тип_изделия, p.тип_изделия),
            "базовое_изделие_id": p.базовое_изделие_id,
            "базовое_изделие": base.наименование if base else None,
            "ед_изм_id": p.ед_изм_id,
            "ед_изм": units.get(p.ед_изм_id),
            "позиций_собственных": own_cnt,
            "модификаций": mods,
            "является_модификацией": p.базовое_изделие_id is not None,
        }

    def get_products(self, db: Session, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        q = db.query(Product)
        if kind:
            q = q.filter(Product.тип_изделия == kind)
        units = self._unit_map(db)
        order = {k: i for i, k in enumerate(reversed(PRODUCT_KINDS))}
        items = [self._product_dict(db, p, units) for p in q.all()]
        items.sort(key=lambda x: (order.get(x["тип_изделия"], 9), x["наименование"], x["id"]))
        return items

    def get_product(self, db: Session, product_id: int) -> Optional[Dict[str, Any]]:
        p = db.get(Product, product_id)
        if not p:
            return None
        d = self._product_dict(db, p)
        d["модификации"] = [
            {"id": m.id, "наименование": m.наименование, "артикул": m.артикул}
            for m in db.query(Product).filter(Product.базовое_изделие_id == p.id).order_by(Product.id).all()
        ]
        # цепочка базовых изделий (для модификаций модификаций)
        chain, cur, guard = [], p, 0
        while cur.базовое_изделие_id and guard < 30:
            cur = db.get(Product, cur.базовое_изделие_id)
            if not cur:
                break
            chain.append({"id": cur.id, "наименование": cur.наименование, "артикул": cur.артикул})
            guard += 1
        d["цепочка_базовых"] = chain
        return d

    def set_product_kind(self, db: Session, product_id: int, kind: str, unit_id: Optional[int]) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        if not p:
            return {"success": False, "message": "Изделие не найдено"}
        if kind not in PRODUCT_KINDS:
            return {"success": False, "message": f"Недопустимый тип изделия. Допустимо: {', '.join(PRODUCT_KINDS)}"}
        if unit_id is not None and not db.get(UnitOfMeasure, unit_id):
            return {"success": False, "message": "Единица измерения не найдена"}
        if kind == "МАТЕРИАЛ" and db.query(BOMItem).filter(BOMItem.изделие_id == product_id).count():
            return {"success": False, "message": "Материал не может иметь собственную спецификацию — сначала удалите позиции"}
        p.тип_изделия = kind
        if unit_id is None:  # ЕИ количества обязательна: по умолчанию — ЕИ класса изделия
            cls = db.get(Classificator, p.класс_id)
            unit_id = (cls.базовая_ед_измерения if cls else None) or p.ед_изм_id
        p.ед_изм_id = unit_id
        db.commit()
        return {"success": True, "message": "Свойства изделия обновлены"}

    # --------------------------------------------------------- спецификация
    def _contains(self, db: Session, root_id: int, target_id: int) -> bool:
        """Входит ли target_id в состав root_id на любом уровне (для контроля циклов)"""
        row = db.execute(
            text("SELECT 1 FROM find_bom(:p) WHERE компонент_id = :t LIMIT 1"), {"p": root_id, "t": target_id}
        ).first()
        return row is not None

    def get_spec(self, db: Session, product_id: int) -> Dict[str, Any]:
        """Спецификация 1-го уровня: действующие позиции + исключённые позиции модификации"""
        p = db.get(Product, product_id)
        if not p:
            return {"success": False, "message": "Изделие не найдено"}
        units = self._unit_map(db)
        rows = db.execute(text("SELECT * FROM bom_effective(:p)"), {"p": product_id}).mappings().all()
        items = []
        for r in rows:
            comp = db.get(Product, r["компонент_id"])
            src = db.get(Product, r["источник_id"])
            pos = db.get(BOMItem, r["позиция_id"])
            items.append({
                "позиция_id": r["позиция_id"],
                "компонент_id": r["компонент_id"],
                "компонент": comp.наименование if comp else "?",
                "артикул": comp.артикул if comp else None,
                "тип_изделия": comp.тип_изделия if comp else None,
                "расход": r["расход"],
                "для_количества": r["для_количества"],
                "норма_на_единицу": r["расход"] / r["для_количества"],
                "ед_изм_id": r["ед_изм_id"],
                "ед_изм": units.get(r["ед_изм_id"]),
                "флаг_базы": r["флаг_базы"],
                "вид_позиции": r["вид_позиции"],
                "унаследовано": r["унаследовано"],
                "источник_id": r["источник_id"],
                "источник": src.наименование if src else None,
                "примечание": pos.примечание if pos else None,
                "порядковый_номер": pos.порядковый_номер if pos else 0,
                "имеет_состав": db.query(BOMItem).filter(BOMItem.изделие_id == r["компонент_id"]).count() > 0
                or bool(comp and comp.базовое_изделие_id),
            })
        # исключённые компоненты (только у модификаций)
        excluded = []
        for x in db.query(BOMItem).filter(BOMItem.изделие_id == product_id, BOMItem.вид_позиции == "ИСКЛЮЧЕНИЕ").all():
            excluded.append({
                "позиция_id": x.id, "компонент_id": x.компонент_id,
                "компонент": x.component.наименование, "артикул": x.component.артикул,
                "примечание": x.примечание,
            })
        items.sort(key=lambda i: (i["унаследовано"], i["порядковый_номер"] or 0, i["компонент"]))
        for n, i in enumerate(items, 1):
            i["номер"] = n
        return {"success": True, "product": self._product_dict(db, p, units), "items": items, "excluded": excluded}

    def add_position(self, db: Session, product_id: int, component_id: int, расход: float,
                     для_количества: float = 1.0, ед_изм_id: Optional[int] = None,
                     флаг_базы: Optional[bool] = None, примечание: Optional[str] = None,
                     автор: Optional[str] = None, причина: Optional[str] = None) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        c = db.get(Product, component_id)
        if not p:
            return {"success": False, "message": "Изделие-родитель не найдено"}
        if not c:
            return {"success": False, "message": "Изделие-компонент не найдено"}
        if product_id == component_id:
            return {"success": False, "message": "Изделие не может входить в собственный состав"}
        if p.тип_изделия == "МАТЕРИАЛ":
            return {"success": False, "message": "Материал не может иметь спецификацию"}
        if расход is None or расход <= 0:
            return {"success": False, "message": "Норма расхода должна быть больше нуля"}
        if для_количества is None or для_количества <= 0:
            return {"success": False, "message": "Значение «для количества» должно быть больше нуля"}
        if ед_изм_id is not None and not db.get(UnitOfMeasure, ед_изм_id):
            return {"success": False, "message": "Единица измерения не найдена"}
        if db.query(BOMItem).filter(BOMItem.изделие_id == product_id, BOMItem.компонент_id == component_id).first():
            return {"success": False, "message": f"Компонент «{c.наименование}» уже есть в собственной спецификации изделия"}
        if self._contains(db, component_id, product_id):
            return {"success": False, "message": f"Циклическая ссылка: «{p.наименование}» уже входит в состав «{c.наименование}»"}

        is_mod = p.базовое_изделие_id is not None
        inherited = False
        if is_mod:
            inherited = db.execute(
                text("SELECT 1 FROM bom_effective(:p) WHERE компонент_id = :c AND унаследовано"),
                {"p": product_id, "c": component_id},
            ).first() is not None
        вид = ("ЗАМЕНА" if inherited else "ДОБАВЛЕНИЕ") if is_mod else "БАЗА"
        if флаг_базы is None:
            флаг_базы = not is_mod
        max_no = db.execute(text('SELECT COALESCE(MAX("порядковый_номер"),0) FROM "позиция_спецификации" WHERE "изделие_id"=:p'),
                            {"p": product_id}).scalar()
        item = BOMItem(изделие_id=product_id, компонент_id=component_id, расход=расход,
                       для_количества=для_количества, ед_изм_id=ед_изм_id or c.ед_изм_id,
                       флаг_базы=флаг_базы, вид_позиции=вид, порядковый_номер=max_no + 1, примечание=примечание)
        db.add(item)
        db.flush()
        unit = db.get(UnitOfMeasure, item.ед_изм_id) if item.ед_изм_id else None
        new_val = f"{_fmt(расход)} {unit.обозначение if unit else ''} на {_fmt(для_количества)}".strip()
        desc = причина or (f"Замена нормы унаследованного компонента «{c.наименование}»" if вид == "ЗАМЕНА"
                           else f"Добавлен компонент «{c.наименование}»")
        self._register(db, product_id, desc, "ЗАМЕНА" if вид == "ЗАМЕНА" else "ДОБАВЛЕНИЕ", component_id, None, new_val, автор)
        db.commit()
        return {"success": True, "message": f"Компонент «{c.наименование}» добавлен ({вид.lower()})", "position_id": item.id}

    def update_position(self, db: Session, position_id: int, расход: float, для_количества: float,
                        ед_изм_id: Optional[int], флаг_базы: Optional[bool], примечание: Optional[str],
                        автор: Optional[str] = None, причина: Optional[str] = None) -> Dict[str, Any]:
        item = db.get(BOMItem, position_id)
        if not item:
            return {"success": False, "message": "Позиция спецификации не найдена"}
        if item.вид_позиции == "ИСКЛЮЧЕНИЕ":
            return {"success": False, "message": "Исключённую позицию нельзя редактировать — восстановите её"}
        if расход is None or расход <= 0:
            return {"success": False, "message": "Норма расхода должна быть больше нуля"}
        if для_количества is None or для_количества <= 0:
            return {"success": False, "message": "Значение «для количества» должно быть больше нуля"}
        units = self._unit_map(db)
        if ед_изм_id is not None and ед_изм_id not in units:
            return {"success": False, "message": "Единица измерения не найдена"}
        old = f"{_fmt(item.расход)} {units.get(item.ед_изм_id, '')} на {_fmt(item.для_количества)}"
        item.расход, item.для_количества, item.ед_изм_id = расход, для_количества, ед_изм_id
        if флаг_базы is not None:
            item.флаг_базы = флаг_базы
        item.примечание = примечание
        new = f"{_fmt(расход)} {units.get(ед_изм_id, '')} на {_fmt(для_количества)}"
        if old != new or причина:
            self._register(db, item.изделие_id, причина or f"Изменена норма расхода «{item.component.наименование}»",
                           "ИЗМЕНЕНИЕ_НОРМЫ", item.компонент_id, old, new, автор)
        db.commit()
        return {"success": True, "message": "Позиция спецификации обновлена"}

    def delete_position(self, db: Session, position_id: int, автор: Optional[str] = None,
                        причина: Optional[str] = None) -> Dict[str, Any]:
        item = db.get(BOMItem, position_id)
        if not item:
            return {"success": False, "message": "Позиция спецификации не найдена"}
        comp_name = item.component.наименование
        restore = item.вид_позиции == "ИСКЛЮЧЕНИЕ"
        old = None if restore else f"{_fmt(item.расход)} на {_fmt(item.для_количества)}"
        parent_id, comp_id = item.изделие_id, item.компонент_id
        db.delete(item)
        db.flush()
        if restore:
            self._register(db, parent_id, причина or f"Восстановлен унаследованный компонент «{comp_name}»",
                           "ВОССТАНОВЛЕНИЕ", comp_id, "исключён", "по базовому изделию", автор)
        else:
            self._register(db, parent_id, причина or f"Удалён компонент «{comp_name}»", "УДАЛЕНИЕ", comp_id, old, None, автор)
        db.commit()
        return {"success": True, "message": "Восстановлено" if restore else "Позиция удалена"}

    def exclude_component(self, db: Session, product_id: int, component_id: int,
                          автор: Optional[str] = None, причина: Optional[str] = None) -> Dict[str, Any]:
        """Исключить унаследованный компонент из спецификации модификации"""
        p = db.get(Product, product_id)
        if not p or not p.базовое_изделие_id:
            return {"success": False, "message": "Исключать унаследованные компоненты можно только у модификации"}
        row = db.execute(
            text("SELECT * FROM bom_effective(:p) WHERE компонент_id = :c AND унаследовано"),
            {"p": product_id, "c": component_id},
        ).mappings().first()
        if not row:
            return {"success": False, "message": "Компонент не наследуется от базового изделия"}
        comp = db.get(Product, component_id)
        db.add(BOMItem(изделие_id=product_id, компонент_id=component_id, расход=0, для_количества=1,
                       ед_изм_id=row["ед_изм_id"], флаг_базы=False, вид_позиции="ИСКЛЮЧЕНИЕ",
                       примечание=причина))
        db.flush()
        self._register(db, product_id, причина or f"Исключён унаследованный компонент «{comp.наименование}»",
                       "ИСКЛЮЧЕНИЕ", component_id, f"{_fmt(row['расход'])} на {_fmt(row['для_количества'])}", "исключён", автор)
        db.commit()
        return {"success": True, "message": f"Компонент «{comp.наименование}» исключён из модификации"}

    # ------------------------------------------------------- FIND / CALC
    def find_bom(self, db: Session, product_id: int) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        if not p:
            return {"success": False, "message": "Изделие не найдено"}
        units = self._unit_map(db)
        rows = db.execute(text("SELECT * FROM find_bom(:p) ORDER BY путь"), {"p": product_id}).mappings().all()
        names = {x.id: x for x in db.query(Product).all()}
        flat = []
        for r in rows:
            c = names.get(r["компонент_id"])
            flat.append({
                "уровень": r["уровень"],
                "родитель_id": r["родитель_id"],
                "компонент_id": r["компонент_id"],
                "компонент": c.наименование if c else "?",
                "артикул": c.артикул if c else None,
                "тип_изделия": c.тип_изделия if c else None,
                "расход": r["расход"],
                "для_количества": r["для_количества"],
                "норма_на_единицу": r["норма_на_единицу"],
                "количество": r["количество"],
                "ед_изм": units.get(r["ед_изм_id"]),
                "унаследовано": r["унаследовано"],
                "путь": list(r["путь"]),
            })
        # вложенное дерево для интерфейса
        root = {"компонент_id": p.id, "компонент": p.наименование, "артикул": p.артикул,
                "тип_изделия": p.тип_изделия, "уровень": 0, "children": []}
        index = {(p.id,): root}
        for f in flat:
            node = dict(f, children=[])
            parent = index.get(tuple(f["путь"][:-1]))
            if parent is not None:
                parent["children"].append(node)
            index[tuple(f["путь"])] = node
        # обход в глубину с упорядочиванием: сборки -> детали -> покупные -> материалы
        order = {"КОМПЛЕКС": 0, "УЗЕЛ": 1, "ДЕТАЛЬ": 2, "КОМПЛЕКТУЮЩЕЕ": 3, "МАТЕРИАЛ": 4}
        ordered = []

        def walk(n):
            n["children"].sort(key=lambda c: (order.get(c["тип_изделия"], 9), c["компонент"]))
            for ch in n["children"]:
                ordered.append({k: v for k, v in ch.items() if k != "children"})
                walk(ch)
        walk(root)
        flat = ordered
        max_level = max([f["уровень"] for f in flat], default=0)
        return {"success": True, "product": {"id": p.id, "наименование": p.наименование, "артикул": p.артикул},
                "rows": flat, "tree": root, "всего_строк": len(flat), "глубина": max_level}

    def calc_bom(self, db: Session, product_id: int, quantity: float, class_id: Optional[int] = None) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        if not p:
            return {"success": False, "message": "Изделие не найдено"}
        if quantity is None or quantity <= 0:
            return {"success": False, "message": "Количество изделий должно быть больше нуля"}
        cls = None
        if class_id is not None:
            cls = db.get(Classificator, class_id)
            if not cls:
                return {"success": False, "message": "Класс классификатора не найден"}
        units = self._unit_map(db)
        rows = db.execute(text("SELECT * FROM calc_bom(:p, :q, :c)"),
                          {"p": product_id, "q": quantity, "c": class_id}).mappings().all()
        result = []
        for r in rows:
            c = db.get(Product, r["компонент_id"])
            k = db.get(Classificator, c.класс_id) if c else None
            result.append({
                "компонент_id": r["компонент_id"],
                "компонент": c.наименование if c else "?",
                "артикул": c.артикул if c else None,
                "тип_изделия": c.тип_изделия if c else None,
                "класс": k.название if k else None,
                "ед_изм": units.get(r["ед_изм_id"]),
                "норма_на_единицу": r["норма_на_единицу"],
                "сводная_норма": r["сводная_норма"],
                "вхождений": r["вхождений"],
            })
        kind_order = {k: i for i, k in enumerate(PRODUCT_KINDS)}
        result.sort(key=lambda x: (kind_order.get(x["тип_изделия"], 9), x["класс"] or "", x["компонент"]))
        return {"success": True, "product": {"id": p.id, "наименование": p.наименование, "артикул": p.артикул},
                "количество": quantity, "класс": cls.название if cls else None, "items": result}

    def where_used(self, db: Session, component_id: int) -> List[Dict[str, Any]]:
        """Применяемость: в спецификации каких изделий непосредственно входит компонент"""
        rows = db.query(BOMItem).filter(BOMItem.компонент_id == component_id, BOMItem.вид_позиции != "ИСКЛЮЧЕНИЕ").all()
        units = self._unit_map(db)
        return [{"изделие_id": r.изделие_id, "изделие": r.parent.наименование, "артикул": r.parent.артикул,
                 "расход": r.расход, "для_количества": r.для_количества, "ед_изм": units.get(r.ед_изм_id),
                 "вид_позиции": r.вид_позиции} for r in rows]

    # -------------------------------------------------- модификации
    def create_modification(self, db: Session, base_id: int, name: str, article: Optional[str],
                            reason: Optional[str] = None, author: Optional[str] = None) -> Dict[str, Any]:
        base = db.get(Product, base_id)
        if not base:
            return {"success": False, "message": "Базовое изделие не найдено"}
        if base.тип_изделия == "МАТЕРИАЛ":
            return {"success": False, "message": "Для материала модификации не создаются"}
        name = (name or "").strip()
        if not name:
            return {"success": False, "message": "Укажите наименование модификации"}
        article = (article or "").strip() or None
        if article and db.query(Product).filter(Product.артикул == article).first():
            return {"success": False, "message": f"Изделие с артикулом «{article}» уже существует"}
        try:
            new_id = db.execute(text("SELECT create_modification(:b, :n, :a, :r, :u)"),
                                {"b": base_id, "n": name, "a": article, "r": reason, "u": author}).scalar()
            db.commit()
            return {"success": True, "message": f"Модификация «{name}» создана", "product_id": new_id}
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e)}

    def get_modifications(self, db: Session) -> List[Dict[str, Any]]:
        units = self._unit_map(db)
        res = []
        for m in db.query(Product).filter(Product.базовое_изделие_id.isnot(None)).order_by(Product.id).all():
            d = self._product_dict(db, m, units)
            own = db.query(BOMItem).filter(BOMItem.изделие_id == m.id).all()
            d["добавлено"] = sum(1 for x in own if x.вид_позиции == "ДОБАВЛЕНИЕ")
            d["заменено"] = sum(1 for x in own if x.вид_позиции == "ЗАМЕНА")
            d["исключено"] = sum(1 for x in own if x.вид_позиции == "ИСКЛЮЧЕНИЕ")
            d["унаследовано"] = db.execute(text("SELECT COUNT(*) FROM bom_effective(:p) WHERE унаследовано"),
                                           {"p": m.id}).scalar()
            res.append(d)
        return res

    # -------------------------------------------------- изменения
    def _register(self, db: Session, product_id: int, desc: str, kind: str, comp_id: Optional[int],
                  old: Optional[str], new: Optional[str], author: Optional[str]) -> int:
        return db.execute(text("SELECT register_change(:p, :d, :t, :c, :o, :n, :a)"),
                          {"p": product_id, "d": desc, "t": kind, "c": comp_id, "o": old, "n": new,
                           "a": author or "Администратор"}).scalar()

    def register_change(self, db: Session, product_id: int, description: str, author: Optional[str] = None) -> Dict[str, Any]:
        if not db.get(Product, product_id):
            return {"success": False, "message": "Изделие не найдено"}
        if not (description or "").strip():
            return {"success": False, "message": "Опишите суть изменения"}
        cid = self._register(db, product_id, description.strip(), "ПРОЧЕЕ", None, None, None, author)
        db.commit()
        return {"success": True, "message": "Изменение зарегистрировано", "change_id": cid}

    def get_changes(self, db: Session, product_id: Optional[int] = None,
                    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                    kind: Optional[str] = None) -> List[Dict[str, Any]]:
        q = db.query(SpecChange)
        if product_id:
            q = q.filter(SpecChange.изделие_id == product_id)
        if date_from:
            q = q.filter(SpecChange.дата >= date_from)
        if date_to:
            q = q.filter(SpecChange.дата <= date_to)
        if kind:
            q = q.filter(SpecChange.тип_изменения == kind)
        return [{
            "id": c.id, "номер": c.номер, "дата": c.дата, "тип_изменения": c.тип_изменения,
            "изделие_id": c.изделие_id, "изделие": c.product.наименование if c.product else None,
            "артикул": c.product.артикул if c.product else None,
            "компонент_id": c.компонент_id, "компонент": c.component.наименование if c.component else None,
            "старое_значение": c.старое_значение, "новое_значение": c.новое_значение,
            "описание": c.описание, "автор": c.автор,
        } for c in q.order_by(SpecChange.дата.desc(), SpecChange.id.desc()).all()]


bom_service = BOMService()


# ======================================================================
# Тестовые данные для задания 5
# ======================================================================
def load_bom_test_data(db: Session, classifier) -> None:
    """Справочник ЕИ, материалы, элементы мини-фигурок, модули сборки,
    наборы-комплексы, их спецификации, модификация и журнал изменений."""
    svc = bom_service
    for code, name, sym in [("796", "Штука", "шт"), ("166", "Килограмм", "кг"), ("163", "Грамм", "г"),
                            ("006", "Метр", "м"), ("839", "Комплект", "компл")]:
        svc.add_unit(db, code, name, sym)
    U = {u["обозначение"]: u["id"] for u in svc.get_units(db)}

    def node(name, parent, kind="промежуточный", order=0):
        ex = db.query(Classificator).filter(Classificator.название == name).first()
        if ex:
            return ex.id
        return classifier.add_node(db, name, kind, parent, sort_order=order)["node_id"]

    def cls_id(name):
        n = db.query(Classificator).filter(Classificator.название == name).first()
        return n.id if n else None

    root = cls_id("Изделия бренда LEGO")
    materials = node("Материалы", root, order=4)
    plastics = node("Пластмассы", materials, "терминальный", 1)
    dyes = node("Красители", materials, "терминальный", 2)
    rubber = node("Резиновые смеси", materials, "терминальный", 3)
    purchased = node("Комплектующие и упаковка", root, order=5)
    packaging = node("Упаковка", purchased, "терминальный", 1)
    printed = node("Печатная продукция", purchased, "терминальный", 2)
    mf_elements = node("Элементы мини-фигурок", cls_id("Мини-фигурки"), "терминальный", 2)
    modules = node("Модули сборки", cls_id("Наборы"), "терминальный", 4)

    def prod(cls, name, sku, kind, unit):
        ex = db.query(Product).filter(Product.артикул == sku).first()
        if ex:
            pid = ex.id
        else:
            pid = classifier.add_product(db, cls, name, sku)["product_id"]
        svc.set_product_kind(db, pid, kind, U[unit])
        return pid

    P = {}
    # --- материалы
    P["ABS"] = prod(plastics, "Гранулы ABS-пластика", "MAT-ABS", "МАТЕРИАЛ", "кг")
    P["PC"] = prod(plastics, "Гранулы поликарбоната (прозрачный)", "MAT-PC", "МАТЕРИАЛ", "кг")
    P["RUB"] = prod(rubber, "Резиновая смесь SBR", "MAT-SBR", "МАТЕРИАЛ", "кг")
    for key, color in [("RED", "красный"), ("BLU", "синий"), ("YEL", "жёлтый"), ("GRN", "зелёный"),
                       ("BLK", "чёрный"), ("WHT", "белый"), ("GRY", "серый")]:
        P["DYE-" + key] = prod(dyes, f"Краситель-концентрат {color}", f"MAT-DYE-{key}", "МАТЕРИАЛ", "г")
    # --- покупные комплектующие
    P["BOX"] = prod(packaging, "Коробка упаковочная 75257", "PKG-BOX-75257", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["BOXG"] = prod(packaging, "Коробка подарочная 75257 (с окном)", "PKG-GIFT-75257", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["BOX60266"] = prod(packaging, "Коробка упаковочная 60266", "PKG-BOX-60266", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["BAG"] = prod(packaging, "Пакет полиэтиленовый пронумерованный", "PKG-BAG", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["MAN"] = prod(printed, "Инструкция по сборке 75257", "DOC-MAN-75257", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["MAN60266"] = prod(printed, "Инструкция по сборке 60266", "DOC-MAN-60266", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["STK"] = prod(printed, "Лист наклеек 75257", "DOC-STK-75257", "КОМПЛЕКТУЮЩЕЕ", "шт")

    # --- детали (существующие изделия задания 1.3) — тип ДЕТАЛЬ
    sku_dye = {"BR-2X4-RED": ("ABS", 3.6, "DYE-RED"), "BR-2X4-BLU": ("ABS", 3.6, "DYE-BLU"),
               "BR-2X4-YEL": ("ABS", 3.6, "DYE-YEL"), "BR-2X2-GRN": ("ABS", 1.9, "DYE-GRN"),
               "BR-2X2-BLK": ("ABS", 1.9, "DYE-BLK"), "PL-1X2-WHT": ("ABS", 0.85, "DYE-WHT"),
               "PL-1X2-GRY": ("ABS", 0.85, "DYE-GRY"), "WH-30-BLK": ("RUB", 5.1, "DYE-BLK"),
               "WH-30-GRY": ("RUB", 5.1, "DYE-GRY")}
    detail_names = {"BR-2X4": "Кирпич 2x4", "BR-2X2": "Кирпич 2x2", "PL-1X2": "Плита 1x2", "WH-30": "Колесо"}
    parts_root = cls_id("Детали") or node("Детали", root, order=2)
    for sku in sku_dye:
        name = detail_names[sku.rsplit("-", 1)[0]]
        # если изделия задания 1.3 нет в базе (было удалено/переименовано) — создаём его
        P[sku] = prod(cls_id(name) or node(name, parts_root, "терминальный"), name, sku, "ДЕТАЛЬ", "шт")
    # --- элементы мини-фигурок
    P["HEAD"] = prod(mf_elements, "Голова мини-фигурки", "MFE-HEAD-YEL", "ДЕТАЛЬ", "шт")
    P["T-LUKE"] = prod(mf_elements, "Торс «Люк Скайуокер»", "MFE-TORSO-LUKE", "ДЕТАЛЬ", "шт")
    P["T-VADER"] = prod(mf_elements, "Торс «Дарт Вейдер»", "MFE-TORSO-VADER", "ДЕТАЛЬ", "шт")
    P["T-POL"] = prod(mf_elements, "Торс «Полицейский»", "MFE-TORSO-POLICE", "ДЕТАЛЬ", "шт")
    P["L-WHT"] = prod(mf_elements, "Ноги мини-фигурки белые", "MFE-LEGS-WHT", "ДЕТАЛЬ", "шт")
    P["L-BLK"] = prod(mf_elements, "Ноги мини-фигурки чёрные", "MFE-LEGS-BLK", "ДЕТАЛЬ", "шт")
    P["HELM"] = prod(mf_elements, "Шлем «Дарт Вейдер»", "MFE-HELMET-VADER", "ДЕТАЛЬ", "шт")
    P["CAP"] = prod(mf_elements, "Фуражка полицейского", "MFE-CAP-POLICE", "ДЕТАЛЬ", "шт")
    P["SABER"] = prod(mf_elements, "Световой меч", "MFE-SABER", "ДЕТАЛЬ", "шт")
    mf_class = cls_id("Мини-фигурка") or node("Мини-фигурка", cls_id("Мини-фигурки") or root, "терминальный")
    for sku, name in [("MF-SW001", "Люк Скайуокер"), ("MF-SW002", "Дарт Вейдер"), ("MF-CT001", "Полицейский")]:
        P[sku] = prod(mf_class, name, sku, "УЗЕЛ", "шт")
    # --- модули сборки и наборы-комплексы
    P["PK1"] = prod(modules, "Модуль №1 «Кабина корабля»", "MOD-75257-1", "УЗЕЛ", "шт")
    P["PK2"] = prod(modules, "Модуль №2 «Двигатели и шасси»", "MOD-75257-2", "УЗЕЛ", "шт")
    P["PK3"] = prod(modules, "Модуль №3 «Экипаж»", "MOD-75257-3", "УЗЕЛ", "шт")
    P["SET75257"] = prod(cls_id("Тематика Star Wars"), "Космический корабль 75257", "SET-75257", "КОМПЛЕКС", "шт")
    P["SET60266"] = prod(cls_id("Тематика City"), "Полицейский участок 60266", "SET-60266", "КОМПЛЕКС", "шт")

    A1, A2, A3 = "Технолог Петрова А.С.", "Конструктор Смирнов И.В.", "Администратор"

    def add(parent, comp, q, unit="шт", per=1, base=None, note=None, author=A1):
        if parent not in P or comp not in P:
            print(f"  [BOM] пропущено: нет изделия {parent if parent not in P else comp}")
            return
        r = svc.add_position(db, P[parent], P[comp], q, per, U[unit], base, note, author)
        if not r["success"]:
            print("  [BOM] ", r["message"])

    # Детали: материалы на 1000 шт (демонстрация «для количества»)
    for sku, (mat, kg, dye) in sku_dye.items():
        if sku in P:
            add(sku, mat, kg, "кг", 1000)
            add(sku, dye, 40 if mat == "ABS" else 60, "г", 1000)
    for key, mat, kg, dye in [("HEAD", "ABS", 0.9, "DYE-YEL"), ("T-LUKE", "ABS", 1.6, "DYE-WHT"),
                              ("T-VADER", "ABS", 1.6, "DYE-BLK"), ("T-POL", "ABS", 1.6, "DYE-BLU"),
                              ("L-WHT", "ABS", 1.3, "DYE-WHT"), ("L-BLK", "ABS", 1.3, "DYE-BLK"),
                              ("HELM", "ABS", 1.1, "DYE-BLK"), ("CAP", "ABS", 0.4, "DYE-BLU"),
                              ("SABER", "PC", 0.5, "DYE-RED")]:
        add(key, mat, kg, "кг", 1000, author=A2)
        add(key, dye, 25, "г", 1000, author=A2)
    # Мини-фигурки (сборочные единицы)
    for mf, parts in [("MF-SW001", ["HEAD", "T-LUKE", "L-WHT", "SABER"]),
                      ("MF-SW002", ["HEAD", "T-VADER", "L-BLK", "HELM", "SABER"]),
                      ("MF-CT001", ["HEAD", "T-POL", "L-BLK", "CAP"])]:
        if mf in P:
            for part in parts:
                add(mf, part, 1, author=A2)
    # Модули сборки набора 75257
    for comp, q in [("BR-2X4-YEL", 12), ("BR-2X2-GRN", 8), ("PL-1X2-GRY", 10), ("BAG", 1)]:
        add("PK1", comp, q, author=A2)
    for comp, q in [("BR-2X4-YEL", 8), ("BR-2X2-GRN", 7), ("WH-30-BLK", 4), ("PL-1X2-WHT", 6), ("BAG", 1)]:
        add("PK2", comp, q, author=A2)
    for comp, q in [("MF-SW001", 1), ("BAG", 1)]:
        add("PK3", comp, q, author=A2)
    # Набор 75257 (комплекс). Коробка — НЕ базовая позиция (флаг_базы = FALSE),
    # поэтому модификации её не наследуют.
    for comp, q, base in [("PK1", 1, True), ("PK2", 1, True), ("PK3", 1, True), ("MAN", 1, True),
                          ("STK", 1, True), ("BOX", 1, False)]:
        add("SET75257", comp, q, base=base, note=("Только для базового исполнения" if not base else None), author=A2)
    # Набор 60266
    for comp, q in [("BR-2X4-RED", 24), ("BR-2X4-BLU", 18), ("BR-2X2-BLK", 10), ("PL-1X2-WHT", 20),
                    ("WH-30-BLK", 4), ("MF-CT001", 2), ("MAN60266", 1), ("BOX60266", 1)]:
        add("SET60266", comp, q, author=A2)

    # Изменение базовой спецификации (журнал изменений)
    pos = db.query(BOMItem).filter(BOMItem.изделие_id == P["PK1"], BOMItem.компонент_id == P["PL-1X2-GRY"]).first()
    if pos:
        svc.update_position(db, pos.id, 12, 1, U["шт"], True, None, A2,
                            "Извещение 75257-01: усиление пола кабины, +2 плиты 1x2")
    # Модификация «Подарочное издание»
    mod = svc.create_modification(db, P["SET75257"], "Космический корабль 75257 — подарочное издание",
                                  "SET-75257-GIFT", "Подарочное издание к новогоднему сезону", A3)
    if mod["success"]:
        P["GIFT"] = mod["product_id"]
        svc.add_position(db, P["GIFT"], P["BOXG"], 1, 1, U["шт"], True, "Коробка с прозрачным окном", A1,
                         "Подарочная упаковка вместо стандартной")
        svc.add_position(db, P["GIFT"], P["MF-SW002"], 1, 1, U["шт"], True, "Бонусная мини-фигурка", A1,
                         "Добавлена бонусная мини-фигурка Дарта Вейдера")
        svc.add_position(db, P["GIFT"], P["STK"], 2, 1, U["шт"], True, "Расширенный лист наклеек", A1,
                         "Два листа наклеек вместо одного")
        svc.exclude_component(db, P["GIFT"], P["MAN"], A1, "Печатная инструкция заменена QR-кодом на цифровую версию")
    db.commit()

    # ================= Дополнительные данные: Technic, экспорт, цепочка модификаций =================
    technic = node("Технические детали", cls_id("Детали"), order=3)
    axles = node("Оси и штифты", technic, "терминальный", 1)
    gears = node("Шестерни", technic, "терминальный", 2)
    beams = node("Балки", technic, "терминальный", 3)
    wheels = node("Колёса и шины", technic, "терминальный", 4)
    fibers = node("Волокна и нити", materials, "терминальный", 4)
    electric = node("Электрика", purchased, "терминальный", 3)

    P["CORD"] = prod(fibers, "Шнур полиэфирный 1 мм", "MAT-CORD-1", "МАТЕРИАЛ", "м")
    P["AX5"] = prod(axles, "Ось 5L", "TP-AXLE-5L", "ДЕТАЛЬ", "шт")
    P["PIN"] = prod(axles, "Штифт с фрикцией", "TP-PIN-FR", "ДЕТАЛЬ", "шт")
    P["G24"] = prod(gears, "Шестерня 24z", "TP-GEAR-24", "ДЕТАЛЬ", "шт")
    P["G8"] = prod(gears, "Шестерня 8z", "TP-GEAR-8", "ДЕТАЛЬ", "шт")
    P["BM15"] = prod(beams, "Балка 15L", "TP-BEAM-15", "ДЕТАЛЬ", "шт")
    P["BM7"] = prod(beams, "Балка 7L", "TP-BEAM-7", "ДЕТАЛЬ", "шт")
    P["RIM"] = prod(wheels, "Диск колёсный 56 мм", "TP-RIM-56", "ДЕТАЛЬ", "шт")
    P["TIRE"] = prod(wheels, "Шина 81x35", "TP-TIRE-81", "ДЕТАЛЬ", "шт")
    P["WHL"] = prod(wheels, "Колесо в сборе 81x35", "TP-WHEEL-81", "УЗЕЛ", "шт")
    P["MOTOR"] = prod(electric, "Электромотор L (Powered Up)", "EL-MOTOR-L", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["HUB"] = prod(electric, "Батарейный блок Hub", "EL-HUB", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["BOX42110"] = prod(packaging, "Коробка упаковочная 42110", "PKG-BOX-42110", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["BOX42110L"] = prod(packaging, "Коробка упаковочная 42110 Lite", "PKG-BOX-42110-L", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["MAN42110"] = prod(printed, "Инструкция по сборке 42110", "DOC-MAN-42110", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["MANML"] = prod(printed, "Инструкция многоязычная 60266", "DOC-MAN-60266-ML", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["CERT"] = prod(printed, "Сертификат подлинности (номерной)", "DOC-CERT", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["STAND"] = prod(packaging, "Подставка-витрина для набора", "PKG-STAND", "КОМПЛЕКТУЮЩЕЕ", "шт")
    P["TM1"] = prod(modules, "Модуль 42110-1 «Шасси и подвеска»", "MOD-42110-1", "УЗЕЛ", "шт")
    P["TM2"] = prod(modules, "Модуль 42110-2 «Кузов»", "MOD-42110-2", "УЗЕЛ", "шт")
    P["TM3"] = prod(modules, "Модуль 42110-3 «Лебёдка»", "MOD-42110-3", "УЗЕЛ", "шт")
    P["SET42110"] = prod(cls_id("Тематика Technic") or modules, "Внедорожник 42110", "SET-42110", "КОМПЛЕКС", "шт")

    for key, mat, kg, dye in [("AX5", "ABS", 0.9, "DYE-GRY"), ("PIN", "ABS", 0.25, "DYE-BLK"),
                              ("G24", "ABS", 2.2, "DYE-GRY"), ("G8", "ABS", 0.6, "DYE-GRY"),
                              ("BM15", "ABS", 3.1, "DYE-RED"), ("BM7", "ABS", 1.5, "DYE-RED"),
                              ("RIM", "ABS", 7.5, "DYE-GRY"), ("TIRE", "RUB", 28.0, "DYE-BLK")]:
        add(key, mat, kg, "кг", 1000, author=A2)
        add(key, dye, 100 if key == "TIRE" else 30, "г", 1000, author=A2)
    add("WHL", "RIM", 1, author=A2)
    add("WHL", "TIRE", 1, author=A2)
    for comp, q in [("BM15", 8), ("BM7", 6), ("AX5", 6), ("PIN", 40), ("G24", 4), ("G8", 2), ("WHL", 4), ("BAG", 1)]:
        add("TM1", comp, q, author=A2)
    for comp, q in [("BR-2X4-RED", 20), ("PL-1X2-GRY", 16), ("BM15", 10), ("PIN", 30), ("BAG", 1)]:
        add("TM2", comp, q, author=A2)
    add("TM3", "G24", 2, author=A2)
    add("TM3", "G8", 1, author=A2)
    add("TM3", "AX5", 2, author=A2)
    add("TM3", "CORD", 0.6, "м", note="Трос лебёдки", author=A1)
    add("TM3", "BAG", 1, author=A2)
    for comp, q, base in [("TM1", 1, True), ("TM2", 1, True), ("TM3", 1, True), ("MOTOR", 2, True),
                          ("HUB", 1, True), ("MAN42110", 1, True), ("BOX42110", 1, False)]:
        add("SET42110", comp, q, base=base, note=("Только для базового исполнения" if not base else None), author=A2)
    pos = db.query(BOMItem).filter(BOMItem.изделие_id == P["TM1"], BOMItem.компонент_id == P["PIN"]).first()
    if pos:
        svc.update_position(db, pos.id, 44, 1, U["шт"], True, None, A2,
                            "Извещение 42110-01: +4 штифта для усиления подвески")
    m = svc.create_modification(db, P["SET42110"], "Внедорожник 42110 — версия без электрики",
                                "SET-42110-LITE", "Бюджетная версия для розничной сети", A1)
    if m["success"]:
        P["LITE"] = m["product_id"]
        svc.exclude_component(db, P["LITE"], P["MOTOR"], A1, "Моторизация не входит в бюджетную версию")
        svc.exclude_component(db, P["LITE"], P["HUB"], A1, "Батарейный блок не требуется без моторов")
        svc.add_position(db, P["LITE"], P["BOX42110L"], 1, 1, U["шт"], False, "Уменьшенная коробка", A1,
                         "Коробка меньшего размера для Lite-версии")
        svc.add_position(db, P["LITE"], P["G8"], 4, 1, U["шт"], False, "Ручной привод лебёдки", A2,
                         "Ручной привод вместо моторизованного")
    m = svc.create_modification(db, P["SET60266"], "Полицейский участок 60266 — экспортное исполнение",
                                "SET-60266-EXP", "Заказ №118: поставка в ЕС", A1)
    if m["success"]:
        P["EXP"] = m["product_id"]
        svc.exclude_component(db, P["EXP"], P["MAN60266"], A1, "Заменяется многоязычной инструкцией")
        svc.add_position(db, P["EXP"], P["MANML"], 1, 1, U["шт"], False, "EN/DE/FR/IT/ES", A1,
                         "Инструкция на 5 языках для рынка ЕС")
        svc.add_position(db, P["EXP"], P["MF-CT001"], 3, 1, U["шт"], False, None, A1,
                         "Третья фигурка полицейского для экспортной версии")
    if "GIFT" in P:
        m = svc.create_modification(db, P["GIFT"], "Космический корабль 75257 — коллекционное издание",
                                    "SET-75257-COLL", "Лимитированная серия 5000 экз. на основе подарочного издания", A3)
        if m["success"]:
            P["COLL"] = m["product_id"]
            svc.add_position(db, P["COLL"], P["CERT"], 1, 1, U["шт"], False, "Номер экземпляра", A1,
                             "Добавлен номерной сертификат подлинности")
            svc.add_position(db, P["COLL"], P["STAND"], 1, 1, U["шт"], False, None, A1,
                             "Добавлена подставка-витрина")
    svc.register_change(db, P["SET75257"], "Плановый пересмотр норм расхода красителей на 2027 год: изменений не требуется",
                        "Главный технолог Орлов В.П.")
    db.commit()
    # Журнал изменений: распределяем даты по истории (для демонстрации фильтра по датам)
    db.execute(text("""UPDATE "изменение_спецификации" SET "дата" =
                       TIMESTAMP '2026-03-02 09:00' + (id - 1) * INTERVAL '1 day 4 hours'"""))
    db.commit()
