# schemas.py
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime

# Category schemas
class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    node_type: str
    sort_order: int = 0
    
    class Config:
        from_attributes = True

# Subcategory
class SubcategoryCreate(BaseModel):
    parent_name: str
    child_name: str

# Move node
class MoveNode(BaseModel):
    new_parent_id: Optional[int] = None

# Reorder children
class ReorderChildren(BaseModel):
    ordered_child_ids: List[int]

# Set base unit
class SetBaseUnit(BaseModel):
    base_ei_id: int

# Set schemas
class SetCreate(BaseModel):
    name: str
    catalog_number: str
    year: int
    price: float
    parts_count: int
    age_category_id: int
    theme_id: int
    parent_id: Optional[int] = None

class SetResponse(BaseModel):
    id: int
    name: str
    catalog_number: str
    year: int
    price: float
    parts_count: int
    
    class Config:
        from_attributes = True

# Part schemas
class PartCreate(BaseModel):
    name: str
    part_type_id: int

class PartResponse(BaseModel):
    id: int
    name: str
    part_type_id: int
    type_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class PartFilter(BaseModel):
    """Фильтр деталей по типу и названию. Характеристики задаются параметрами изделия."""
    part_type_id: Optional[int] = None
    name_contains: Optional[str] = None

# Minifigure schemas
class MinifigureCreate(BaseModel):
    name: str
    character: str
    series: str
    unique_code: str

class MinifigureResponse(BaseModel):
    id: int
    name: str
    character: str
    series: str
    unique_code: str
    
    class Config:
        from_attributes = True

# Theme schemas
class ThemeCreate(BaseModel):
    name: str
    description: str

class ThemeResponse(BaseModel):
    id: int
    name: str
    description: str
    
    class Config:
        from_attributes = True

# Age category schemas
class AgeCategoryCreate(BaseModel):
    name: str
    min_age: int
    max_age: int

class AgeCategoryResponse(BaseModel):
    id: int
    name: str
    min_age: int
    max_age: int
    
    class Config:
        from_attributes = True

# Part type schemas
class PartTypeCreate(BaseModel):
    name: str
    hierarchy_level: int

class PartTypeResponse(BaseModel):
    id: int
    name: str
    hierarchy_level: int
    
    class Config:
        from_attributes = True

# Operation result
class OperationResult(BaseModel):
    success: bool
    message: str
    node_id: Optional[int] = None
    product_id: Optional[int] = None

# Search results
class SetSearchResult(BaseModel):
    set_name: str
    catalog_number: str
    year: int
    price: float
    theme_name: str

class AgeSearchResult(BaseModel):
    set_name: str
    catalog_number: str
    min_age: int
    max_age: int
    price: float

class PartSearchResult(BaseModel):
    part_name: str
    type_name: str

# Set contents
class SetContent(BaseModel):
    item_type: str
    item_name: str
    quantity: int
    color: Optional[str] = None

class SetProductItemCreate(BaseModel):
    product_id: int
    quantity: int


# Enumeration schemas
class EnumerationCreate(BaseModel):
    name: str
    description: Optional[str] = None

class EnumerationResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    values_count: Optional[int] = 0

    class Config:
        from_attributes = True

# EnumValue schemas
class EnumValueCreate(BaseModel):
    value: str
    sort_order: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None

class EnumValueResponse(BaseModel):
    id: int
    enumeration_id: int
    value: str
    sort_order: int
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class EnumValueReorder(BaseModel):
    ordered_ids: List[int]

# ========== НОВЫЕ СХЕМЫ ДЛЯ ЗАДАНИЯ 1.3 (СПРАВОЧНИК ИЗДЕЛИЙ) ==========

# Parameter schemas
class ParameterCreate(BaseModel):
    обозначение: str
    полное_имя: str
    тип_параметра: str  # REAL, INTEGER, STRING, DATETIME, ENUM
    единица_измерения: Optional[str] = None
    перечисление_id: Optional[int] = None

class ParameterResponse(BaseModel):
    id: int
    обозначение: str
    полное_имя: str
    единица_измерения: Optional[str] = None
    тип_параметра: str
    перечисление_id: Optional[int] = None

    class Config:
        from_attributes = True

# ParameterClass schemas
class ParameterClassCreate(BaseModel):
    параметр_id: int
    мин_значение: Optional[float] = None
    макс_значение: Optional[float] = None
    значение_по_умолчанию: Optional[str] = None
    обязательный: bool = False

class ParameterClassResponse(BaseModel):
    id: int
    класс_id: int
    параметр_id: int
    порядковый_номер: int
    мин_значение: Optional[float] = None
    макс_значение: Optional[float] = None
    значение_по_умолчанию: Optional[str] = None
    обязательный: bool

    class Config:
        from_attributes = True

# Product schemas
class ProductCreate(BaseModel):
    класс_id: int
    наименование: str
    артикул: Optional[str] = None

class ProductResponse(BaseModel):
    id: int
    наименование: str
    артикул: Optional[str] = None
    класс_id: int
    класс_название: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ParameterValue schemas
class ParameterValueCreate(BaseModel):
    param_class_id: int
    value: Any  # может быть число, строка, дата или ID перечисления

class ParameterValueResponse(BaseModel):
    param_class_id: int
    обозначение: str
    полное_имя: str
    тип_параметра: str
    единица_измерения: Optional[str] = None
    значение: Any
    обязательный: bool

# Filter schemas
class ParamFilter(BaseModel):
    param_code: str
    operator: str  # =, >, <, between
    value: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None

class ProductFilter(BaseModel):
    class_ids: Optional[List[int]] = None
    param_filters: Optional[List[ParamFilter]] = None

# ========== СХЕМЫ ДЛЯ ХОЗЯЙСТВЕННЫХ ОПЕРАЦИЙ (ЗАДАНИЕ 1.4) ==========

# Типы ХО
class HOTypeCreate(BaseModel):
    название: str
    родительский_id: Optional[int] = None

class HOTypeResponse(BaseModel):
    id: int
    название: str
    родительский_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Роли
class HORoleCreate(BaseModel):
    название: str
    допустимый_класс_СХД: Optional[int] = None

class HORoleResponse(BaseModel):
    id: int
    тип_хо_id: int
    название: str
    допустимый_класс_СХД: Optional[int] = None

# Параметры ХО
class HOParameterCreate(BaseModel):
    параметр_id: int
    порядковый_номер: Optional[int] = None
    обязательный: bool = False

# Субъекты
class SubjectCreate(BaseModel):
    наименование: str
    инн: Optional[str] = None
    контактное_лицо: Optional[str] = None
    телефон: Optional[str] = None

class SubjectResponse(BaseModel):
    id: int
    наименование: str
    инн: Optional[str] = None
    контактное_лицо: Optional[str] = None
    телефон: Optional[str] = None

# Экземпляры ХО
class HOOperationCreate(BaseModel):
    тип_хо_id: int
    номер_документа: str
    дата: datetime

class HOOperationResponse(BaseModel):
    id: int
    тип_хо_id: int
    номер_документа: str
    дата: datetime
    сумма: float

# Назначение роли
class HORoleAssignmentCreate(BaseModel):
    роль_хо_id: int
    субъект_хо_id: int

# Значение параметра ХО
class HOParameterValueCreate(BaseModel):
    параметр_хо_id: int
    value: Any

# Позиция ХО
class HOItemCreate(BaseModel):
    изделие_id: int
    количество: float
    цена: float

class HOItemResponse(BaseModel):
    id: int
    изделие_id: int
    количество: float
    цена: float
    сумма: float

# Фильтр
class HOFilter(BaseModel):
    тип_хо_id: Optional[int] = None
    дата_от: Optional[datetime] = None
    дата_до: Optional[datetime] = None
    сумма_мин: Optional[float] = None
    сумма_макс: Optional[float] = None
