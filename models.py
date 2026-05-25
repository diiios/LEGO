# models.py
from datetime import datetime
from sqlalchemy import JSON, DateTime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Classificator(Base):
    __tablename__ = "классификатор"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    название = Column(String(100), nullable=False)
    тип_элемента = Column(String(20), nullable=False)
    родительский_id = Column(Integer, ForeignKey("классификатор.id", ondelete="SET NULL"), nullable=True)
    порядок_сортировки = Column(Integer, default=0)
    базовая_ед_измерения = Column(Integer, nullable=True)
    
    # Relationships
    children = relationship("Classificator", backref="parent", remote_side=[id])
    theme = relationship("Theme", back_populates="classificator", uselist=False)
    age_category = relationship("AgeCategory", back_populates="classificator", uselist=False)
    part_type = relationship("PartType", back_populates="classificator", uselist=False)
    product_set = relationship("Set", back_populates="classificator", uselist=False)
    part = relationship("Part", back_populates="classificator", uselist=False)
    minifigure = relationship("Minifigure", back_populates="classificator", uselist=False)


class Theme(Base):
    __tablename__ = "тематика"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_классификатора = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), unique=True)
    описание = Column(Text)
    
    # Relationships
    classificator = relationship("Classificator", back_populates="theme")
    sets = relationship("Set", back_populates="theme")


class AgeCategory(Base):
    __tablename__ = "возрастная_категория"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_классификатора = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), unique=True)
    минимальный_возраст = Column(Integer, nullable=False)
    максимальный_возраст = Column(Integer, nullable=False)
    
    # Relationships
    classificator = relationship("Classificator", back_populates="age_category")
    sets = relationship("Set", back_populates="age_category")


class PartType(Base):
    __tablename__ = "тип_детали"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_классификатора = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), unique=True)
    уровень_иерархии = Column(Integer)
    
    # Relationships
    classificator = relationship("Classificator", back_populates="part_type")
    parts = relationship("Part", back_populates="part_type")


class Set(Base):
    __tablename__ = "набор"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_классификатора = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), unique=True)
    номер_по_каталогу = Column(String(20), nullable=False, unique=True)
    количество_деталей = Column(Integer)
    год_выпуска = Column(Integer)
    цена = Column(Float)
    id_возрастной_категории = Column(Integer, ForeignKey("возрастная_категория.id"))
    id_тематики = Column(Integer, ForeignKey("тематика.id"))
    
    # Relationships
    classificator = relationship("Classificator", back_populates="product_set")
    age_category = relationship("AgeCategory", back_populates="sets")
    theme = relationship("Theme", back_populates="sets")
    parts = relationship("SetPart", back_populates="set")
    minifigures = relationship("SetMinifigure", back_populates="set")


class Part(Base):
    __tablename__ = "деталь"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_классификатора = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), unique=True)
    цвет = Column(String(30))
    размер = Column(String(20))
    вес = Column(Float)
    id_типа = Column(Integer, ForeignKey("тип_детали.id"))
    
    # Relationships
    classificator = relationship("Classificator", back_populates="part")
    part_type = relationship("PartType", back_populates="parts")


class Minifigure(Base):
    __tablename__ = "мини_фигурка"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_классификатора = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), unique=True)
    персонаж = Column(String(100))
    серия = Column(String(50))
    уникальный_код = Column(String(20), unique=True)
    
    # Relationships
    classificator = relationship("Classificator", back_populates="minifigure")
    sets = relationship("SetMinifigure", back_populates="minifigure")


class SetPart(Base):
    __tablename__ = "состав_набора"
    
    id_набора = Column(Integer, ForeignKey("набор.id", ondelete="CASCADE"), primary_key=True)
    id_детали = Column(Integer, ForeignKey("изделие.id", ondelete="CASCADE"), primary_key=True)
    количество_штук = Column(Integer)
    
    # Relationships
    set = relationship("Set", back_populates="parts")
    product = relationship("Product")


class SetMinifigure(Base):
    __tablename__ = "фигурки_в_наборе"
    
    id_набора = Column(Integer, ForeignKey("набор.id", ondelete="CASCADE"), primary_key=True)
    id_фигурки = Column(Integer, ForeignKey("мини_фигурка.id", ondelete="CASCADE"), primary_key=True)
    количество_штук = Column(Integer)
    
    # Relationships
    set = relationship("Set", back_populates="minifigures")
    minifigure = relationship("Minifigure", back_populates="sets")


class Enumeration(Base):
    """Справочник перечислений (тип enum)"""
    __tablename__ = "перечисление"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    values = relationship("EnumValue", back_populates="enumeration", cascade="all, delete-orphan")

class EnumValue(Base):
    """Значение перечисления"""
    __tablename__ = "значение_перечисления"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enumeration_id = Column(Integer, ForeignKey("перечисление.id", ondelete="CASCADE"), nullable=False)
    value = Column(String(200), nullable=False)
    sort_order = Column(Integer, default=0)
    extra_data = Column(JSON, nullable=True)

    enumeration = relationship("Enumeration", back_populates="values")

# ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ ЗАДАНИЯ 1.3 (СПРАВОЧНИК ИЗДЕЛИЙ С ПАРАМЕТРАМИ) ==========

class Parameter(Base):
    """Параметр — характеристика, которую можно измерять"""
    __tablename__ = "параметр"

    id = Column(Integer, primary_key=True, autoincrement=True)
    обозначение = Column(String(50), nullable=False, unique=True)   # "вес", "длина"
    полное_имя = Column(String(200), nullable=False)                # "Вес изделия"
    единица_измерения = Column(String(20))                         # "кг", "мм"
    тип_параметра = Column(String(20), nullable=False)             # REAL, INTEGER, STRING, DATETIME, ENUM
    перечисление_id = Column(Integer, ForeignKey("перечисление.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    class_links = relationship("ParameterClass", back_populates="parameter")

class ParameterClass(Base):
    """Привязка параметра к классу изделий (с ограничениями)"""
    __tablename__ = "параметр_класса"

    id = Column(Integer, primary_key=True, autoincrement=True)
    класс_id = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), nullable=False)
    параметр_id = Column(Integer, ForeignKey("параметр.id", ondelete="CASCADE"), nullable=False)
    порядковый_номер = Column(Integer, default=0)
    мин_значение = Column(Float, nullable=True)
    макс_значение = Column(Float, nullable=True)
    значение_по_умолчанию = Column(Text, nullable=True)
    обязательный = Column(Integer, default=0)  # 0 = нет, 1 = да
    
    # Relationships
    parameter = relationship("Parameter", back_populates="class_links")
    class_node = relationship("Classificator", foreign_keys=[класс_id])
    values = relationship("ParameterValue", back_populates="parameter_class", cascade="all, delete-orphan")


class Product(Base):
    """Конкретное изделие (экземпляр)"""
    __tablename__ = "изделие"

    id = Column(Integer, primary_key=True, autoincrement=True)
    класс_id = Column(Integer, ForeignKey("классификатор.id", ondelete="CASCADE"), nullable=False)
    наименование = Column(String(200), nullable=False)
    артикул = Column(String(50), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    class_node = relationship("Classificator", foreign_keys=[класс_id])
    parameter_values = relationship("ParameterValue", back_populates="product", cascade="all, delete-orphan")


class ParameterValue(Base):
    """Значение параметра для конкретного изделия"""
    __tablename__ = "значение_параметра"

    id = Column(Integer, primary_key=True, autoincrement=True)
    изделие_id = Column(Integer, ForeignKey("изделие.id", ondelete="CASCADE"), nullable=False)
    параметр_класса_id = Column(Integer, ForeignKey("параметр_класса.id", ondelete="CASCADE"), nullable=False)
    значение_число = Column(Float, nullable=True)
    значение_строка = Column(Text, nullable=True)
    значение_дата = Column(DateTime, nullable=True)
    значение_перечисление_id = Column(Integer, ForeignKey("значение_перечисления.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="parameter_values")
    parameter_class = relationship("ParameterClass", back_populates="values")
    enum_value = relationship("EnumValue", foreign_keys=[значение_перечисление_id])


# ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ ЗАДАНИЯ 1.4 (ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ) ==========

class HOType(Base):
    """Тип хозяйственной операции (иерархический классификатор)"""
    __tablename__ = "классификатор_хо"

    id = Column(Integer, primary_key=True, autoincrement=True)
    название = Column(String(200), nullable=False)
    родительский_id = Column(Integer, ForeignKey("классификатор_хо.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    children = relationship("HOType", backref="parent", remote_side=[id])
    roles = relationship("HORole", back_populates="ho_type", cascade="all, delete-orphan")
    parameters = relationship("HOParameter", back_populates="ho_type", cascade="all, delete-orphan")
    operations = relationship("HOOperation", back_populates="ho_type")


class HORole(Base):
    """Роль участника в операции (например, «Отправитель»)"""
    __tablename__ = "роль_хо"

    id = Column(Integer, primary_key=True, autoincrement=True)
    тип_хо_id = Column(Integer, ForeignKey("классификатор_хо.id", ondelete="CASCADE"), nullable=False)
    название = Column(String(100), nullable=False)
    допустимый_класс_СХД = Column(Integer, nullable=True)  # id узла классификатора (тип субъекта)

    ho_type = relationship("HOType", back_populates="roles")
    assignments = relationship("HORoleAssignment", back_populates="role", cascade="all, delete-orphan")


class HOParameter(Base):
    """Параметр, привязанный к типу ХО"""
    __tablename__ = "параметр_хо"

    id = Column(Integer, primary_key=True, autoincrement=True)
    тип_хо_id = Column(Integer, ForeignKey("классификатор_хо.id", ondelete="CASCADE"), nullable=False)
    параметр_id = Column(Integer, ForeignKey("параметр.id", ondelete="CASCADE"), nullable=False)   # ссылка на параметр из 1.3
    порядковый_номер = Column(Integer, default=0)
    обязательный = Column(Integer, default=0)   # 0/1

    ho_type = relationship("HOType", back_populates="parameters")
    parameter = relationship("Parameter")
    values = relationship("HOParameterValue", back_populates="ho_parameter", cascade="all, delete-orphan")


class Subject(Base):
    """Субъект хозяйственной деятельности (контрагент, подразделение)"""
    __tablename__ = "субъект_хоз_деятельности"

    id = Column(Integer, primary_key=True, autoincrement=True)
    наименование = Column(String(200), nullable=False)
    инн = Column(String(12), nullable=True)
    контактное_лицо = Column(String(100), nullable=True)
    телефон = Column(String(20), nullable=True)

    role_assignments = relationship("HORoleAssignment", back_populates="subject")


class HOOperation(Base):
    """Экземпляр хозяйственной операции"""
    __tablename__ = "хозяйственная_операция"

    id = Column(Integer, primary_key=True, autoincrement=True)
    тип_хо_id = Column(Integer, ForeignKey("классификатор_хо.id", ondelete="CASCADE"), nullable=False)
    номер_документа = Column(String(50), nullable=False)
    дата = Column(DateTime, nullable=False)
    сумма = Column(Float, default=0.0)

    ho_type = relationship("HOType", back_populates="operations")
    role_assignments = relationship("HORoleAssignment", back_populates="operation", cascade="all, delete-orphan")
    parameter_values = relationship("HOParameterValue", back_populates="operation", cascade="all, delete-orphan")
    items = relationship("HOItem", back_populates="operation", cascade="all, delete-orphan")


class HORoleAssignment(Base):
    """Назначение конкретного субъекта на роль в конкретной ХО"""
    __tablename__ = "роль_в_хо"

    id = Column(Integer, primary_key=True, autoincrement=True)
    операция_id = Column(Integer, ForeignKey("хозяйственная_операция.id", ondelete="CASCADE"), nullable=False)
    роль_хо_id = Column(Integer, ForeignKey("роль_хо.id", ondelete="CASCADE"), nullable=False)
    субъект_хо_id = Column(Integer, ForeignKey("субъект_хоз_деятельности.id", ondelete="SET NULL"), nullable=True)

    operation = relationship("HOOperation", back_populates="role_assignments")
    role = relationship("HORole", back_populates="assignments")
    subject = relationship("Subject", back_populates="role_assignments")


class HOParameterValue(Base):
    """Значение параметра для конкретной ХО"""
    __tablename__ = "значение_параметра_хо"

    id = Column(Integer, primary_key=True, autoincrement=True)
    операция_id = Column(Integer, ForeignKey("хозяйственная_операция.id", ondelete="CASCADE"), nullable=False)
    параметр_хо_id = Column(Integer, ForeignKey("параметр_хо.id", ondelete="CASCADE"), nullable=False)
    значение_число = Column(Float, nullable=True)
    значение_строка = Column(Text, nullable=True)
    значение_дата = Column(DateTime, nullable=True)
    значение_перечисление_id = Column(Integer, ForeignKey("значение_перечисления.id", ondelete="SET NULL"), nullable=True)

    operation = relationship("HOOperation", back_populates="parameter_values")
    ho_parameter = relationship("HOParameter", back_populates="values")
    enum_value = relationship("EnumValue", foreign_keys=[значение_перечисление_id])


class HOItem(Base):
    """Позиция (товарная строка) в ХО"""
    __tablename__ = "позиция_хо"

    id = Column(Integer, primary_key=True, autoincrement=True)
    операция_id = Column(Integer, ForeignKey("хозяйственная_операция.id", ondelete="CASCADE"), nullable=False)
    изделие_id = Column(Integer, ForeignKey("изделие.id", ondelete="CASCADE"), nullable=False)  # конкретное изделие из 1.3
    количество = Column(Float, nullable=False)
    цена = Column(Float, nullable=False)
    сумма = Column(Float, nullable=False)   # количество * цена

    operation = relationship("HOOperation", back_populates="items")
    product = relationship("Product")
