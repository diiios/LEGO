# config_api.py
"""Задание 7 (усложнённый уровень). REST API «Заказы на изделия с вариантами исполнения и сложными ограничениями»"""
from datetime import date
from functools import wraps
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config_service import ConfigError, config_service as svc

router = APIRouter(prefix="/cfg", tags=["Заказы и конфигуратор"])

_get_db = None   # подставляется из main.py


def get_db():
    yield from _get_db()


def handle(fn):
    """Перевод исключений предметной области в HTTP 400"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        db = kwargs.get("db")
        try:
            return fn(*args, **kwargs)
        except ConfigError as e:
            if db is not None:
                db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except IntegrityError as e:
            if db is not None:
                db.rollback()
            raise HTTPException(status_code=400, detail=f"Нарушение целостности данных: {e.orig}")
    return wrapper


# ------------------------------------------------------------- схемы
class KindIn(BaseModel):
    вид_конфигурации: str = Field(..., description="ПРОСТОЕ или ТИПОВОЕ")
    цена: Optional[float] = Field(None, ge=0)


class ConfigParamIn(BaseModel):
    флаг_конфигурации: bool = True
    мин_значение: Optional[float] = None
    макс_значение: Optional[float] = None
    обязательный: Optional[bool] = None


class ConstraintIn(BaseModel):
    наименование: str = Field(..., min_length=1, max_length=200)
    выражение: Optional[str] = Field(None, description="Например: W <= L AND W * L <= 256")
    сообщение: Optional[str] = None
    активно: bool = True


class PriceIn(BaseModel):
    выражение: Optional[str] = Field(None, description="Например: (0.8 + 0.12 * W * L) * IF(цвет = 'Прозрачный', 1.3, 1)")
    цена: Optional[float] = Field(None, ge=0)


class ValuesIn(BaseModel):
    значения: Dict[int, Any] = Field(default_factory=dict, description="{id параметра: значение}; для перечисления – id значения")


class PreviewArgIn(BaseModel):
    имя: str
    тип_id: Optional[int] = None


class PreviewIn(BaseModel):
    выражение: str
    изделие_id: Optional[int] = Field(None, description="Типовое изделие, параметры которого доступны в выражении")
    значения: Dict[int, Any] = Field(default_factory=dict)
    аргументы: List[PreviewArgIn] = Field(default_factory=list, description="Формальные аргументы (для тела функции)")


class ArgIn(BaseModel):
    имя: str = Field(..., min_length=1, max_length=40)
    тип_id: int


class FunctionIn(BaseModel):
    обозначение: str = Field(..., min_length=1, max_length=40)
    наименование: str = Field(..., min_length=1, max_length=200)
    класс_id: int
    аргументы: List[ArgIn]
    тело: str = Field(..., description="Выражение над формальными аргументами, например: a / b >= lo AND a / b <= hi")
    описание: Optional[str] = None


class EvalIn(BaseModel):
    аргументы: List[Any] = Field(..., description="Значения формальных параметров по порядку; для перечисления – id значения")


class OrderIn(BaseModel):
    номер: Optional[str] = None
    заказчик_id: int
    дата_регистрации: Optional[date] = None
    срок_изготовления: Optional[date] = None
    контактное_лицо: Optional[str] = None
    телефон: Optional[str] = None
    примечание: Optional[str] = None


class StatusIn(BaseModel):
    статус: str = Field(..., description="ЧЕРНОВИК или СОГЛАСОВАН")


class ItemIn(BaseModel):
    изделие_id: int
    количество: float = Field(..., gt=0)


class ConfigureIn(BaseModel):
    изделие_id: int = Field(..., description="Типовое изделие (шаблон) или вариант исполнения – прототип")
    значения: Dict[int, Any] = Field(default_factory=dict)
    количество: float = Field(..., gt=0)


class QtyIn(BaseModel):
    количество: float = Field(..., gt=0)


# ------------------------------------------------------------- справочники и изделия
@router.get("/references", summary="Справочники: типы значений, классы функций, заказчики")
@handle
def references(db: Session = Depends(get_db)):
    return svc.references(db)


@router.get("/products", summary="Изделия с видом конфигурации (ПРОСТОЕ, ТИПОВОЕ, ВАРИАНТ) и ценой")
@handle
def products(вид: Optional[str] = None, db: Session = Depends(get_db)):
    return svc.products(db, вид)


@router.put("/products/{product_id}/kind", summary="Описание шаблона: сделать изделие типовым с конфигуратором или простым")
@handle
def set_kind(product_id: int, body: KindIn, db: Session = Depends(get_db)):
    return svc.set_kind(db, product_id, body.вид_конфигурации, body.цена)


# ------------------------------------------------------------- типовые изделия
@router.get("/templates", summary="Типовые изделия с конфигуратором")
@handle
def templates(db: Session = Depends(get_db)):
    return svc.templates(db)


@router.get("/templates/{product_id}", summary="Карточка типового изделия: параметры, ограничения, формула цены, варианты")
@handle
def template_card(product_id: int, db: Session = Depends(get_db)):
    return svc.template_card(db, product_id)


@router.get("/templates/{product_id}/config-params", summary="GET_CONFIG_PARAMS – параметры конфигурации типового изделия")
@handle
def config_params(product_id: int, db: Session = Depends(get_db)):
    return svc.config_params(db, product_id)


@router.put("/class-params/{pc_id}", summary="Описание состава параметров конфигурации: флаг и диапазон (мин, макс)")
@handle
def set_config_param(pc_id: int, body: ConfigParamIn, db: Session = Depends(get_db)):
    return svc.set_config_param(db, pc_id, body.флаг_конфигурации, body.мин_значение, body.макс_значение, body.обязательный)


@router.post("/templates/{product_id}/constraints", summary="Описать ограничение типового изделия (выражение разбирается в вызовы функций)")
@handle
def add_constraint(product_id: int, body: ConstraintIn, db: Session = Depends(get_db)):
    if not body.выражение:
        raise HTTPException(status_code=422, detail="Укажите выражение ограничения")
    return svc.add_constraint(db, product_id, body.наименование, body.выражение, body.сообщение)


@router.put("/constraints/{constraint_id}", summary="Изменить ограничение (имя, выражение, сообщение, активность)")
@handle
def update_constraint(constraint_id: int, body: ConstraintIn, db: Session = Depends(get_db)):
    return svc.update_constraint(db, constraint_id, body.наименование, body.выражение, body.сообщение, body.активно)


@router.delete("/constraints/{constraint_id}", summary="Удалить ограничение вместе с деревом вызовов")
@handle
def delete_constraint(constraint_id: int, db: Session = Depends(get_db)):
    return svc.delete_constraint(db, constraint_id)


@router.put("/templates/{product_id}/price-formula", summary="Задать формулу цены варианта исполнения")
@handle
def set_price_formula(product_id: int, body: PriceIn, db: Session = Depends(get_db)):
    return svc.set_price_formula(db, product_id, body.выражение, body.цена)


@router.post("/expressions/preview", summary="Разобрать выражение без сохранения: текст, дерево, тип, значение")
@handle
def preview(body: PreviewIn, db: Session = Depends(get_db)):
    return svc.preview(db, body.выражение, body.изделие_id, body.значения, [a.model_dump() for a in body.аргументы])


@router.post("/templates/{product_id}/check", summary="CHECK_CONSTRAINTS – проверка ограничений для значений параметров")
@handle
def check(product_id: int, body: ValuesIn, db: Session = Depends(get_db)):
    return svc.check(db, product_id, body.значения)


@router.post("/templates/{product_id}/variants",
             summary="CREATE_VARIANT – создать вариант исполнения (шаблон или вариант служит прототипом)")
@handle
def create_variant(product_id: int, body: ValuesIn, db: Session = Depends(get_db)):
    return svc.create_variant(db, product_id, body.значения)


@router.get("/variants/{variant_id}", summary="Вариант исполнения: значения параметров")
@handle
def variant_card(variant_id: int, db: Session = Depends(get_db)):
    return svc.variant_card(db, variant_id)


# ------------------------------------------------------------- библиотека функций
@router.get("/functions", summary="Библиотека функций ограничений (по классам функций)")
@handle
def functions(db: Session = Depends(get_db)):
    return svc.functions(db)


@router.post("/functions", summary="Добавить функцию с формальными параметрами (тело – выражение)")
@handle
def add_function(body: FunctionIn, db: Session = Depends(get_db)):
    return svc.add_function(db, body.обозначение, body.наименование, body.класс_id,
                            [a.model_dump() for a in body.аргументы], body.тело, body.описание)


@router.post("/functions/{function_id}/evaluate", summary="EVAL_FUNCTION – вычислить функцию для заданных значений аргументов")
@handle
def evaluate_function(function_id: int, body: EvalIn, db: Session = Depends(get_db)):
    return svc.evaluate_function(db, function_id, body.аргументы)


@router.delete("/functions/{function_id}", summary="Удалить составную функцию, если она не используется")
@handle
def delete_function(function_id: int, db: Session = Depends(get_db)):
    return svc.delete_function(db, function_id)


# ------------------------------------------------------------- заказы
@router.get("/orders", summary="Заказы с суммой")
@handle
def orders(db: Session = Depends(get_db)):
    return svc.orders(db)


@router.post("/orders", summary="Регистрация заказа")
@handle
def create_order(body: OrderIn, db: Session = Depends(get_db)):
    return svc.save_order(db, None, body.model_dump())


@router.get("/orders/{order_id}", summary="Состав заказа с вариантами исполнения и суммой")
@handle
def order_card(order_id: int, db: Session = Depends(get_db)):
    return svc.order_card(db, order_id)


@router.put("/orders/{order_id}", summary="Изменить реквизиты заказа")
@handle
def update_order(order_id: int, body: OrderIn, db: Session = Depends(get_db)):
    return svc.save_order(db, order_id, body.model_dump())


@router.put("/orders/{order_id}/status", summary="Согласовать заказ или вернуть в черновик")
@handle
def set_status(order_id: int, body: StatusIn, db: Session = Depends(get_db)):
    return svc.set_status(db, order_id, body.статус)


@router.delete("/orders/{order_id}", summary="Удалить заказ-черновик")
@handle
def delete_order(order_id: int, db: Session = Depends(get_db)):
    return svc.delete_order(db, order_id)


@router.post("/orders/{order_id}/items", summary="ADD_TO_ORDER – добавить изделие или вариант исполнения в заказ")
@handle
def add_item(order_id: int, body: ItemIn, db: Session = Depends(get_db)):
    return svc.add_item(db, order_id, body.изделие_id, body.количество)


@router.post("/orders/{order_id}/configure",
             summary="Задать вариант исполнения и добавить в заказ (CREATE_VARIANT + ADD_TO_ORDER)")
@handle
def configure_item(order_id: int, body: ConfigureIn, db: Session = Depends(get_db)):
    return svc.configure_item(db, order_id, body.изделие_id, body.значения, body.количество)


@router.put("/order-items/{item_id}", summary="Изменить количество в позиции заказа")
@handle
def update_item(item_id: int, body: QtyIn, db: Session = Depends(get_db)):
    return svc.update_item(db, item_id, body.количество)


@router.delete("/order-items/{item_id}", summary="Удалить позицию заказа")
@handle
def delete_item(item_id: int, db: Session = Depends(get_db)):
    return svc.delete_item(db, item_id)
