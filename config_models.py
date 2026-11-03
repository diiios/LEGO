# config_models.py
"""
Задание 7 (усложнённый уровень). Заказы на изделия с вариантами исполнения и сложными
ограничениями на значения параметров конфигурации — модель хранения (ORM).

  Изделие (Product, models.py) — одна таблица на иерархию, поле «вид_конфигурации»:
      ├─ Изделие без конфигурации   ПРОСТОЕ   — добавляется в заказ как есть
      ├─ Типовое изделие с конфигуратором ТИПОВОЕ — шаблон, в заказ напрямую не попадает
      └─ Вариант исполнения         ВАРИАНТ   — создаётся из шаблона (шаблон_id) со значениями параметров
  Параметр класса с флагом конфигурации (models.ParameterClass) — параметр конфигурации
  Значение параметра (models.ParameterValue) — значение параметра у варианта исполнения

  Модель ограничений с функциями, формальными и фактическими параметрами:
  Функция_ограничения (ConstraintFunction) — элемент библиотеки функций; класс функции
      (Предикат, Логическая, Арифметическая, Функция выбора) — из классификатора;
      оператор — из перечислений операторов; либо тело — выражение над формальными аргументами
  Аргумент_функции (FunctionArgument)  — формальный параметр функции
  Вызов_функции (FunctionCall)         — конкретное использование функции
  Фактический_параметр (ActualParameter) — значение аргумента вызова: параметр изделия,
      константа, значение перечисления, вложенный вызов или формальный аргумент
  Константа (Constant)
  Ограничение (ProductConstraint)      — правило типового изделия = корневой вызов логической функции

  Заказ (Order), Позиция_заказа (OrderItem)
"""
from datetime import date

from sqlalchemy import (Boolean, CheckConstraint, Column, Date, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from models import Base


class ConstraintFunction(Base):
    """Функция для ограничений (FUN_COMP)"""
    __tablename__ = "функция_ограничения"

    id = Column(Integer, primary_key=True, autoincrement=True)
    обозначение = Column(String(40), nullable=False, unique=True)          # GT, AND, RATIO_IN_RANGE
    наименование = Column(String(200), nullable=False)
    класс_id = Column(Integer, ForeignKey("классификатор.id", ondelete="RESTRICT"), nullable=False)  # CLASS_F
    оператор_id = Column(Integer, ForeignKey("значение_перечисления.id", ondelete="RESTRICT"), nullable=True)  # OPER
    тип_результата_id = Column(Integer, ForeignKey("классификатор.id", ondelete="RESTRICT"), nullable=False)  # TYPE_RES
    тело_вызов_id = Column(Integer, ForeignKey("вызов_функции.id", ondelete="SET NULL", use_alter=True,
                                               name="fk_функция_тело"), nullable=True)
    описание = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("num_nonnulls(оператор_id, тело_вызов_id) <= 1", name="ck_функция_оператор_или_тело"),
    )
    arguments = relationship("FunctionArgument", back_populates="function", cascade="all, delete-orphan",
                             order_by="FunctionArgument.номер")


class FunctionArgument(Base):
    """Формальный параметр функции (ARG_FUN)"""
    __tablename__ = "аргумент_функции"

    id = Column(Integer, primary_key=True, autoincrement=True)
    функция_id = Column(Integer, ForeignKey("функция_ограничения.id", ondelete="CASCADE"), nullable=False)
    номер = Column(Integer, nullable=False)
    имя = Column(String(40), nullable=False)
    тип_id = Column(Integer, ForeignKey("классификатор.id", ondelete="RESTRICT"), nullable=False)  # ID_CLASS
    повторяемый = Column(Boolean, nullable=False, default=False)   # последний аргумент может повторяться (AND, IN)

    __table_args__ = (UniqueConstraint("функция_id", "номер", name="uq_аргумент_функции"),)
    function = relationship("ConstraintFunction", back_populates="arguments")


class Constant(Base):
    """Константа (CONST)"""
    __tablename__ = "константа"

    id = Column(Integer, primary_key=True, autoincrement=True)
    наименование = Column(String(100), nullable=False)
    тип_id = Column(Integer, ForeignKey("классификатор.id", ondelete="RESTRICT"), nullable=False)
    значение_число = Column(Float, nullable=True)
    значение_строка = Column(Text, nullable=True)
    ед_изм_id = Column(Integer, ForeignKey("единица_измерения.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("(значение_число IS NULL) <> (значение_строка IS NULL)", name="ck_константа_значение"),
    )


class FunctionCall(Base):
    """Вызов функции (FACT_FUN)"""
    __tablename__ = "вызов_функции"

    id = Column(Integer, primary_key=True, autoincrement=True)
    функция_id = Column(Integer, ForeignKey("функция_ограничения.id", ondelete="RESTRICT"), nullable=False)

    function = relationship("ConstraintFunction", foreign_keys=[функция_id])
    params = relationship("ActualParameter", back_populates="call", cascade="all, delete-orphan",
                          foreign_keys="ActualParameter.вызов_id", order_by="ActualParameter.номер")


class ActualParameter(Base):
    """Фактический параметр вызова (FACT_PAR): ровно один источник значения"""
    __tablename__ = "фактический_параметр"

    id = Column(Integer, primary_key=True, autoincrement=True)
    вызов_id = Column(Integer, ForeignKey("вызов_функции.id", ondelete="CASCADE"), nullable=False)
    номер = Column(Integer, nullable=False)
    параметр_id = Column(Integer, ForeignKey("параметр.id", ondelete="RESTRICT"), nullable=True)          # FACT_PROD
    константа_id = Column(Integer, ForeignKey("константа.id", ondelete="RESTRICT"), nullable=True)        # FACT_CONST
    значение_перечисления_id = Column(Integer, ForeignKey("значение_перечисления.id", ondelete="RESTRICT"),
                                      nullable=True)                                                   # FACT_ENUM
    вложенный_вызов_id = Column(Integer, ForeignKey("вызов_функции.id", ondelete="RESTRICT"), nullable=True)  # FACT_FUN
    аргумент_id = Column(Integer, ForeignKey("аргумент_функции.id", ondelete="RESTRICT"), nullable=True)  # в теле функции

    __table_args__ = (
        UniqueConstraint("вызов_id", "номер", name="uq_фактический_параметр"),
        CheckConstraint("num_nonnulls(параметр_id, константа_id, значение_перечисления_id, вложенный_вызов_id, "
                        "аргумент_id) = 1", name="ck_фактический_параметр_один_источник"),
    )
    call = relationship("FunctionCall", back_populates="params", foreign_keys=[вызов_id])
    nested = relationship("FunctionCall", foreign_keys=[вложенный_вызов_id])


class ProductConstraint(Base):
    """Ограничение типового изделия (LIMIT): корневой вызов логической функции"""
    __tablename__ = "ограничение"

    id = Column(Integer, primary_key=True, autoincrement=True)
    изделие_id = Column(Integer, ForeignKey("изделие.id", ondelete="CASCADE"), nullable=False)
    вызов_id = Column(Integer, ForeignKey("вызов_функции.id", ondelete="RESTRICT"), nullable=False)
    наименование = Column(String(200), nullable=False)
    сообщение = Column(Text, nullable=True)
    активно = Column(Boolean, nullable=False, default=True)
    порядок = Column(Integer, nullable=False, default=0)


class Order(Base):
    """Заказ (ORDER)"""
    __tablename__ = "заказ"

    id = Column(Integer, primary_key=True, autoincrement=True)
    номер = Column(String(30), nullable=False, unique=True)
    дата_регистрации = Column(Date, nullable=False, default=date.today)
    срок_изготовления = Column(Date, nullable=True)
    заказчик_id = Column(Integer, ForeignKey("субъект_хоз_деятельности.id", ondelete="RESTRICT"), nullable=False)
    контактное_лицо = Column(String(100), nullable=True)
    телефон = Column(String(40), nullable=True)
    статус = Column(String(20), nullable=False, default="ЧЕРНОВИК")   # ЧЕРНОВИК, СОГЛАСОВАН
    примечание = Column(Text, nullable=True)

    __table_args__ = (CheckConstraint("статус IN ('ЧЕРНОВИК', 'СОГЛАСОВАН')", name="ck_заказ_статус"),)
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan",
                         order_by="OrderItem.номер")


class OrderItem(Base):
    """Позиция заказа (POS_ORDER)"""
    __tablename__ = "позиция_заказа"

    id = Column(Integer, primary_key=True, autoincrement=True)
    заказ_id = Column(Integer, ForeignKey("заказ.id", ondelete="CASCADE"), nullable=False)
    номер = Column(Integer, nullable=False)
    изделие_id = Column(Integer, ForeignKey("изделие.id", ondelete="RESTRICT"), nullable=False)
    количество = Column(Float, nullable=False)
    цена = Column(Float, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("заказ_id", "номер", name="uq_позиция_заказа"),
        CheckConstraint("количество > 0", name="ck_позиция_заказа_количество"),
        CheckConstraint("цена >= 0", name="ck_позиция_заказа_цена"),
    )
    order = relationship("Order", back_populates="items")
