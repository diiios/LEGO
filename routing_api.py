# routing_api.py
"""Задание 6. REST API «Маршрутная технология изготовления изделий»"""
from functools import wraps
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routing_service import RoutingError, routing_service as svc

TAG = "Маршрутная технология"
router = APIRouter(prefix="/tm", tags=[TAG])

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
        except RoutingError as e:
            if db is not None:
                db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except IntegrityError as e:
            if db is not None:
                db.rollback()
            raise HTTPException(status_code=400, detail=f"Нарушение целостности данных: {e.orig}")
    return wrapper


# ------------------------------------------------------------- схемы
class WorkCenterIn(BaseModel):
    код: str = Field(..., min_length=1, max_length=20)
    наименование: str = Field(..., min_length=1, max_length=200)
    класс_id: Optional[int] = None
    субъект_id: Optional[int] = None
    количество_ед: int = Field(1, ge=1)
    ставка_часа: float = Field(0.0, ge=0)


class ToolIn(BaseModel):
    обозначение: str = Field(..., min_length=1, max_length=50)
    наименование: str = Field(..., min_length=1, max_length=200)
    вид: str = "ИНСТРУМЕНТ"
    класс_id: Optional[int] = None


class OperationIn(BaseModel):
    вид: str = Field("ТЕХ", description="ТЕХ — позиция тех-маршрута, ЗАКУПКА — позиция закупки")
    номер: Optional[int] = None
    наименование: Optional[str] = None
    класс_то_id: Optional[int] = None
    грц_id: Optional[int] = None
    профессия_id: Optional[int] = None
    квалификация_id: Optional[int] = None
    тпз: float = Field(0.0, ge=0, description="Подготовительно-заключительное время, мин на партию")
    тшт: float = Field(0.0, ge=0, description="Штучное время, мин на 1 изделие")
    цена: Optional[float] = Field(None, ge=0, description="Цена закупки за ЕИ")
    ед_изм_id: Optional[int] = None
    примечание: Optional[str] = None


class InputIn(BaseModel):
    вход_id: int = Field(..., description="Входная изделие-операция (обычно итоговая операция компонента)")
    норма: float = Field(..., gt=0)
    для_количества: float = Field(1.0, gt=0)
    ед_изм_id: Optional[int] = None


class InputUpdate(BaseModel):
    норма: float = Field(..., gt=0)
    для_количества: float = Field(1.0, gt=0)
    ед_изм_id: Optional[int] = None


class ToolLinkIn(BaseModel):
    инструмент_id: int
    количество: int = Field(1, ge=1)


class TypicalApply(BaseModel):
    тп_id: int
    значения: Dict[int, float] = Field(default_factory=dict, description="{параметр_id: значение}")


class TypicalIn(BaseModel):
    обозначение: str = Field(..., min_length=1, max_length=30)
    наименование: str = Field(..., min_length=1, max_length=200)
    класс_то_id: Optional[int] = None
    описание: Optional[str] = None


class TypicalParamIn(BaseModel):
    обозначение: str = Field(..., min_length=1, max_length=20)
    наименование: str = Field(..., min_length=1, max_length=100)
    ед_изм: Optional[str] = None
    мин: Optional[float] = None
    макс: Optional[float] = None
    по_умолчанию: Optional[float] = None


class TypicalOperationIn(BaseModel):
    номер: Optional[int] = None
    наименование: str
    класс_то_id: Optional[int] = None
    грц_id: Optional[int] = None
    профессия_id: Optional[int] = None
    квалификация_id: Optional[int] = None
    тпз: float = 0.0
    тшт_база: float = 0.0
    тшт_коэф: float = 0.0
    параметр_id: Optional[int] = None


class TypicalResourceIn(BaseModel):
    изделие_id: int
    норма_база: float = 0.0
    норма_коэф: float = 0.0
    параметр_id: Optional[int] = None
    ед_изм_id: Optional[int] = None


class PreviewIn(BaseModel):
    значения: Dict[int, float] = Field(default_factory=dict)


# ------------------------------------------------------------- справочники
@router.get("/references", summary="Справочники: классы ТО, профессии, квалификации, ГРЦ, инструмент")
@handle
def references(db: Session = Depends(get_db)):
    return svc.references(db)


@router.get("/work-centers", summary="ГРЦ — групповые рабочие центры")
@handle
def work_centers(db: Session = Depends(get_db)):
    return svc.get_work_centers(db)


@router.post("/work-centers", summary="Добавить ГРЦ")
@handle
def add_work_center(data: WorkCenterIn, db: Session = Depends(get_db)):
    return svc.save_work_center(db, None, data.model_dump())


@router.put("/work-centers/{wc_id}", summary="Изменить ГРЦ")
@handle
def update_work_center(wc_id: int, data: WorkCenterIn, db: Session = Depends(get_db)):
    return svc.save_work_center(db, wc_id, data.model_dump())


@router.delete("/work-centers/{wc_id}", summary="Удалить ГРЦ")
@handle
def delete_work_center(wc_id: int, db: Session = Depends(get_db)):
    return svc.delete_work_center(db, wc_id)


@router.get("/tools", summary="Инструмент и оснастка")
@handle
def tools(db: Session = Depends(get_db)):
    return svc.get_tools(db)


@router.post("/tools", summary="Добавить инструмент / оснастку")
@handle
def add_tool(data: ToolIn, db: Session = Depends(get_db)):
    return svc.save_tool(db, None, data.model_dump())


@router.put("/tools/{tool_id}", summary="Изменить инструмент / оснастку")
@handle
def update_tool(tool_id: int, data: ToolIn, db: Session = Depends(get_db)):
    return svc.save_tool(db, tool_id, data.model_dump())


@router.delete("/tools/{tool_id}", summary="Удалить инструмент / оснастку")
@handle
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    return svc.delete_tool(db, tool_id)


# ------------------------------------------------------------- маршрут изделия
@router.get("/products", summary="Справочник изделий с признаками маршрута")
@handle
def products(db: Session = Depends(get_db)):
    return svc.get_products(db)


@router.get("/products/{product_id}/route", summary="Технологический маршрут изделия (1 уровень)")
@handle
def route(product_id: int, db: Session = Depends(get_db)):
    return svc.get_route(db, product_id)


@router.post("/products/{product_id}/operations", summary="Добавить Изделие-Операцию (ТЕХ / ЗАКУПКА)")
@handle
def add_operation(product_id: int, data: OperationIn, db: Session = Depends(get_db)):
    d = data.model_dump()
    return svc.add_operation(db, product_id, d.pop("вид"), d)


@router.post("/products/{product_id}/build-from-bom", summary="Сформировать входные ресурсы по спецификации (BOM)")
@handle
def build_from_bom(product_id: int, operation_id: Optional[int] = None, db: Session = Depends(get_db)):
    return svc.build_from_bom(db, product_id, operation_id)


@router.put("/operations/{op_id}", summary="Изменить операцию")
@handle
def update_operation(op_id: int, data: OperationIn, db: Session = Depends(get_db)):
    return svc.update_operation(db, op_id, data.model_dump())


@router.delete("/operations/{op_id}", summary="Удалить операцию")
@handle
def delete_operation(op_id: int, db: Session = Depends(get_db)):
    return svc.delete_operation(db, op_id)


@router.post("/operations/{op_id}/inputs", summary="Добавить позицию входного ресурса (норму расхода)")
@handle
def add_input(op_id: int, data: InputIn, db: Session = Depends(get_db)):
    return svc.add_input(db, op_id, data.вход_id, data.норма, data.для_количества, data.ед_изм_id)


@router.put("/inputs/{input_id}", summary="Изменить норму расхода")
@handle
def update_input(input_id: int, data: InputUpdate, db: Session = Depends(get_db)):
    return svc.update_input(db, input_id, data.норма, data.для_количества, data.ед_изм_id)


@router.delete("/inputs/{input_id}", summary="Удалить входной ресурс")
@handle
def delete_input(input_id: int, db: Session = Depends(get_db)):
    return svc.delete_input(db, input_id)


@router.post("/operations/{op_id}/tools", summary="Назначить инструмент / оснастку операции")
@handle
def add_tool_link(op_id: int, data: ToolLinkIn, db: Session = Depends(get_db)):
    return svc.add_tool(db, op_id, data.инструмент_id, data.количество)


@router.delete("/operation-tools/{link_id}", summary="Снять инструмент с операции")
@handle
def delete_tool_link(link_id: int, db: Session = Depends(get_db)):
    return svc.delete_tool_link(db, link_id)


@router.post("/operations/{op_id}/typical", summary="Применить типовой ТП (Flyweight) со значениями параметров")
@handle
def apply_typical(op_id: int, data: TypicalApply, db: Session = Depends(get_db)):
    return svc.apply_typical(db, op_id, data.тп_id, data.значения)


@router.delete("/operations/{op_id}/typical", summary="Отвязать типовой ТП (нормы фиксируются в операции)")
@handle
def remove_typical(op_id: int, db: Session = Depends(get_db)):
    return svc.remove_typical(db, op_id)


# ------------------------------------------------------------- расчёты
@router.get("/products/{product_id}/find", summary="FIND_TM — технологический маршрут на всю глубину")
@handle
def find_tm(product_id: int, db: Session = Depends(get_db)):
    return svc.find_tm(db, product_id)


@router.get("/operations/{op_id}/mr", summary="MR_Q — нормы расхода ресурсов для операции")
@handle
def mr_q(op_id: int, quantity: float = Query(1.0, gt=0), db: Session = Depends(get_db)):
    return svc.mr_q(db, op_id, quantity)


@router.get("/products/{product_id}/materials", summary="SUM_MR — сводные нормы материальных ресурсов")
@handle
def sum_mr(product_id: int, quantity: float = Query(1.0, gt=0), db: Session = Depends(get_db)):
    return svc.sum_mr(db, product_id, quantity)


@router.get("/products/{product_id}/labor", summary="TR_TO — потребность в трудовых ресурсах и загрузка ГРЦ")
@handle
def tr_to(product_id: int, quantity: float = Query(1.0, gt=0), db: Session = Depends(get_db)):
    return svc.tr_to(db, product_id, quantity)


@router.get("/products/{product_id}/cost", summary="Калькуляция себестоимости (материалы + труд + оборудование)")
@handle
def calc_cost(product_id: int, quantity: float = Query(1.0, gt=0), db: Session = Depends(get_db)):
    return svc.calc_cost(db, product_id, quantity)


# ------------------------------------------------------------- типовые ТП (Flyweight)
@router.get("/typical", summary="Типовые технологические процессы")
@handle
def typicals(db: Session = Depends(get_db)):
    return svc.get_typicals(db)


@router.get("/typical/stats", summary="Статистика пула приспособленцев")
@handle
def typical_stats(db: Session = Depends(get_db)):
    return svc.flyweight_stats(db)


@router.get("/typical/{tp_id}", summary="Типовой ТП: параметры, операции, ресурсы, применение")
@handle
def typical(tp_id: int, db: Session = Depends(get_db)):
    return svc.get_typical(db, tp_id)


@router.post("/typical", summary="Добавить типовой ТП")
@handle
def add_typical(data: TypicalIn, db: Session = Depends(get_db)):
    return svc.save_typical(db, None, data.model_dump())


@router.put("/typical/{tp_id}", summary="Изменить типовой ТП")
@handle
def update_typical(tp_id: int, data: TypicalIn, db: Session = Depends(get_db)):
    return svc.save_typical(db, tp_id, data.model_dump())


@router.delete("/typical/{tp_id}", summary="Удалить типовой ТП")
@handle
def delete_typical(tp_id: int, db: Session = Depends(get_db)):
    return svc.delete_typical(db, tp_id)


@router.post("/typical/{tp_id}/params", summary="Добавить параметр ТПП")
@handle
def add_typical_param(tp_id: int, data: TypicalParamIn, db: Session = Depends(get_db)):
    return svc.add_typical_param(db, tp_id, data.model_dump())


@router.post("/typical/{tp_id}/operations", summary="Добавить типовую операцию")
@handle
def add_typical_operation(tp_id: int, data: TypicalOperationIn, db: Session = Depends(get_db)):
    return svc.add_typical_operation(db, tp_id, data.model_dump())


@router.post("/typical/{tp_id}/resources", summary="Добавить материальный ресурс типового ТП")
@handle
def add_typical_resource(tp_id: int, data: TypicalResourceIn, db: Session = Depends(get_db)):
    return svc.add_typical_resource(db, tp_id, data.model_dump())


@router.delete("/typical-items/{kind}/{item_id}", summary="Удалить параметр / операцию / ресурс типового ТП")
@handle
def delete_typical_item(kind: str, item_id: int, db: Session = Depends(get_db)):
    return svc.delete_typical_item(db, kind, item_id)


@router.post("/typical/{tp_id}/preview", summary="Расчёт норм типового ТП для заданных значений параметров")
@handle
def preview_typical(tp_id: int, data: PreviewIn, db: Session = Depends(get_db)):
    return svc.preview_typical(db, tp_id, data.значения)
