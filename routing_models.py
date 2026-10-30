# routing_models.py
"""
Задание 6. Маршрутная технология изготовления изделий — модель хранения (ORM).

Классы соответствуют проектной модели (вариант 2) и расширению для типовых
техпроцессов (паттерн «Приспособленец»):

  ГРЦ (WorkCenter)                       — групповой рабочий центр (группа однотипного оборудования)
  Инструмент (Tool)                      — инструмент и технологическая оснастка
  Изделие_операция (ProductOperation)    — изделие в состоянии «после операции» (абстрактный класс)
      ├─ Позиция_тех_маршрута (RoutePosition)   — операция, выполняемая на предприятии (Тпз, Тшт)
      └─ Позиция_закупки (PurchasePosition)     — компонент покупается готовым («операция» Закупка)
  Позиция_входного_ресурса (InputResource) — «для выходной И-О требуется входная И-О в количестве …»
  Инструмент_операции (OperationTool)    — инструмент/оснастка, требуемые для операции
  Типовой_ТП (TypicalProcess)            — разделяемое внутреннее состояние (Flyweight)
      ├─ Параметр_ТПП (TypicalParam)
      ├─ Типовая_операция (TypicalOperation)   — нормы времени: Т = база + коэф × параметр
      └─ Типовой_ресурс (TypicalResource)      — нормы расхода: Н = база + коэф × параметр
  Значение_параметра_ТПП (TypicalParamValue) — внешнее состояние: значения параметров у И-О

Классы операций, профессии, типы оборудования и инструмента ведутся в общем
классификаторе (метакласс Классификатор, таблица «классификатор»), квалификация —
перечисление «Квалификация (разряд)» (таблица «значение_перечисления»).
"""
from datetime import datetime

from sqlalchemy import (CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from models import Base


class WorkCenter(Base):
    """ГРЦ — групповой рабочий центр"""
    __tablename__ = "грц"

    id = Column(Integer, primary_key=True, autoincrement=True)
    код = Column(String(20), nullable=False, unique=True)
    наименование = Column(String(200), nullable=False)
    класс_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)   # тип оборудования
    субъект_id = Column(Integer, ForeignKey("субъект_хоз_деятельности.id", ondelete="SET NULL"), nullable=True)  # подразделение
    количество_ед = Column(Integer, nullable=False, default=1)       # единиц оборудования в группе
    ставка_часа = Column(Float, nullable=False, default=0.0)         # стоимость машино-часа, руб/ч

    class_node = relationship("Classificator", foreign_keys=[класс_id])
    subject = relationship("Subject", foreign_keys=[субъект_id])


class Tool(Base):
    """Инструмент и технологическая оснастка"""
    __tablename__ = "инструмент"

    id = Column(Integer, primary_key=True, autoincrement=True)
    обозначение = Column(String(50), nullable=False, unique=True)
    наименование = Column(String(200), nullable=False)
    класс_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)
    вид = Column(String(20), nullable=False, default="ИНСТРУМЕНТ")   # ИНСТРУМЕНТ / ОСНАСТКА

    class_node = relationship("Classificator", foreign_keys=[класс_id])


class TypicalProcess(Base):
    """Типовой технологический процесс — внутреннее (разделяемое) состояние приспособленца"""
    __tablename__ = "типовой_тп"

    id = Column(Integer, primary_key=True, autoincrement=True)
    обозначение = Column(String(30), nullable=False, unique=True)
    наименование = Column(String(200), nullable=False)
    класс_то_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)
    описание = Column(Text, nullable=True)

    params = relationship("TypicalParam", back_populates="process", cascade="all, delete-orphan",
                          order_by="TypicalParam.id")
    operations = relationship("TypicalOperation", back_populates="process", cascade="all, delete-orphan",
                              order_by="TypicalOperation.номер")
    resources = relationship("TypicalResource", back_populates="process", cascade="all, delete-orphan",
                             order_by="TypicalResource.id")


class TypicalParam(Base):
    """Параметр типового ТП (например, масса детали m, площадь печати S)"""
    __tablename__ = "параметр_тпп"
    __table_args__ = (UniqueConstraint("тп_id", "обозначение", name="uq_параметр_тпп"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    тп_id = Column(Integer, ForeignKey("типовой_тп.id", ondelete="CASCADE"), nullable=False)
    обозначение = Column(String(20), nullable=False)
    наименование = Column(String(100), nullable=False)
    ед_изм = Column(String(20), nullable=True)
    мин_значение = Column(Float, nullable=True)
    макс_значение = Column(Float, nullable=True)
    по_умолчанию = Column(Float, nullable=True)

    process = relationship("TypicalProcess", back_populates="params")


class TypicalOperation(Base):
    """Операция типового ТП. Штучное время: Тшт = тшт_база + тшт_коэф × значение параметра"""
    __tablename__ = "типовая_операция"
    __table_args__ = (UniqueConstraint("тп_id", "номер", name="uq_типовая_операция"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    тп_id = Column(Integer, ForeignKey("типовой_тп.id", ondelete="CASCADE"), nullable=False)
    номер = Column(Integer, nullable=False)
    наименование = Column(String(200), nullable=False)
    класс_то_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)
    грц_id = Column(Integer, ForeignKey("грц.id", ondelete="SET NULL"), nullable=True)
    профессия_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)
    квалификация_id = Column(Integer, ForeignKey("значение_перечисления.id", ondelete="SET NULL"), nullable=True)
    тпз = Column(Float, nullable=False, default=0.0)          # мин на партию
    тшт_база = Column(Float, nullable=False, default=0.0)     # мин на 1 шт
    тшт_коэф = Column(Float, nullable=False, default=0.0)     # мин на единицу параметра
    параметр_id = Column(Integer, ForeignKey("параметр_тпп.id", ondelete="SET NULL"), nullable=True)

    process = relationship("TypicalProcess", back_populates="operations")


class TypicalResource(Base):
    """Материальный ресурс типового ТП. Норма: Н = норма_база + норма_коэф × значение параметра"""
    __tablename__ = "типовой_ресурс"

    id = Column(Integer, primary_key=True, autoincrement=True)
    тп_id = Column(Integer, ForeignKey("типовой_тп.id", ondelete="CASCADE"), nullable=False)
    изделие_id = Column(Integer, ForeignKey("изделие.id", ondelete="RESTRICT"), nullable=False)
    норма_база = Column(Float, nullable=False, default=0.0)
    норма_коэф = Column(Float, nullable=False, default=0.0)
    параметр_id = Column(Integer, ForeignKey("параметр_тпп.id", ondelete="SET NULL"), nullable=True)
    ед_изм_id = Column(Integer, ForeignKey("единица_измерения.id", ondelete="SET NULL"), nullable=True)

    process = relationship("TypicalProcess", back_populates="resources")
    product = relationship("Product")


class ProductOperation(Base):
    """Изделие-Операция: изделие в состоянии после выполнения операции (абстрактный класс).
    Наследование «одна таблица на иерархию»: дискриминатор — поле «вид»."""
    __tablename__ = "изделие_операция"
    __table_args__ = (
        UniqueConstraint("изделие_id", "номер", name="uq_изделие_операция_номер"),
        CheckConstraint("тпз >= 0 AND тшт >= 0", name="ck_трудоемкость_неотрицательна"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    изделие_id = Column(Integer, ForeignKey("изделие.id", ondelete="CASCADE"), nullable=False)   # FOR_PROD
    номер = Column(Integer, nullable=False)                                                     # NUM
    вид = Column(String(20), nullable=False)                                                    # ТЕХ / ЗАКУПКА
    наименование = Column(String(200), nullable=False)        # состояние: «после литья», «после контроля»
    класс_то_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)   # CL_TO
    грц_id = Column(Integer, ForeignKey("грц.id", ondelete="SET NULL"), nullable=True)                 # ID_GRC
    профессия_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True) # CL_PROF
    квалификация_id = Column(Integer, ForeignKey("значение_перечисления.id", ondelete="SET NULL"), nullable=True)  # KVAL
    тпз = Column(Float, nullable=False, default=0.0)          # подготовительно-заключительное время, мин/партию
    тшт = Column(Float, nullable=False, default=0.0)          # штучное время, мин/шт
    цена = Column(Float, nullable=True)                       # цена закупки за ЕИ (для позиции закупки)
    ед_изм_id = Column(Integer, ForeignKey("единица_измерения.id", ondelete="SET NULL"), nullable=True)
    типовой_тп_id = Column(Integer, ForeignKey("типовой_тп.id", ondelete="SET NULL"), nullable=True)
    примечание = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")
    typical = relationship("TypicalProcess")
    inputs = relationship("InputResource", foreign_keys="InputResource.выход_id",
                          cascade="all, delete-orphan", back_populates="output")
    tools = relationship("OperationTool", cascade="all, delete-orphan", back_populates="operation")
    param_values = relationship("TypicalParamValue", cascade="all, delete-orphan", back_populates="operation")

    __mapper_args__ = {"polymorphic_on": вид, "polymorphic_abstract": True}

    def is_purchase(self) -> bool:
        return False


class RoutePosition(ProductOperation):
    """Позиция тех-маршрута: операция, выполняемая на предприятии"""
    __mapper_args__ = {"polymorphic_identity": "ТЕХ"}


class PurchasePosition(ProductOperation):
    """Позиция закупки: компонент (материал, комплектующее) покупается готовым"""
    __mapper_args__ = {"polymorphic_identity": "ЗАКУПКА"}

    def is_purchase(self) -> bool:
        return True


class InputResource(Base):
    """Позиция входного ресурса: выходная И-О потребляет входную И-О в количестве норма / для_количества"""
    __tablename__ = "входной_ресурс"
    __table_args__ = (
        UniqueConstraint("выход_id", "вход_id", name="uq_входной_ресурс"),
        CheckConstraint("выход_id <> вход_id", name="ck_входной_ресурс_не_сам"),
        CheckConstraint("норма > 0 AND для_количества > 0", name="ck_входной_ресурс_норма"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    выход_id = Column(Integer, ForeignKey("изделие_операция.id", ondelete="CASCADE"), nullable=False)  # OUT_TO
    вход_id = Column(Integer, ForeignKey("изделие_операция.id", ondelete="RESTRICT"), nullable=False)  # IN_TO
    норма = Column(Float, nullable=False)                    # Q
    для_количества = Column(Float, nullable=False, default=1.0)   # FOR_Q
    ед_изм_id = Column(Integer, ForeignKey("единица_измерения.id", ondelete="SET NULL"), nullable=True)
    источник = Column(String(20), nullable=False, default="ВРУЧНУЮ")   # ВРУЧНУЮ / СПЕЦИФИКАЦИЯ

    output = relationship("ProductOperation", foreign_keys=[выход_id], back_populates="inputs")
    input_op = relationship("ProductOperation", foreign_keys=[вход_id])


class OperationTool(Base):
    """Инструмент / оснастка, требуемые для выполнения операции"""
    __tablename__ = "инструмент_операции"
    __table_args__ = (UniqueConstraint("операция_id", "инструмент_id", name="uq_инструмент_операции"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    операция_id = Column(Integer, ForeignKey("изделие_операция.id", ondelete="CASCADE"), nullable=False)
    инструмент_id = Column(Integer, ForeignKey("инструмент.id", ondelete="RESTRICT"), nullable=False)
    количество = Column(Integer, nullable=False, default=1)

    operation = relationship("ProductOperation", back_populates="tools")
    tool = relationship("Tool")


class TypicalParamValue(Base):
    """Значение параметра типового ТП у конкретной Изделие-Операции (внешнее состояние приспособленца)"""
    __tablename__ = "значение_параметра_тпп"
    __table_args__ = (UniqueConstraint("операция_id", "параметр_id", name="uq_значение_параметра_тпп"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    операция_id = Column(Integer, ForeignKey("изделие_операция.id", ondelete="CASCADE"), nullable=False)
    параметр_id = Column(Integer, ForeignKey("параметр_тпп.id", ondelete="CASCADE"), nullable=False)
    значение = Column(Float, nullable=False)

    operation = relationship("ProductOperation", back_populates="param_values")
    param = relationship("TypicalParam")
