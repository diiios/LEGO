# bom_api.py
"""Задание 5. REST API «Материальная спецификация изделий (Bill of materials)»"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from bom_service import PRODUCT_KIND_TITLES, bom_service

TAG = "Спецификации (BOM)"
router = APIRouter(prefix="/bom", tags=[TAG])

# Зависимость get_db подставляется из main.py (router.dependency_overrides не нужен)
_get_db = None


def get_db():
    yield from _get_db()


# ------------------------------------------------------------- схемы
class UnitCreate(BaseModel):
    код: str = Field(..., min_length=1, max_length=10)
    наименование: str = Field(..., min_length=1, max_length=50)
    обозначение: str = Field(..., min_length=1, max_length=10)


class ProductKindUpdate(BaseModel):
    тип_изделия: str
    ед_изм_id: Optional[int] = None


class PositionCreate(BaseModel):
    компонент_id: int
    расход: float = Field(..., gt=0, description="Норма расхода")
    для_количества: float = Field(1.0, gt=0, description="На какое количество изделия задана норма")
    ед_изм_id: Optional[int] = None
    флаг_базы: Optional[bool] = None
    примечание: Optional[str] = None
    автор: Optional[str] = None
    причина: Optional[str] = None


class PositionUpdate(BaseModel):
    расход: float = Field(..., gt=0)
    для_количества: float = Field(1.0, gt=0)
    ед_изм_id: Optional[int] = None
    флаг_базы: Optional[bool] = None
    примечание: Optional[str] = None
    автор: Optional[str] = None
    причина: Optional[str] = None


class ExcludeComponent(BaseModel):
    компонент_id: int
    автор: Optional[str] = None
    причина: Optional[str] = None


class ModificationCreate(BaseModel):
    наименование: str = Field(..., min_length=1, max_length=200)
    артикул: Optional[str] = Field(None, max_length=50)
    причина: Optional[str] = None
    автор: Optional[str] = None


class ChangeCreate(BaseModel):
    описание: str = Field(..., min_length=1)
    автор: Optional[str] = None


def _ok(result: Dict[str, Any], code: int = 400) -> Dict[str, Any]:
    if not result.get("success"):
        raise HTTPException(status_code=code, detail=result.get("message", "Ошибка"))
    return result


# ------------------------------------------------------------- ЕИ
@router.get("/units", summary="Справочник единиц измерения")
def get_units(db: Session = Depends(get_db)):
    return bom_service.get_units(db)


@router.post("/units", summary="Добавить единицу измерения")
def add_unit(data: UnitCreate, db: Session = Depends(get_db)):
    return _ok(bom_service.add_unit(db, data.код, data.наименование, data.обозначение))


@router.put("/units/{unit_id}", summary="Изменить единицу измерения")
def update_unit(unit_id: int, data: UnitCreate, db: Session = Depends(get_db)):
    return _ok(bom_service.update_unit(db, unit_id, data.код, data.наименование, data.обозначение))


@router.delete("/units/{unit_id}", summary="Удалить единицу измерения")
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    return _ok(bom_service.delete_unit(db, unit_id))


# ------------------------------------------------------------- изделия
@router.get("/product-kinds", summary="Типы изделий")
def product_kinds():
    return [{"code": k, "title": v} for k, v in PRODUCT_KIND_TITLES.items()]


@router.get("/products", summary="Изделия с признаками спецификации")
def get_products(kind: Optional[str] = None, db: Session = Depends(get_db)):
    return bom_service.get_products(db, kind)


@router.get("/products/{product_id}", summary="Карточка изделия (базовое изделие, модификации)")
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = bom_service.get_product(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Изделие не найдено")
    return p


@router.put("/products/{product_id}/kind", summary="Задать тип изделия и основную ЕИ")
def set_kind(product_id: int, data: ProductKindUpdate, db: Session = Depends(get_db)):
    return _ok(bom_service.set_product_kind(db, product_id, data.тип_изделия, data.ед_изм_id))


# ------------------------------------------------------------- спецификация
@router.get("/products/{product_id}/spec", summary="Спецификация 1-го уровня (с учётом модификаций)")
def get_spec(product_id: int, db: Session = Depends(get_db)):
    return _ok(bom_service.get_spec(db, product_id), 404)


@router.post("/products/{product_id}/spec", summary="Добавить позицию спецификации")
def add_position(product_id: int, data: PositionCreate, db: Session = Depends(get_db)):
    return _ok(bom_service.add_position(db, product_id, data.компонент_id, data.расход, data.для_количества,
                                        data.ед_изм_id, data.флаг_базы, data.примечание, data.автор, data.причина))


@router.put("/positions/{position_id}", summary="Изменить позицию спецификации (норму расхода)")
def update_position(position_id: int, data: PositionUpdate, db: Session = Depends(get_db)):
    return _ok(bom_service.update_position(db, position_id, data.расход, data.для_количества, data.ед_изм_id,
                                           data.флаг_базы, data.примечание, data.автор, data.причина))


@router.delete("/positions/{position_id}", summary="Удалить позицию / восстановить исключённую")
def delete_position(position_id: int, автор: Optional[str] = None, причина: Optional[str] = None,
                    db: Session = Depends(get_db)):
    return _ok(bom_service.delete_position(db, position_id, автор, причина))


@router.post("/products/{product_id}/exclude", summary="Исключить унаследованный компонент из модификации")
def exclude(product_id: int, data: ExcludeComponent, db: Session = Depends(get_db)):
    return _ok(bom_service.exclude_component(db, product_id, data.компонент_id, data.автор, data.причина))


@router.get("/products/{product_id}/find", summary="FIND_BOM — состав на всю глубину вложенности")
def find_bom(product_id: int, db: Session = Depends(get_db)):
    return _ok(bom_service.find_bom(db, product_id), 404)


@router.get("/products/{product_id}/calc", summary="CALC_BOM — сводные нормы расхода")
def calc_bom(product_id: int, quantity: float = Query(1.0, gt=0), class_id: Optional[int] = None,
             db: Session = Depends(get_db)):
    return _ok(bom_service.calc_bom(db, product_id, quantity, class_id))


@router.get("/products/{product_id}/where-used", summary="Применяемость компонента")
def where_used(product_id: int, db: Session = Depends(get_db)):
    return bom_service.where_used(db, product_id)


# ------------------------------------------------------------- модификации
@router.post("/products/{product_id}/modifications", summary="CREATE_MODIFICATION — создать модификацию")
def create_modification(product_id: int, data: ModificationCreate, db: Session = Depends(get_db)):
    return _ok(bom_service.create_modification(db, product_id, data.наименование, data.артикул,
                                               data.причина, data.автор))


@router.get("/modifications", summary="Список модификаций")
def get_modifications(db: Session = Depends(get_db)):
    return bom_service.get_modifications(db)


# ------------------------------------------------------------- изменения
@router.get("/changes", summary="Журнал изменений спецификаций")
def get_changes(product_id: Optional[int] = None, date_from: Optional[datetime] = None,
                date_to: Optional[datetime] = None, kind: Optional[str] = None,
                db: Session = Depends(get_db)):
    return bom_service.get_changes(db, product_id, date_from, date_to, kind)


@router.post("/products/{product_id}/changes", summary="REGISTER_CHANGE — зарегистрировать изменение")
def register_change(product_id: int, data: ChangeCreate, db: Session = Depends(get_db)):
    return _ok(bom_service.register_change(db, product_id, data.описание, data.автор))
