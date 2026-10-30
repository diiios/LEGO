# routing_service.py
"""
Задание 6. Сервис маршрутной технологии изготовления изделий.

Применённые паттерны и принципы ООП:
  * Приспособленец (Flyweight) — TypicalProcessFlyweight / TypicalProcessFactory:
      внутреннее состояние типового ТП (операции, нормативы, ресурсы) хранится в одном
      неизменяемом объекте на весь процесс и разделяется всеми Изделиями-Операциями,
      а внешнее состояние (значения параметров) передаётся при каждом обращении.
  * Фабричный метод (Factory Method) — ProductOperationFactory создаёт нужный подкласс
      Изделия-Операции (Позиция тех-маршрута / Позиция закупки) и проверяет его инварианты.
  * Компоновщик (Composite) — RouteComponent / RouteOperationNode / PurchaseLeaf:
      дерево маршрута (результат FIND_TM), в котором операция и закупка обрабатываются единообразно.
  * Фасад (Facade) — RoutingService: единая точка входа для интерфейса и API,
      скрывающая ORM и хранимые функции PostgreSQL.
  * Наследование и полиморфизм — ProductOperation → RoutePosition / PurchasePosition (routing_models).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import BOMItem, Classificator, Enumeration, EnumValue, Product, Subject, UnitOfMeasure
from routing_models import (InputResource, OperationTool, ProductOperation, PurchasePosition, RoutePosition,
                            Tool, TypicalOperation, TypicalParam, TypicalParamValue, TypicalProcess,
                            TypicalResource, WorkCenter)

ROOT_OPERATIONS = "Технологические операции"
ROOT_PROFESSIONS = "Профессии"
ROOT_EQUIPMENT = "Оборудование"
ROOT_TOOLS = "Инструмент и оснастка"
QUALIFICATION_ENUM = "Квалификация (разряд)"
OP_PURCHASE_CLASS = "Закупка"


class RoutingError(Exception):
    """Нарушение правил предметной области (сообщение показывается пользователю)"""


# =====================================================================================
# Приспособленец (Flyweight): типовой технологический процесс
# =====================================================================================
@dataclass(frozen=True)
class LinearNorm:
    """Норматив вида «база + коэффициент × параметр» (укрупнённое нормирование)"""
    base: float
    coef: float
    param_id: Optional[int]

    def evaluate(self, values: Dict[int, float], defaults: Dict[int, float]) -> float:
        if not self.param_id or not self.coef:
            return self.base
        value = values.get(self.param_id, defaults.get(self.param_id, 0.0))
        return self.base + self.coef * (value or 0.0)


@dataclass(frozen=True)
class TypicalParamFW:
    id: int
    code: str
    name: str
    unit: Optional[str]
    min_value: Optional[float]
    max_value: Optional[float]
    default: Optional[float]


@dataclass(frozen=True)
class TypicalOperationFW:
    id: int
    number: int
    name: str
    class_id: Optional[int]
    work_center_id: Optional[int]
    profession_id: Optional[int]
    qualification_id: Optional[int]
    t_setup: float
    t_piece: LinearNorm


@dataclass(frozen=True)
class TypicalResourceFW:
    id: int
    product_id: int
    unit_id: Optional[int]
    norm: LinearNorm


@dataclass(frozen=True)
class TypicalProcessFlyweight:
    """Внутреннее (разделяемое, неизменяемое) состояние типового ТП"""
    id: int
    code: str
    name: str
    params: Tuple[TypicalParamFW, ...]
    operations: Tuple[TypicalOperationFW, ...]
    resources: Tuple[TypicalResourceFW, ...]

    @property
    def defaults(self) -> Dict[int, float]:
        return {p.id: p.default for p in self.params if p.default is not None}

    def validate(self, values: Dict[int, float]) -> None:
        """Проверка внешнего состояния (значений параметров) на допустимость"""
        unknown = set(values) - {p.id for p in self.params}
        if unknown:
            raise RoutingError(f"Параметры {sorted(unknown)} не принадлежат типовому ТП «{self.name}»")
        for p in self.params:
            v = values.get(p.id, p.default)
            if v is None:
                raise RoutingError(f"Не задано значение параметра «{p.name}» ({p.code})")
            if p.min_value is not None and v < p.min_value:
                raise RoutingError(f"Параметр «{p.name}»: значение {v:g} меньше минимального {p.min_value:g}")
            if p.max_value is not None and v > p.max_value:
                raise RoutingError(f"Параметр «{p.name}»: значение {v:g} больше максимального {p.max_value:g}")

    def operations_for(self, values: Dict[int, float]) -> List[Dict[str, Any]]:
        """Операции типового ТП с нормами времени для конкретного контекста (внешнего состояния)"""
        d = self.defaults
        return [{"номер": o.number, "наименование": o.name, "класс_то_id": o.class_id,
                 "грц_id": o.work_center_id, "профессия_id": o.profession_id,
                 "квалификация_id": o.qualification_id, "тпз": o.t_setup,
                 "тшт": round(o.t_piece.evaluate(values, d), 6)} for o in self.operations]

    def resources_for(self, values: Dict[int, float]) -> List[Dict[str, Any]]:
        d = self.defaults
        return [{"изделие_id": r.product_id, "ед_изм_id": r.unit_id,
                 "норма": round(r.norm.evaluate(values, d), 9)} for r in self.resources]

    def piece_time(self, values: Dict[int, float]) -> float:
        return sum(o["тшт"] for o in self.operations_for(values))


class TypicalProcessFactory:
    """Фабрика приспособленцев: возвращает единственный экземпляр типового ТП из пула"""

    def __init__(self) -> None:
        self._pool: Dict[int, TypicalProcessFlyweight] = {}
        self.requests = 0

    def get(self, db: Session, tp_id: int) -> TypicalProcessFlyweight:
        self.requests += 1
        fw = self._pool.get(tp_id)
        if fw is None:
            tp = db.get(TypicalProcess, tp_id)
            if not tp:
                raise RoutingError("Типовой ТП не найден")
            fw = TypicalProcessFlyweight(
                id=tp.id, code=tp.обозначение, name=tp.наименование,
                params=tuple(TypicalParamFW(p.id, p.обозначение, p.наименование, p.ед_изм, p.мин_значение,
                                            p.макс_значение, p.по_умолчанию) for p in tp.params),
                operations=tuple(TypicalOperationFW(o.id, o.номер, o.наименование, o.класс_то_id, o.грц_id,
                                                    o.профессия_id, o.квалификация_id, o.тпз,
                                                    LinearNorm(o.тшт_база, o.тшт_коэф, o.параметр_id))
                                 for o in tp.operations),
                resources=tuple(TypicalResourceFW(r.id, r.изделие_id, r.ед_изм_id,
                                                  LinearNorm(r.норма_база, r.норма_коэф, r.параметр_id))
                                for r in tp.resources),
            )
            self._pool[tp_id] = fw
        return fw

    def invalidate(self, tp_id: Optional[int] = None) -> None:
        """Сброс кэша после изменения типового ТП (внутреннее состояние неизменяемо — пересоздаём)"""
        if tp_id is None:
            self._pool.clear()
        else:
            self._pool.pop(tp_id, None)

    @property
    def size(self) -> int:
        return len(self._pool)


# =====================================================================================
# Фабричный метод: создание Изделия-Операции нужного подкласса
# =====================================================================================
class ProductOperationFactory:
    """Создаёт Позицию тех-маршрута или Позицию закупки и проверяет инварианты подкласса"""

    @staticmethod
    def create(kind: str, **fields: Any) -> ProductOperation:
        if kind == "ТЕХ":
            if not fields.get("класс_то_id") and not fields.get("типовой_тп_id"):
                raise RoutingError("Для операции тех-маршрута укажите класс технологической операции")
            if (fields.get("тпз") or 0) < 0 or (fields.get("тшт") or 0) < 0:
                raise RoutingError("Нормы времени Тпз и Тшт не могут быть отрицательными")
            fields.pop("цена", None)
            return RoutePosition(**fields)
        if kind == "ЗАКУПКА":
            if fields.get("цена") is not None and fields["цена"] < 0:
                raise RoutingError("Цена закупки не может быть отрицательной")
            for k in ("грц_id", "профессия_id", "квалификация_id", "типовой_тп_id"):
                fields.pop(k, None)
            fields["тпз"], fields["тшт"] = 0.0, 0.0
            return PurchasePosition(**fields)
        raise RoutingError(f"Неизвестный вид позиции: {kind}")


# =====================================================================================
# Компоновщик: дерево технологического маршрута
# =====================================================================================
class RouteComponent(ABC):
    def __init__(self, row: Dict[str, Any]):
        self.row = row
        self.children: List["RouteComponent"] = []

    @abstractmethod
    def material_cost(self) -> float: ...

    @abstractmethod
    def labor_minutes(self) -> float: ...

    def add(self, child: "RouteComponent") -> None:
        raise RoutingError("К позиции закупки нельзя добавить вложенные операции")

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.row)
        d["children"] = [c.to_dict() for c in self.children]
        return d


class PurchaseLeaf(RouteComponent):
    """Лист: позиция закупки — стоимость = количество × цена, труда нет"""

    def material_cost(self) -> float:
        return (self.row.get("количество") or 0) * (self.row.get("цена") or 0)

    def labor_minutes(self) -> float:
        return 0.0


class RouteOperationNode(RouteComponent):
    """Составной узел: операция тех-маршрута, во вложенных узлах — её входные ресурсы"""

    def add(self, child: RouteComponent) -> None:
        self.children.append(child)

    def material_cost(self) -> float:
        return sum(c.material_cost() for c in self.children)

    def labor_minutes(self) -> float:
        return (self.row.get("тшт_итого") or 0) * (self.row.get("количество") or 0) + \
            sum(c.labor_minutes() for c in self.children)


# =====================================================================================
# Фасад: сервис маршрутной технологии
# =====================================================================================
class RoutingService:
    """Управляющий класс «Сервис_маршрутов»"""

    def __init__(self) -> None:
        self.flyweights = TypicalProcessFactory()

    # ------------------------------------------------------------ справочники
    def _subtree(self, db: Session, root_name: str, terminal_only: bool = True) -> List[Dict[str, Any]]:
        root = db.query(Classificator).filter(Classificator.название == root_name).first()
        if not root:
            return []
        rows = db.execute(text("""
            WITH RECURSIVE t AS (
                SELECT id, "название", "родительский_id", 0 AS lvl FROM "классификатор" WHERE id = :r
                UNION ALL
                SELECT k.id, k."название", k."родительский_id", t.lvl + 1
                FROM "классификатор" k JOIN t ON k."родительский_id" = t.id)
            SELECT t.id, t."название", t.lvl,
                   NOT EXISTS (SELECT 1 FROM "классификатор" c WHERE c."родительский_id" = t.id) AS leaf
            FROM t WHERE t.id <> :r ORDER BY t.lvl, t."название" """), {"r": root.id}).mappings().all()
        return [{"id": r["id"], "name": r["название"], "level": r["lvl"]} for r in rows
                if r["leaf"] or not terminal_only]

    def _qualifications(self, db: Session) -> List[Dict[str, Any]]:
        e = db.query(Enumeration).filter(Enumeration.name == QUALIFICATION_ENUM).first()
        if not e:
            return []
        vals = db.query(EnumValue).filter(EnumValue.enumeration_id == e.id).order_by(EnumValue.sort_order).all()
        return [{"id": v.id, "name": v.value, "ставка": (v.extra_data or {}).get("ставка", 0)} for v in vals]

    def references(self, db: Session) -> Dict[str, Any]:
        return {
            "operation_classes": self._subtree(db, ROOT_OPERATIONS),
            "professions": self._subtree(db, ROOT_PROFESSIONS),
            "equipment_classes": self._subtree(db, ROOT_EQUIPMENT),
            "tool_classes": self._subtree(db, ROOT_TOOLS),
            "qualifications": self._qualifications(db),
            "work_centers": [{"id": g.id, "name": f"{g.код} {g.наименование}"} for g in
                             db.query(WorkCenter).order_by(WorkCenter.код).all()],
            "tools": [{"id": t.id, "name": f"{t.обозначение} {t.наименование}", "вид": t.вид} for t in
                      db.query(Tool).order_by(Tool.обозначение).all()],
            "typical": [{"id": t.id, "name": f"{t.обозначение} {t.наименование}"} for t in
                        db.query(TypicalProcess).order_by(TypicalProcess.обозначение).all()],
            "units": [{"id": u.id, "name": u.обозначение} for u in db.query(UnitOfMeasure).order_by(UnitOfMeasure.id).all()],
            "subjects": [{"id": s.id, "name": s.наименование} for s in db.query(Subject).order_by(Subject.id).all()],
        }

    def _names(self, db: Session) -> Dict[str, Dict[int, str]]:
        cls = {c.id: c.название for c in db.query(Classificator).all()}
        quals = {q["id"]: q["name"] for q in self._qualifications(db)}
        grc = {g.id: f"{g.код} {g.наименование}" for g in db.query(WorkCenter).all()}
        units = {u.id: u.обозначение for u in db.query(UnitOfMeasure).all()}
        prods = {p.id: p for p in db.query(Product).all()}
        tps = {t.id: f"{t.обозначение} {t.наименование}" for t in db.query(TypicalProcess).all()}
        return {"cls": cls, "qual": quals, "grc": grc, "unit": units, "prod": prods, "tp": tps}

    # ------------------------------------------------------------ ГРЦ
    def get_work_centers(self, db: Session) -> List[Dict[str, Any]]:
        n = self._names(db)
        subj = {s.id: s.наименование for s in db.query(Subject).all()}
        used = dict(db.execute(text('SELECT "грц_id", count(*) FROM "изделие_операция" WHERE "грц_id" IS NOT NULL GROUP BY 1')).all())
        used_t = dict(db.execute(text('SELECT "грц_id", count(*) FROM "типовая_операция" WHERE "грц_id" IS NOT NULL GROUP BY 1')).all())
        return [{"id": g.id, "код": g.код, "наименование": g.наименование, "класс_id": g.класс_id,
                 "класс": n["cls"].get(g.класс_id), "субъект_id": g.субъект_id, "подразделение": subj.get(g.субъект_id),
                 "количество_ед": g.количество_ед, "ставка_часа": g.ставка_часа,
                 "операций": used.get(g.id, 0) + used_t.get(g.id, 0)}
                for g in db.query(WorkCenter).order_by(WorkCenter.код).all()]

    def save_work_center(self, db: Session, wc_id: Optional[int], data: Dict[str, Any]) -> Dict[str, Any]:
        code, name = (data.get("код") or "").strip(), (data.get("наименование") or "").strip()
        if not code or not name:
            raise RoutingError("Укажите код и наименование ГРЦ")
        if (data.get("количество_ед") or 0) < 1:
            raise RoutingError("Количество единиц оборудования должно быть не меньше 1")
        if (data.get("ставка_часа") or 0) < 0:
            raise RoutingError("Стоимость машино-часа не может быть отрицательной")
        dup = db.query(WorkCenter).filter(WorkCenter.код == code, WorkCenter.id != (wc_id or 0)).first()
        if dup:
            raise RoutingError(f"ГРЦ с кодом «{code}» уже существует")
        g = db.get(WorkCenter, wc_id) if wc_id else WorkCenter()
        if wc_id and not g:
            raise RoutingError("ГРЦ не найден")
        g.код, g.наименование = code, name
        g.класс_id, g.субъект_id = data.get("класс_id"), data.get("субъект_id")
        g.количество_ед, g.ставка_часа = data.get("количество_ед") or 1, data.get("ставка_часа") or 0
        db.add(g)
        db.commit()
        return {"success": True, "message": "ГРЦ сохранён", "id": g.id}

    def delete_work_center(self, db: Session, wc_id: int) -> Dict[str, Any]:
        g = db.get(WorkCenter, wc_id)
        if not g:
            raise RoutingError("ГРЦ не найден")
        n = db.query(ProductOperation).filter(ProductOperation.грц_id == wc_id).count()
        if n:
            raise RoutingError(f"ГРЦ используется в {n} операциях маршрутов")
        db.delete(g)
        db.commit()
        return {"success": True, "message": "ГРЦ удалён"}

    # ------------------------------------------------------------ инструмент
    def get_tools(self, db: Session) -> List[Dict[str, Any]]:
        n = self._names(db)
        used = dict(db.execute(text('SELECT "инструмент_id", count(*) FROM "инструмент_операции" GROUP BY 1')).all())
        return [{"id": t.id, "обозначение": t.обозначение, "наименование": t.наименование, "вид": t.вид,
                 "класс_id": t.класс_id, "класс": n["cls"].get(t.класс_id), "операций": used.get(t.id, 0)}
                for t in db.query(Tool).order_by(Tool.обозначение).all()]

    def save_tool(self, db: Session, tool_id: Optional[int], data: Dict[str, Any]) -> Dict[str, Any]:
        code, name = (data.get("обозначение") or "").strip(), (data.get("наименование") or "").strip()
        if not code or not name:
            raise RoutingError("Укажите обозначение и наименование")
        if data.get("вид") not in ("ИНСТРУМЕНТ", "ОСНАСТКА"):
            raise RoutingError("Вид: ИНСТРУМЕНТ или ОСНАСТКА")
        if db.query(Tool).filter(Tool.обозначение == code, Tool.id != (tool_id or 0)).first():
            raise RoutingError(f"Инструмент с обозначением «{code}» уже существует")
        t = db.get(Tool, tool_id) if tool_id else Tool()
        if tool_id and not t:
            raise RoutingError("Инструмент не найден")
        t.обозначение, t.наименование, t.вид, t.класс_id = code, name, data["вид"], data.get("класс_id")
        db.add(t)
        db.commit()
        return {"success": True, "message": "Инструмент сохранён", "id": t.id}

    def delete_tool(self, db: Session, tool_id: int) -> Dict[str, Any]:
        t = db.get(Tool, tool_id)
        if not t:
            raise RoutingError("Инструмент не найден")
        n = db.query(OperationTool).filter(OperationTool.инструмент_id == tool_id).count()
        if n:
            raise RoutingError(f"Инструмент назначен {n} операциям")
        db.delete(t)
        db.commit()
        return {"success": True, "message": "Инструмент удалён"}

    # ------------------------------------------------------------ изделия и маршрут
    def get_products(self, db: Session) -> List[Dict[str, Any]]:
        stats = {r[0]: r[1:] for r in db.execute(text("""
            SELECT "изделие_id", count(*), bool_or("вид" = 'ЗАКУПКА'), count("типовой_тп_id")
            FROM "изделие_операция" GROUP BY 1""")).all()}
        units = {u.id: u.обозначение for u in db.query(UnitOfMeasure).all()}
        res = []
        order = {"КОМПЛЕКС": 0, "УЗЕЛ": 1, "ДЕТАЛЬ": 2, "КОМПЛЕКТУЮЩЕЕ": 3, "МАТЕРИАЛ": 4}
        for p in db.query(Product).all():
            cnt, purchase, typ = stats.get(p.id, (0, False, 0))
            res.append({"id": p.id, "наименование": p.наименование, "артикул": p.артикул,
                        "тип_изделия": p.тип_изделия, "ед_изм": units.get(p.ед_изм_id),
                        "операций": cnt, "закупка": bool(purchase), "типовых": typ})
        res.sort(key=lambda x: (order.get(x["тип_изделия"], 9), x["наименование"], x["id"]))
        return res

    def _param_values(self, op: ProductOperation) -> Dict[int, float]:
        return {v.параметр_id: v.значение for v in op.param_values}

    def _op_dict(self, db: Session, op: ProductOperation, n: Dict[str, Dict]) -> Dict[str, Any]:
        d = {"id": op.id, "изделие_id": op.изделие_id, "номер": op.номер, "вид": op.вид,
             "наименование": op.наименование, "класс_то_id": op.класс_то_id, "класс_то": n["cls"].get(op.класс_то_id),
             "грц_id": op.грц_id, "грц": n["grc"].get(op.грц_id), "профессия_id": op.профессия_id,
             "профессия": n["cls"].get(op.профессия_id), "квалификация_id": op.квалификация_id,
             "квалификация": n["qual"].get(op.квалификация_id), "тпз": op.тпз, "тшт": op.тшт, "цена": op.цена,
             "ед_изм_id": op.ед_изм_id, "ед_изм": n["unit"].get(op.ед_изм_id), "типовой_тп_id": op.типовой_тп_id,
             "типовой_тп": n["tp"].get(op.типовой_тп_id), "примечание": op.примечание,
             "закупка": op.is_purchase()}
        d["inputs"] = []
        for r in op.inputs:
            ip = r.input_op
            p = n["prod"].get(ip.изделие_id)
            d["inputs"].append({"id": r.id, "вход_id": r.вход_id, "изделие_id": ip.изделие_id,
                                "изделие": p.наименование if p else "?", "артикул": p.артикул if p else None,
                                "после_операции": "закупки" if ip.is_purchase() else f"{ip.номер:03d} {ip.наименование}", "вид_входа": ip.вид,
                                "норма": r.норма, "для_количества": r.для_количества, "ед_изм_id": r.ед_изм_id,
                                "ед_изм": n["unit"].get(r.ед_изм_id), "источник": r.источник})
        d["tools"] = [{"id": t.id, "инструмент_id": t.инструмент_id, "обозначение": t.tool.обозначение,
                       "наименование": t.tool.наименование, "вид": t.tool.вид, "количество": t.количество}
                      for t in op.tools]
        if op.типовой_тп_id:
            fw = self.flyweights.get(db, op.типовой_тп_id)
            vals = self._param_values(op)
            d["параметры"] = [{"id": p.id, "обозначение": p.code, "наименование": p.name, "ед_изм": p.unit,
                               "значение": vals.get(p.id, p.default), "мин": p.min_value, "макс": p.max_value}
                              for p in fw.params]
            d["типовые_операции"] = [dict(o, класс_то=n["cls"].get(o["класс_то_id"]), грц=n["grc"].get(o["грц_id"]),
                                          профессия=n["cls"].get(o["профессия_id"]),
                                          квалификация=n["qual"].get(o["квалификация_id"]))
                                     for o in fw.operations_for(vals)]
            d["типовые_ресурсы"] = [dict(r, изделие=n["prod"][r["изделие_id"]].наименование,
                                         ед_изм=n["unit"].get(r["ед_изм_id"])) for r in fw.resources_for(vals)]
            d["тшт_итого"] = fw.piece_time(vals)
            d["тпз_итого"] = sum(o["тпз"] for o in d["типовые_операции"])
        else:
            d["тшт_итого"], d["тпз_итого"] = op.тшт, op.тпз
        return d

    def get_route(self, db: Session, product_id: int) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        if not p:
            raise RoutingError("Изделие не найдено")
        n = self._names(db)
        ops = db.query(ProductOperation).filter(ProductOperation.изделие_id == product_id) \
            .order_by(ProductOperation.номер).all()
        used_by = db.execute(text("""
            SELECT DISTINCT o."изделие_id", pr."наименование" FROM "входной_ресурс" r
            JOIN "изделие_операция" i ON i.id = r."вход_id" JOIN "изделие_операция" o ON o.id = r."выход_id"
            JOIN "изделие" pr ON pr.id = o."изделие_id" WHERE i."изделие_id" = :p"""), {"p": product_id}).all()
        bom_cnt = db.query(BOMItem).filter(BOMItem.изделие_id == product_id).count()
        return {"product": {"id": p.id, "наименование": p.наименование, "артикул": p.артикул,
                            "тип_изделия": p.тип_изделия, "ед_изм": n["unit"].get(p.ед_изм_id),
                            "класс": n["cls"].get(p.класс_id), "позиций_спецификации": bom_cnt},
                "operations": [self._op_dict(db, o, n) for o in ops],
                "used_by": [{"id": r[0], "наименование": r[1]} for r in used_by]}

    def _check_refs(self, db: Session, data: Dict[str, Any]) -> None:
        if data.get("квалификация_id"):
            if data["квалификация_id"] not in {q["id"] for q in self._qualifications(db)}:
                raise RoutingError("Квалификация не найдена в перечислении «Квалификация (разряд)»")
        for key, root in (("класс_то_id", ROOT_OPERATIONS), ("профессия_id", ROOT_PROFESSIONS)):
            if data.get(key) and data[key] not in {c["id"] for c in self._subtree(db, root, False)}:
                raise RoutingError(f"Значение поля «{key}» не входит в классификатор «{root}»")
        if data.get("грц_id") and not db.get(WorkCenter, data["грц_id"]):
            raise RoutingError("ГРЦ не найден")

    def add_operation(self, db: Session, product_id: int, kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        if not p:
            raise RoutingError("Изделие не найдено")
        existing = db.query(ProductOperation).filter(ProductOperation.изделие_id == product_id).all()
        if kind == "ТЕХ" and p.тип_изделия == "МАТЕРИАЛ":
            raise RoutingError("Материал не изготавливается на предприятии — используйте позицию закупки")
        if kind == "ЗАКУПКА" and existing:
            raise RoutingError("Позиция закупки возможна только для изделия без маршрута изготовления")
        if kind == "ТЕХ" and any(o.is_purchase() for o in existing):
            raise RoutingError("Изделие закупается — удалите позицию закупки, чтобы описать изготовление")
        num = data.get("номер") or (max([o.номер for o in existing], default=0) + 10 if kind == "ТЕХ" else 1)
        if num <= 0:
            raise RoutingError("Номер операции должен быть положительным")
        if any(o.номер == num for o in existing):
            raise RoutingError(f"Операция с номером {num:03d} уже есть в маршруте")
        self._check_refs(db, data)
        name = (data.get("наименование") or "").strip() or ("Закупка" if kind == "ЗАКУПКА" else "")
        if not name:
            raise RoutingError("Укажите наименование операции (состояние изделия после неё)")
        if kind == "ЗАКУПКА" and not data.get("класс_то_id"):
            purchase_cls = db.query(Classificator).filter(Classificator.название == OP_PURCHASE_CLASS).first()
            data["класс_то_id"] = purchase_cls.id if purchase_cls else None
        op = ProductOperationFactory.create(
            kind, изделие_id=product_id, номер=num, наименование=name, класс_то_id=data.get("класс_то_id"),
            грц_id=data.get("грц_id"), профессия_id=data.get("профессия_id"),
            квалификация_id=data.get("квалификация_id"), тпз=data.get("тпз") or 0.0, тшт=data.get("тшт") or 0.0,
            цена=data.get("цена"), ед_изм_id=data.get("ед_изм_id") or p.ед_изм_id, примечание=data.get("примечание"))
        db.add(op)
        db.commit()
        return {"success": True, "message": f"Операция {num:03d} «{name}» добавлена", "id": op.id}

    def update_operation(self, db: Session, op_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        op = db.get(ProductOperation, op_id)
        if not op:
            raise RoutingError("Операция не найдена")
        num = data.get("номер") or op.номер
        if num <= 0:
            raise RoutingError("Номер операции должен быть положительным")
        if db.query(ProductOperation).filter(ProductOperation.изделие_id == op.изделие_id,
                                             ProductOperation.номер == num, ProductOperation.id != op.id).first():
            raise RoutingError(f"Операция с номером {num:03d} уже есть в маршруте")
        self._check_refs(db, data)
        if (data.get("тпз") or 0) < 0 or (data.get("тшт") or 0) < 0 or (data.get("цена") or 0) < 0:
            raise RoutingError("Нормы времени и цена не могут быть отрицательными")
        name = (data.get("наименование") or "").strip()
        if not name:
            raise RoutingError("Укажите наименование операции")
        op.номер, op.наименование, op.примечание = num, name, data.get("примечание")
        if op.is_purchase():
            op.цена, op.ед_изм_id = data.get("цена") or 0.0, data.get("ед_изм_id") or op.ед_изм_id
        else:
            if not data.get("класс_то_id") and not op.типовой_тп_id:
                raise RoutingError("Укажите класс технологической операции")
            op.класс_то_id, op.грц_id = data.get("класс_то_id"), data.get("грц_id")
            op.профессия_id, op.квалификация_id = data.get("профессия_id"), data.get("квалификация_id")
            op.тпз, op.тшт = data.get("тпз") or 0.0, data.get("тшт") or 0.0
        db.commit()
        return {"success": True, "message": "Операция сохранена"}

    def delete_operation(self, db: Session, op_id: int) -> Dict[str, Any]:
        op = db.get(ProductOperation, op_id)
        if not op:
            raise RoutingError("Операция не найдена")
        users = db.query(InputResource).filter(InputResource.вход_id == op_id).count()
        if users:
            raise RoutingError(f"Результат операции используется как входной ресурс в {users} операциях других изделий")
        db.delete(op)
        db.commit()
        return {"success": True, "message": "Операция удалена"}

    # ------------------------------------------------------------ входные ресурсы и инструмент
    def _route_contains(self, db: Session, root_product: int, product: int) -> bool:
        return db.execute(text("SELECT 1 FROM find_tm(:r) WHERE изделие_id = :p LIMIT 1"),
                          {"r": root_product, "p": product}).first() is not None

    def add_input(self, db: Session, op_id: int, input_op_id: int, норма: float, для_количества: float = 1.0,
                  ед_изм_id: Optional[int] = None, источник: str = "ВРУЧНУЮ") -> Dict[str, Any]:
        out = db.get(ProductOperation, op_id)
        inp = db.get(ProductOperation, input_op_id)
        if not out or not inp:
            raise RoutingError("Операция не найдена")
        if out.is_purchase():
            raise RoutingError("У позиции закупки не бывает входных ресурсов")
        if inp.изделие_id == out.изделие_id:
            raise RoutingError("Операции одного изделия выполняются последовательно по номерам — "
                               "входным ресурсом может быть только другое изделие")
        if норма is None or норма <= 0 or для_количества is None or для_количества <= 0:
            raise RoutingError("Норма расхода и «для количества» должны быть больше нуля")
        if self._route_contains(db, inp.изделие_id, out.изделие_id):
            raise RoutingError("Циклическая ссылка: изделие уже входит в маршрут входного ресурса")
        if db.query(InputResource).join(ProductOperation, ProductOperation.id == InputResource.вход_id) \
                .filter(InputResource.выход_id == op_id, ProductOperation.изделие_id == inp.изделие_id).first():
            raise RoutingError("Изделие уже назначено входным ресурсом этой операции — измените его норму")
        r = InputResource(выход_id=op_id, вход_id=input_op_id, норма=норма, для_количества=для_количества,
                          ед_изм_id=ед_изм_id or inp.ед_изм_id or (inp.product.ед_изм_id if inp.product else None),
                          источник=источник)
        db.add(r)
        db.commit()
        return {"success": True, "message": f"Входной ресурс «{inp.product.наименование}» добавлен", "id": r.id}

    def update_input(self, db: Session, input_id: int, норма: float, для_количества: float,
                     ед_изм_id: Optional[int]) -> Dict[str, Any]:
        r = db.get(InputResource, input_id)
        if not r:
            raise RoutingError("Входной ресурс не найден")
        if норма is None or норма <= 0 or для_количества is None or для_количества <= 0:
            raise RoutingError("Норма расхода и «для количества» должны быть больше нуля")
        r.норма, r.для_количества, r.ед_изм_id = норма, для_количества, ед_изм_id
        db.commit()
        return {"success": True, "message": "Норма расхода изменена"}

    def delete_input(self, db: Session, input_id: int) -> Dict[str, Any]:
        r = db.get(InputResource, input_id)
        if not r:
            raise RoutingError("Входной ресурс не найден")
        db.delete(r)
        db.commit()
        return {"success": True, "message": "Входной ресурс удалён"}

    def add_tool(self, db: Session, op_id: int, tool_id: int, qty: int = 1) -> Dict[str, Any]:
        op, tool = db.get(ProductOperation, op_id), db.get(Tool, tool_id)
        if not op or not tool:
            raise RoutingError("Операция или инструмент не найдены")
        if op.is_purchase():
            raise RoutingError("Для позиции закупки инструмент не назначается")
        if qty < 1:
            raise RoutingError("Количество должно быть не меньше 1")
        if db.query(OperationTool).filter(OperationTool.операция_id == op_id, OperationTool.инструмент_id == tool_id).first():
            raise RoutingError("Инструмент уже назначен операции")
        db.add(OperationTool(операция_id=op_id, инструмент_id=tool_id, количество=qty))
        db.commit()
        return {"success": True, "message": f"«{tool.наименование}» назначен операции"}

    def delete_tool_link(self, db: Session, link_id: int) -> Dict[str, Any]:
        t = db.get(OperationTool, link_id)
        if not t:
            raise RoutingError("Назначение не найдено")
        db.delete(t)
        db.commit()
        return {"success": True, "message": "Инструмент снят с операции"}

    # ------------------------------------------------------------ применение типового ТП (Flyweight)
    def apply_typical(self, db: Session, op_id: int, tp_id: int, values: Dict[int, float]) -> Dict[str, Any]:
        op = db.get(ProductOperation, op_id)
        if not op or op.is_purchase():
            raise RoutingError("Типовой ТП применяется к операции тех-маршрута")
        fw = self.flyweights.get(db, tp_id)
        values = {int(k): float(v) for k, v in (values or {}).items() if v is not None and v != ""}
        fw.validate(values)
        for r in fw.resources:   # у материалов типового ТП должна быть позиция закупки
            self.ensure_purchase(db, r.product_id)
        op.типовой_тп_id = tp_id
        op.тпз, op.тшт = 0.0, 0.0     # нормы времени берутся из типового ТП
        if not op.класс_то_id:
            op.класс_то_id = db.get(TypicalProcess, tp_id).класс_то_id
        for v in list(op.param_values):
            db.delete(v)
        db.flush()
        for p in fw.params:
            db.add(TypicalParamValue(операция_id=op.id, параметр_id=p.id, значение=values.get(p.id, p.default)))
        db.commit()
        return {"success": True, "message": f"Применён типовой ТП «{fw.name}»"}

    def remove_typical(self, db: Session, op_id: int) -> Dict[str, Any]:
        op = db.get(ProductOperation, op_id)
        if not op or not op.типовой_тп_id:
            raise RoutingError("У операции нет типового ТП")
        fw = self.flyweights.get(db, op.типовой_тп_id)
        vals = self._param_values(op)
        op.тпз = sum(o["тпз"] for o in fw.operations_for(vals))      # фиксируем нормы как собственные
        op.тшт = fw.piece_time(vals)
        op.типовой_тп_id = None
        for v in list(op.param_values):
            db.delete(v)
        db.commit()
        return {"success": True, "message": "Типовой ТП отвязан, нормы времени сохранены в операции"}

    def ensure_purchase(self, db: Session, product_id: int) -> Optional[int]:
        """Позиция закупки для материала/комплектующего без маршрута (создаётся с нулевой ценой)"""
        if db.query(ProductOperation).filter(ProductOperation.изделие_id == product_id).first():
            return None
        p = db.get(Product, product_id)
        if p.тип_изделия not in ("МАТЕРИАЛ", "КОМПЛЕКТУЮЩЕЕ"):
            return None
        r = self.add_operation(db, product_id, "ЗАКУПКА", {"наименование": "Закупка", "цена": 0.0})
        return r["id"]

    # ------------------------------------------------------------ формирование по спецификации (задание 5)
    def build_from_bom(self, db: Session, product_id: int, op_id: Optional[int] = None) -> Dict[str, Any]:
        """Формирование сети И-О: компоненты действующей спецификации становятся входными ресурсами операции"""
        p = db.get(Product, product_id)
        if not p:
            raise RoutingError("Изделие не найдено")
        ops = db.query(RoutePosition).filter(RoutePosition.изделие_id == product_id).order_by(RoutePosition.номер).all()
        if not ops:
            raise RoutingError("Сначала добавьте в маршрут хотя бы одну операцию изготовления")
        target = db.get(ProductOperation, op_id) if op_id else ops[0]
        if not target or target.изделие_id != product_id or target.is_purchase():
            raise RoutingError("Операция-получатель не найдена в маршруте изделия")
        covered = set()
        if target.типовой_тп_id:
            covered = {r.product_id for r in self.flyweights.get(db, target.типовой_тп_id).resources}
        spec = db.execute(text("SELECT * FROM bom_effective(:p)"), {"p": product_id}).mappings().all()
        if not spec:
            raise RoutingError("У изделия нет спецификации (задание 5)")
        report = {"добавлено": [], "обновлено": [], "пропущено": []}
        for s in spec:
            comp = db.get(Product, s["компонент_id"])
            if comp.id in covered:
                report["пропущено"].append(f"{comp.наименование}: норма задана типовым ТП")
                continue
            self.ensure_purchase(db, comp.id)
            final_id = db.execute(text("SELECT tm_final_op(:p)"), {"p": comp.id}).scalar()
            if not final_id:
                report["пропущено"].append(f"{comp.наименование}: нет маршрута изготовления")
                continue
            # компонент уже назначен входным ресурсом какой-либо операции изделия (возможно, после другой
            # операции компонента) — обновляем норму на месте, а не дублируем потребность
            route_ops = [o.id for o in ops]
            ex = db.query(InputResource).join(ProductOperation, ProductOperation.id == InputResource.вход_id) \
                .filter(InputResource.выход_id.in_(route_ops), ProductOperation.изделие_id == comp.id).first()
            if ex:
                ex.вход_id = final_id
                ex.норма, ex.для_количества, ex.ед_изм_id = s["расход"], s["для_количества"], s["ед_изм_id"]
                ex.источник = "СПЕЦИФИКАЦИЯ"
                db.commit()
                report["обновлено"].append(comp.наименование)
            else:
                try:
                    self.add_input(db, target.id, final_id, s["расход"], s["для_количества"], s["ед_изм_id"], "СПЕЦИФИКАЦИЯ")
                    report["добавлено"].append(comp.наименование)
                except RoutingError as e:
                    db.rollback()
                    report["пропущено"].append(f"{comp.наименование}: {e}")
        msg = (f"Операция {target.номер:03d}: добавлено {len(report['добавлено'])}, "
               f"обновлено {len(report['обновлено'])}, пропущено {len(report['пропущено'])}")
        return {"success": True, "message": msg, **report}

    # ------------------------------------------------------------ расчёты (FIND_TM, MR_Q, SUM_MR, TR_TO)
    def find_tm(self, db: Session, product_id: int) -> Dict[str, Any]:
        p = db.get(Product, product_id)
        if not p:
            raise RoutingError("Изделие не найдено")
        n = self._names(db)
        rows = db.execute(text("SELECT * FROM find_tm(:p) ORDER BY путь, номер"), {"p": product_id}).mappings().all()
        ops = {o.id: o for o in db.query(ProductOperation).filter(
            ProductOperation.id.in_([r["операция_id"] for r in rows] or [0])).all()}
        # Компоновщик: строим дерево операций (узел) и закупок (лист)
        roots: List[RouteComponent] = []
        last_by_product: Dict[Tuple, RouteComponent] = {}
        nodes_by_op: Dict[int, List[RouteComponent]] = {}
        flat = []
        for r in rows:
            op = ops[r["операция_id"]]
            prod = n["prod"].get(r["изделие_id"])
            d = self._op_dict(db, op, n) if op.типовой_тп_id else None
            row = {"уровень": r["уровень"], "изделие_id": r["изделие_id"], "изделие": prod.наименование if prod else "?",
                   "артикул": prod.артикул if prod else None, "тип_изделия": prod.тип_изделия if prod else None,
                   "операция_id": op.id, "номер": op.номер, "вид": op.вид, "наименование": op.наименование,
                   "класс_то": n["cls"].get(op.класс_то_id), "грц": n["grc"].get(op.грц_id),
                   "профессия": n["cls"].get(op.профессия_id), "квалификация": n["qual"].get(op.квалификация_id),
                   "тпз": d["тпз_итого"] if d else op.тпз, "тшт_итого": d["тшт_итого"] if d else op.тшт,
                   "типовой_тп": n["tp"].get(op.типовой_тп_id), "цена": op.цена,
                   "количество": r["количество"], "ед_изм": n["unit"].get(prod.ед_изм_id) if prod else None,
                   "родитель_операция_id": r["родитель_операция_id"], "путь": list(r["путь"]),
                   "типовые_операции": d["типовые_операции"] if d else []}
            flat.append(row)
            node = PurchaseLeaf(row) if op.вид == "ЗАКУПКА" else RouteOperationNode(row)
            parent_id = r["родитель_операция_id"]
            parent_key = (tuple(r["путь"][:-1]), parent_id)
            parents = [x for x in nodes_by_op.get(parent_id, []) if tuple(x.row["путь"]) == tuple(r["путь"][:-1])]
            if parent_id is None or not parents:
                roots.append(node)
            else:
                parents[0].add(node)
            nodes_by_op.setdefault(op.id, []).append(node)
        tree = [x.to_dict() for x in roots]
        return {"success": True, "product": {"id": p.id, "наименование": p.наименование, "артикул": p.артикул},
                "rows": flat, "tree": tree, "строк": len(flat),
                "глубина": max([r["уровень"] for r in flat], default=0),
                "материалы_руб_на_ед": round(sum(x.material_cost() for x in roots), 4),
                "труд_мин_на_ед": round(sum(x.labor_minutes() for x in roots), 4)}

    def mr_q(self, db: Session, op_id: int, qty: float) -> Dict[str, Any]:
        op = db.get(ProductOperation, op_id)
        if not op:
            raise RoutingError("Операция не найдена")
        if qty is None or qty <= 0:
            raise RoutingError("Количество должно быть больше нуля")
        n = self._names(db)
        rows = db.execute(text("SELECT * FROM mr_q(:o, :q)"), {"o": op_id, "q": qty}).mappings().all()
        return {"success": True, "операция": f"{op.номер:03d} {op.наименование}", "количество": qty,
                "items": [{"изделие_id": r["изделие_id"], "изделие": n["prod"][r["изделие_id"]].наименование,
                           "артикул": n["prod"][r["изделие_id"]].артикул, "вид_входа": r["вид"],
                           "норма": r["норма"], "для_количества": r["для_количества"], "количество": r["количество"],
                           "ед_изм": n["unit"].get(r["ед_изм_id"]), "источник": r["источник"]} for r in rows]}

    def _check_qty(self, db: Session, product_id: int, qty: float) -> None:
        if not db.get(Product, product_id):
            raise RoutingError("Изделие не найдено")
        if qty is None or qty <= 0:
            raise RoutingError("Количество изделий должно быть больше нуля")

    def sum_mr(self, db: Session, product_id: int, qty: float) -> Dict[str, Any]:
        self._check_qty(db, product_id, qty)
        n = self._names(db)
        rows = db.execute(text("SELECT * FROM sum_mr(:p, :q)"), {"p": product_id, "q": qty}).mappings().all()
        items = [{"изделие_id": r["изделие_id"], "изделие": n["prod"][r["изделие_id"]].наименование,
                  "артикул": n["prod"][r["изделие_id"]].артикул, "тип_изделия": n["prod"][r["изделие_id"]].тип_изделия,
                  "ед_изм": n["unit"].get(r["ед_изм_id"]), "норма_на_единицу": r["норма_на_единицу"],
                  "количество": r["количество"], "цена": r["цена"], "стоимость": r["стоимость"],
                  "вхождений": r["вхождений"]} for r in rows]
        items.sort(key=lambda x: (x["тип_изделия"] != "МАТЕРИАЛ", -x["стоимость"]))
        return {"success": True, "количество": qty, "items": items, "итого": sum(i["стоимость"] for i in items)}

    def tr_to(self, db: Session, product_id: int, qty: float) -> Dict[str, Any]:
        self._check_qty(db, product_id, qty)
        n = self._names(db)
        rows = db.execute(text("SELECT * FROM tr_to(:p, :q)"), {"p": product_id, "q": qty}).mappings().all()
        items = [{"профессия": n["cls"].get(r["профессия_id"]) or "—", "квалификация": n["qual"].get(r["квалификация_id"]) or "—",
                  "операций": r["операций"], "трудоемкость_ч": r["трудоемкость_ч"], "ставка": r["ставка"],
                  "стоимость": r["стоимость"]} for r in rows]
        items.sort(key=lambda x: -x["трудоемкость_ч"])
        load = db.execute(text("SELECT * FROM grc_load(:p, :q)"), {"p": product_id, "q": qty}).mappings().all()
        wc = {g.id: g for g in db.query(WorkCenter).all()}
        grc = [{"грц": n["grc"].get(r["грц_id"]), "операций": r["операций"], "машино_часы": r["машино_часы"],
                "ставка": r["ставка"], "стоимость": r["стоимость"],
                "фонд_ч_в_смену": (wc[r["грц_id"]].количество_ед * 8) if r["грц_id"] in wc else None}
               for r in load]
        grc.sort(key=lambda x: -x["машино_часы"])
        return {"success": True, "количество": qty, "items": items, "грц": grc,
                "итого_ч": sum(i["трудоемкость_ч"] for i in items), "итого_руб": sum(i["стоимость"] for i in items)}

    def calc_cost(self, db: Session, product_id: int, qty: float) -> Dict[str, Any]:
        self._check_qty(db, product_id, qty)
        rows = db.execute(text("SELECT * FROM calc_cost(:p, :q)"), {"p": product_id, "q": qty}).mappings().all()
        return {"success": True, "количество": qty,
                "items": [{"статья": r["статья"], "сумма": r["сумма"], "на_единицу": r["на_единицу"]} for r in rows]}

    # ------------------------------------------------------------ типовые ТП (CRUD)
    def get_typicals(self, db: Session) -> List[Dict[str, Any]]:
        n = self._names(db)
        usage = dict(db.execute(text('SELECT "типовой_тп_id", count(*) FROM "изделие_операция" '
                                     'WHERE "типовой_тп_id" IS NOT NULL GROUP BY 1')).all())
        return [{"id": t.id, "обозначение": t.обозначение, "наименование": t.наименование,
                 "класс_то": n["cls"].get(t.класс_то_id), "описание": t.описание,
                 "параметров": len(t.params), "операций": len(t.operations), "ресурсов": len(t.resources),
                 "применений": usage.get(t.id, 0)} for t in db.query(TypicalProcess).order_by(TypicalProcess.обозначение).all()]

    def get_typical(self, db: Session, tp_id: int) -> Dict[str, Any]:
        t = db.get(TypicalProcess, tp_id)
        if not t:
            raise RoutingError("Типовой ТП не найден")
        n = self._names(db)
        pname = {p.id: p.обозначение for p in t.params}
        uses = db.execute(text("""
            SELECT o.id, o."номер", o."наименование", p.id, p."наименование", p."артикул"
            FROM "изделие_операция" o JOIN "изделие" p ON p.id = o."изделие_id"
            WHERE o."типовой_тп_id" = :t ORDER BY p."наименование" """), {"t": tp_id}).all()
        vals = {}
        for v in db.query(TypicalParamValue).join(TypicalParam).filter(TypicalParam.тп_id == tp_id).all():
            vals.setdefault(v.операция_id, {})[pname.get(v.параметр_id, "?")] = v.значение
        return {"id": t.id, "обозначение": t.обозначение, "наименование": t.наименование,
                "класс_то_id": t.класс_то_id, "класс_то": n["cls"].get(t.класс_то_id), "описание": t.описание,
                "params": [{"id": p.id, "обозначение": p.обозначение, "наименование": p.наименование, "ед_изм": p.ед_изм,
                            "мин": p.мин_значение, "макс": p.макс_значение, "по_умолчанию": p.по_умолчанию} for p in t.params],
                "operations": [{"id": o.id, "номер": o.номер, "наименование": o.наименование,
                                "класс_то_id": o.класс_то_id, "класс_то": n["cls"].get(o.класс_то_id),
                                "грц_id": o.грц_id, "грц": n["grc"].get(o.грц_id), "профессия_id": o.профессия_id,
                                "профессия": n["cls"].get(o.профессия_id), "квалификация_id": o.квалификация_id,
                                "квалификация": n["qual"].get(o.квалификация_id), "тпз": o.тпз, "тшт_база": o.тшт_база,
                                "тшт_коэф": o.тшт_коэф, "параметр_id": o.параметр_id, "параметр": pname.get(o.параметр_id)}
                               for o in t.operations],
                "resources": [{"id": r.id, "изделие_id": r.изделие_id, "изделие": r.product.наименование,
                               "артикул": r.product.артикул, "норма_база": r.норма_база, "норма_коэф": r.норма_коэф,
                               "параметр_id": r.параметр_id, "параметр": pname.get(r.параметр_id),
                               "ед_изм_id": r.ед_изм_id, "ед_изм": n["unit"].get(r.ед_изм_id)} for r in t.resources],
                "uses": [{"операция_id": u[0], "номер": u[1], "операция": u[2], "изделие_id": u[3], "изделие": u[4],
                          "артикул": u[5], "значения": vals.get(u[0], {})} for u in uses]}

    def save_typical(self, db: Session, tp_id: Optional[int], data: Dict[str, Any]) -> Dict[str, Any]:
        code, name = (data.get("обозначение") or "").strip(), (data.get("наименование") or "").strip()
        if not code or not name:
            raise RoutingError("Укажите обозначение и наименование типового ТП")
        if db.query(TypicalProcess).filter(TypicalProcess.обозначение == code, TypicalProcess.id != (tp_id or 0)).first():
            raise RoutingError(f"Типовой ТП «{code}» уже существует")
        t = db.get(TypicalProcess, tp_id) if tp_id else TypicalProcess()
        if tp_id and not t:
            raise RoutingError("Типовой ТП не найден")
        t.обозначение, t.наименование = code, name
        t.класс_то_id, t.описание = data.get("класс_то_id"), data.get("описание")
        db.add(t)
        db.commit()
        self.flyweights.invalidate(t.id)
        return {"success": True, "message": "Типовой ТП сохранён", "id": t.id}

    def delete_typical(self, db: Session, tp_id: int) -> Dict[str, Any]:
        t = db.get(TypicalProcess, tp_id)
        if not t:
            raise RoutingError("Типовой ТП не найден")
        n = db.query(ProductOperation).filter(ProductOperation.типовой_тп_id == tp_id).count()
        if n:
            raise RoutingError(f"Типовой ТП применён в {n} операциях — сначала отвяжите его")
        db.delete(t)
        db.commit()
        self.flyweights.invalidate(tp_id)
        return {"success": True, "message": "Типовой ТП удалён"}

    def add_typical_param(self, db: Session, tp_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        if not db.get(TypicalProcess, tp_id):
            raise RoutingError("Типовой ТП не найден")
        code, name = (data.get("обозначение") or "").strip(), (data.get("наименование") or "").strip()
        if not code or not name:
            raise RoutingError("Укажите обозначение и наименование параметра")
        mn, mx, df = data.get("мин"), data.get("макс"), data.get("по_умолчанию")
        if mn is not None and mx is not None and mn > mx:
            raise RoutingError("Минимальное значение больше максимального")
        if df is not None and ((mn is not None and df < mn) or (mx is not None and df > mx)):
            raise RoutingError("Значение по умолчанию вне допустимого диапазона")
        if db.query(TypicalParam).filter(TypicalParam.тп_id == tp_id, TypicalParam.обозначение == code).first():
            raise RoutingError(f"Параметр «{code}» уже есть в типовом ТП")
        p = TypicalParam(тп_id=tp_id, обозначение=code, наименование=name, ед_изм=data.get("ед_изм"),
                         мин_значение=mn, макс_значение=mx, по_умолчанию=df)
        db.add(p)
        db.commit()
        self.flyweights.invalidate(tp_id)
        return {"success": True, "message": "Параметр добавлен", "id": p.id}

    def add_typical_operation(self, db: Session, tp_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        t = db.get(TypicalProcess, tp_id)
        if not t:
            raise RoutingError("Типовой ТП не найден")
        name = (data.get("наименование") or "").strip()
        if not name:
            raise RoutingError("Укажите наименование операции")
        num = data.get("номер") or (max([o.номер for o in t.operations], default=0) + 10)
        if any(o.номер == num for o in t.operations):
            raise RoutingError(f"Операция {num:03d} уже есть в типовом ТП")
        if min(data.get("тпз") or 0, data.get("тшт_база") or 0, data.get("тшт_коэф") or 0) < 0:
            raise RoutingError("Нормативы времени не могут быть отрицательными")
        if data.get("параметр_id") and data["параметр_id"] not in {p.id for p in t.params}:
            raise RoutingError("Параметр не принадлежит этому типовому ТП")
        self._check_refs(db, data)
        db.add(TypicalOperation(тп_id=tp_id, номер=num, наименование=name, класс_то_id=data.get("класс_то_id"),
                                грц_id=data.get("грц_id"), профессия_id=data.get("профессия_id"),
                                квалификация_id=data.get("квалификация_id"), тпз=data.get("тпз") or 0.0,
                                тшт_база=data.get("тшт_база") or 0.0, тшт_коэф=data.get("тшт_коэф") or 0.0,
                                параметр_id=data.get("параметр_id")))
        db.commit()
        self.flyweights.invalidate(tp_id)
        return {"success": True, "message": f"Типовая операция {num:03d} добавлена"}

    def add_typical_resource(self, db: Session, tp_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        t = db.get(TypicalProcess, tp_id)
        if not t:
            raise RoutingError("Типовой ТП не найден")
        p = db.get(Product, data.get("изделие_id") or 0)
        if not p:
            raise RoutingError("Выберите материал")
        if (data.get("норма_база") or 0) < 0 or (data.get("норма_коэф") or 0) < 0:
            raise RoutingError("Нормативы расхода не могут быть отрицательными")
        if not (data.get("норма_база") or data.get("норма_коэф")):
            raise RoutingError("Задайте базовую норму или коэффициент")
        if data.get("параметр_id") and data["параметр_id"] not in {x.id for x in t.params}:
            raise RoutingError("Параметр не принадлежит этому типовому ТП")
        db.add(TypicalResource(тп_id=tp_id, изделие_id=p.id, норма_база=data.get("норма_база") or 0.0,
                               норма_коэф=data.get("норма_коэф") or 0.0, параметр_id=data.get("параметр_id"),
                               ед_изм_id=data.get("ед_изм_id") or p.ед_изм_id))
        self.ensure_purchase(db, p.id)
        db.commit()
        self.flyweights.invalidate(tp_id)
        return {"success": True, "message": f"Ресурс «{p.наименование}» добавлен"}

    def delete_typical_item(self, db: Session, kind: str, item_id: int) -> Dict[str, Any]:
        model = {"param": TypicalParam, "operation": TypicalOperation, "resource": TypicalResource}.get(kind)
        if not model:
            raise RoutingError("Неизвестный элемент")
        obj = db.get(model, item_id)
        if not obj:
            raise RoutingError("Элемент не найден")
        tp_id = obj.тп_id
        db.delete(obj)
        db.commit()
        self.flyweights.invalidate(tp_id)
        return {"success": True, "message": "Удалено"}

    def preview_typical(self, db: Session, tp_id: int, values: Dict[int, float]) -> Dict[str, Any]:
        fw = self.flyweights.get(db, tp_id)
        values = {int(k): float(v) for k, v in values.items()}
        fw.validate(values)
        n = self._names(db)
        return {"operations": [dict(o, класс_то=n["cls"].get(o["класс_то_id"]), профессия=n["cls"].get(o["профессия_id"]),
                                    грц=n["grc"].get(o["грц_id"]), квалификация=n["qual"].get(o["квалификация_id"]))
                               for o in fw.operations_for(values)],
                "resources": [dict(r, изделие=n["prod"][r["изделие_id"]].наименование, ед_изм=n["unit"].get(r["ед_изм_id"]))
                              for r in fw.resources_for(values)],
                "тшт_итого": fw.piece_time(values)}

    def flyweight_stats(self, db: Session) -> Dict[str, Any]:
        uses = db.query(ProductOperation).filter(ProductOperation.типовой_тп_id.isnot(None)).count()
        typical_rows = db.query(TypicalOperation).count() + db.query(TypicalResource).count()
        per_use = db.execute(text("""
            SELECT COALESCE(sum((SELECT count(*) FROM "типовая_операция" t WHERE t."тп_id" = o."типовой_тп_id")
                              + (SELECT count(*) FROM "типовой_ресурс" r WHERE r."тп_id" = o."типовой_тп_id")), 0)
            FROM "изделие_операция" o WHERE o."типовой_тп_id" IS NOT NULL""")).scalar()
        values = db.query(TypicalParamValue).count()
        return {"типовых_тп": db.query(TypicalProcess).count(), "применений": uses,
                "строк_норм_хранится": typical_rows, "строк_без_приспособленца": int(per_use),
                "значений_параметров": values, "объектов_в_пуле": self.flyweights.size,
                "запросов_к_фабрике": self.flyweights.requests}


routing_service = RoutingService()
