# config_service.py
"""
Задание 7 (усложнённый уровень). Бизнес-логика «Ведение заказов на изделия с вариантами исполнения».

Паттерны:
  Интерпретатор (Interpreter) — ограничения и формулы цены описываются выражениями над параметрами
      конфигурации. Выражение — дерево: терминальные выражения (параметр, константа, значение
      перечисления, формальный аргумент) и нетерминальные (вызов функции из библиотеки). Дерево
      разбирается из текста (Parser), хранится в таблицах вызов_функции / фактический_параметр,
      печатается обратно в текст и вычисляется (interpret здесь и EVAL_FUNCTION в PostgreSQL).
  Прототип (Prototype) — вариант исполнения создаётся клонированием типового изделия (шаблона)
      с подстановкой значений параметров; существующий вариант служит прототипом для нового
      варианта с изменёнными значениями («Копия с изменением»).
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from config_models import (ActualParameter, Constant, ConstraintFunction, FunctionArgument, FunctionCall, Order,
                           OrderItem, ProductConstraint)
from models import (Classificator, EnumValue, Enumeration, Parameter, ParameterClass, ParameterValue, Product,
                    Subject, UnitOfMeasure)

ROOT_FUNCTIONS = "Классы функций ограничений"
FN_PREDICATE, FN_LOGIC, FN_ARITH, FN_CHOICE = "Предикат", "Логическая функция", "Арифметическая функция", "Функция выбора"
ROOT_TYPES = "Типы значений"
T_NUM, T_BOOL, T_STR, T_ENUM, T_ANY = "Число", "Логическое значение", "Строка", "Значение перечисления", "Любое значение"
OPERATOR_ENUMS = {
    "Операторы сравнения": [">", ">=", "<", "<=", "=", "<>", "IN"],
    "Логические операторы": ["AND", "OR", "NOT"],
    "Арифметические операторы": ["+", "-", "*", "/", "MIN", "MAX"],
    "Операторы выбора": ["IF"],
}
KINDS = ("ПРОСТОЕ", "ТИПОВОЕ", "ВАРИАНТ")
ORDER_STATUSES = ("ЧЕРНОВИК", "СОГЛАСОВАН")


class ConfigError(Exception):
    """Нарушение правил предметной области (HTTP 400)"""


def _pg_msg(ex: Exception) -> str:
    """Текст RAISE EXCEPTION из хранимой процедуры (pg8000 отдаёт словарь полей ошибки)"""
    orig = getattr(ex, "orig", ex)
    arg = orig.args[0] if getattr(orig, "args", None) else str(orig)
    if isinstance(arg, dict):
        return arg.get("M", str(arg))
    return str(arg).split("\n")[0].replace("ERROR:  ", "")


def _num_text(v: float) -> str:
    if v is None:
        return "—"
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


# =============================================================================== Интерпретатор
class Library:
    """Библиотека функций ограничений и справочник типов (загружается из БД)"""

    def __init__(self, db: Session):
        self.types = self._subtree_names(db, ROOT_TYPES)               # id -> название
        self.type_id = {v: k for k, v in self.types.items()}
        self.classes = self._subtree_names(db, ROOT_FUNCTIONS)
        ops = {v.id: v.value for v in db.query(EnumValue).join(Enumeration)
               .filter(Enumeration.name.in_(list(OPERATOR_ENUMS))).all()}
        self.funcs: Dict[int, Dict[str, Any]] = {}
        for f in db.query(ConstraintFunction).all():
            self.funcs[f.id] = {
                "id": f.id, "обозначение": f.обозначение, "наименование": f.наименование,
                "класс": self.classes.get(f.класс_id), "оператор": ops.get(f.оператор_id),
                "тип": self.types.get(f.тип_результата_id), "тело_вызов_id": f.тело_вызов_id,
                "args": [{"id": a.id, "номер": a.номер, "имя": a.имя, "тип": self.types.get(a.тип_id),
                          "повторяемый": a.повторяемый} for a in f.arguments]}
        self.by_name = {f["обозначение"].upper(): f for f in self.funcs.values()}
        self.by_op = {f["оператор"]: f for f in self.funcs.values() if f["оператор"]}

    @staticmethod
    def _subtree_names(db: Session, root: str) -> Dict[int, str]:
        r = db.query(Classificator).filter(Classificator.название == root).first()
        if not r:
            return {}
        rows = db.execute(text("""WITH RECURSIVE t AS (SELECT id, "название" FROM "классификатор" WHERE id = :r
                                  UNION ALL SELECT k.id, k."название" FROM "классификатор" k JOIN t ON k."родительский_id" = t.id)
                                  SELECT id, "название" FROM t WHERE id <> :r"""), {"r": r.id}).all()
        return {i: n for i, n in rows}

    def op(self, symbol: str) -> Dict[str, Any]:
        f = self.by_op.get(symbol)
        if not f:
            raise ConfigError(f"В библиотеке нет функции с оператором «{symbol}»")
        return f


class Expression(ABC):
    """Абстрактное выражение паттерна «Интерпретатор»"""
    prec = 9

    @abstractmethod
    def interpret(self, ctx: Dict[str, Any]) -> Any: ...

    @abstractmethod
    def to_text(self) -> str: ...

    @abstractmethod
    def type_name(self) -> str: ...

    @abstractmethod
    def to_tree(self) -> Dict[str, Any]: ...

    @abstractmethod
    def source(self, db: Session, svc: "ConfigService") -> Dict[str, Any]:
        """Поля фактического параметра, ссылающиеся на это выражение"""


class ParamExpr(Expression):
    """Терминальное выражение: параметр конфигурации изделия"""

    def __init__(self, p: Dict[str, Any]):
        self.p = p

    def interpret(self, ctx):
        v = ctx["values"].get(self.p["id"])
        if v is None:
            raise ConfigError(f"Не задано значение параметра {self.p['обозначение']}")
        return v

    def to_text(self):
        return self.p["обозначение"]

    def type_name(self):
        return {"ENUM": T_ENUM, "STRING": T_STR}.get(self.p["тип"], T_NUM)

    def to_tree(self):
        return {"вид": "Параметр", "текст": self.p["обозначение"], "пояснение": self.p.get("полное_имя")}

    def source(self, db, svc):
        return {"параметр_id": self.p["id"]}


class ConstExpr(Expression):
    """Терминальное выражение: константа"""

    def __init__(self, value: Any, const_id: Optional[int] = None):
        self.value, self.const_id = value, const_id

    def interpret(self, ctx):
        return self.value

    def to_text(self):
        return _num_text(self.value) if isinstance(self.value, (int, float)) else f"'{self.value}'"

    def type_name(self):
        return T_NUM if isinstance(self.value, (int, float)) else T_STR

    def to_tree(self):
        return {"вид": "Константа", "текст": self.to_text()}

    def source(self, db, svc):
        return {"константа_id": self.const_id or svc.constant_id(db, self.value)}


class EnumExpr(Expression):
    """Терминальное выражение: значение перечисления"""

    def __init__(self, ev_id: int, label: str):
        self.ev_id, self.label = ev_id, label

    def interpret(self, ctx):
        return self.ev_id

    def to_text(self):
        return f"'{self.label}'"

    def type_name(self):
        return T_ENUM

    def to_tree(self):
        return {"вид": "Значение перечисления", "текст": self.label}

    def source(self, db, svc):
        return {"значение_перечисления_id": self.ev_id}


class ArgExpr(Expression):
    """Терминальное выражение: формальный аргумент функции (в теле составной функции)"""

    def __init__(self, arg: Dict[str, Any]):
        self.arg = arg

    def interpret(self, ctx):
        return ctx["args"][self.arg["номер"] - 1]

    def to_text(self):
        return self.arg["имя"]

    def type_name(self):
        return self.arg["тип"] or T_ANY

    def to_tree(self):
        return {"вид": "Аргумент", "текст": self.arg["имя"]}

    def source(self, db, svc):
        return {"аргумент_id": self.arg["id"]}


INFIX = {"OR": 1, "AND": 2, ">": 4, ">=": 4, "<": 4, "<=": 4, "=": 4, "<>": 4, "+": 5, "-": 5, "*": 6, "/": 6}


class CallExpr(Expression):
    """Нетерминальное выражение: вызов функции из библиотеки"""

    def __init__(self, f: Dict[str, Any], args: List[Expression], lib: Library):
        self.f, self.args, self.lib = f, args, lib
        op = f["оператор"]
        self.prec = INFIX.get(op, 3 if op == "NOT" else (4 if op == "IN" else 9))

    # ---- вычисление (то же, что EVAL_FUNCTION в БД)
    def interpret(self, ctx):
        a = [x.interpret(ctx) for x in self.args]
        if self.f["тело_вызов_id"]:
            body = ctx["svc"].load_call(ctx["db"], self.f["тело_вызов_id"], self.lib)
            return body.interpret({**ctx, "args": a})
        op = self.f["оператор"]
        num = lambda v: float(v)  # noqa: E731
        if op == "+":
            return sum(num(x) for x in a)
        if op == "*":
            r = 1.0
            for x in a:
                r *= num(x)
            return r
        if op == "-":
            return num(a[0]) - num(a[1])
        if op == "/":
            if num(a[1]) == 0:
                raise ConfigError(f"Деление на ноль в функции {self.f['обозначение']}")
            return num(a[0]) / num(a[1])
        if op in ("MIN", "MAX"):
            return (min if op == "MIN" else max)(num(x) for x in a)
        if op in (">", ">=", "<", "<="):
            x, y = num(a[0]), num(a[1])
            return {">": x > y, ">=": x >= y, "<": x < y, "<=": x <= y}[op]
        if op == "=":
            return a[0] == a[1]
        if op == "<>":
            return a[0] != a[1]
        if op == "IN":
            return a[0] in a[1:]
        if op == "AND":
            return all(bool(x) for x in a)
        if op == "OR":
            return any(bool(x) for x in a)
        if op == "NOT":
            return not bool(a[0])
        if op == "IF":
            return a[1] if a[0] else a[2]
        raise ConfigError(f"Неизвестный оператор функции {self.f['обозначение']}")

    # ---- печать в текст (инфиксная запись для операторов, NAME(...) для остальных)
    def _wrap(self, e: Expression, right: bool = False) -> str:
        t = e.to_text()
        if e.prec < self.prec or (right and e.prec == self.prec and self.f["оператор"] in ("-", "/")):
            return f"({t})"
        return t

    def to_text(self):
        op = self.f["оператор"]
        if op in INFIX:
            sep = f" {op} "
            return sep.join(self._wrap(a, i > 0) for i, a in enumerate(self.args))
        if op == "NOT":
            a0 = self.args[0]
            inner = a0.to_text()
            return f"NOT ({inner})" if isinstance(a0, CallExpr) and a0.f["оператор"] != "NOT" and \
                (a0.f["оператор"] in INFIX or a0.f["оператор"] == "IN") else f"NOT {inner}"
        if op == "IN":
            return f"{self._wrap(self.args[0])} IN ({', '.join(a.to_text() for a in self.args[1:])})"
        return f"{self.f['обозначение']}({', '.join(a.to_text() for a in self.args)})"

    def type_name(self):
        if self.f["оператор"] == "IF" and len(self.args) == 3:
            return self.args[1].type_name()
        return self.f["тип"] or T_ANY

    def to_tree(self):
        return {"вид": "Вызов функции", "текст": self.f["обозначение"], "пояснение": self.f["наименование"],
                "класс": self.f["класс"], "дети": [a.to_tree() for a in self.args]}

    def check(self) -> None:
        """Проверка числа и типов фактических параметров (по формальным)"""
        fa = self.f["args"]
        n = len(self.args)
        rep = bool(fa) and fa[-1]["повторяемый"]
        if (rep and n < len(fa)) or (not rep and n != len(fa)):
            need = f"не менее {len(fa)}" if rep else str(len(fa))
            raise ConfigError(f"Функция {self.f['обозначение']} ожидает {need} аргумент(а), передано {n}")
        for i, e in enumerate(self.args):
            formal = fa[min(i, len(fa) - 1)]
            want, got = formal["тип"] or T_ANY, e.type_name()
            if T_ANY not in (want, got) and want != got:
                raise ConfigError(f"Аргумент {i + 1} функции {self.f['обозначение']} ({formal['имя']}): "
                                  f"ожидается «{want}», получено «{got}» в «{e.to_text()}»")
        if self.f["оператор"] in ("=", "<>", "IN"):
            kinds = {a.type_name() for a in self.args} - {T_ANY}
            if len(kinds) > 1:
                raise ConfigError(f"Несравнимые значения в «{self.to_text()}»: {', '.join(sorted(kinds))}")

    def source(self, db, svc):
        return {"вложенный_вызов_id": self.save(db, svc)}

    def save(self, db: Session, svc: "ConfigService") -> int:
        call = FunctionCall(функция_id=self.f["id"])
        db.add(call)
        db.flush()
        for i, a in enumerate(self.args, 1):
            db.add(ActualParameter(вызов_id=call.id, номер=i, **a.source(db, svc)))
        db.flush()
        return call.id


class StrLit(Expression):
    """Строковый литерал до разрешения: значение перечисления или строковая константа"""

    def __init__(self, s: str):
        self.s = s

    def interpret(self, ctx):
        return self.s

    def to_text(self):
        return f"'{self.s}'"

    def type_name(self):
        return T_STR

    def to_tree(self):
        return {"вид": "Константа", "текст": self.to_text()}

    def source(self, db, svc):
        return {"константа_id": svc.constant_id(db, self.s)}


TOKEN = re.compile(r"\s*(?:(\d+(?:[.,]\d+)?)|'([^']*)'|\"([^\"]*)\"|«([^»]*)»|(>=|<=|<>|!=|[-+*/(),=<>])|([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*))")
KW = {"AND": "AND", "И": "AND", "OR": "OR", "ИЛИ": "OR", "NOT": "NOT", "НЕ": "NOT", "IN": "IN", "В": "IN"}


class Parser:
    """Разбор текста выражения в дерево Интерпретатора (рекурсивный спуск)"""

    def __init__(self, src: str, lib: Library, names: Dict[str, Dict[str, Any]], enums: Dict[int, Dict[str, int]]):
        self.lib, self.names, self.enums = lib, names, enums
        self.toks: List[Tuple[str, Any]] = []
        pos, src = 0, src.strip()
        while pos < len(src):
            m = TOKEN.match(src, pos)
            if not m or m.end() == pos:
                raise ConfigError(f"Непонятный символ в позиции {pos + 1}: «{src[pos:pos + 10]}»")
            pos = m.end()
            num, s1, s2, s3, op, ident = m.groups()
            if num is not None:
                self.toks.append(("num", float(num.replace(",", "."))))
            elif s1 is not None or s2 is not None or s3 is not None:
                self.toks.append(("str", next(x for x in (s1, s2, s3) if x is not None)))
            elif op is not None:
                self.toks.append(("op", "<>" if op == "!=" else op))
            elif ident.upper() in KW:
                self.toks.append(("kw", KW[ident.upper()]))
            else:
                self.toks.append(("id", ident))
        if not self.toks:
            raise ConfigError("Выражение пустое")
        self.i = 0

    def peek(self, kind=None, val=None):
        if self.i >= len(self.toks):
            return None
        k, v = self.toks[self.i]
        if (kind and k != kind) or (val is not None and v != val):
            return None
        return self.toks[self.i]

    def take(self, kind=None, val=None):
        t = self.peek(kind, val)
        if not t:
            got = self.toks[self.i][1] if self.i < len(self.toks) else "конец выражения"
            raise ConfigError(f"Ожидается «{val or kind}», а найдено «{got}»")
        self.i += 1
        return t

    def parse(self) -> Expression:
        e = self.expr()
        if self.i != len(self.toks):
            raise ConfigError(f"Лишний фрагмент выражения: «{self.toks[self.i][1]}»")
        return e

    def call(self, f, args) -> CallExpr:
        c = CallExpr(f, args, self.lib)
        c.check()
        return c

    def nary(self, kw, sub):
        items = [sub()]
        while self.peek("kw", kw):
            self.take()
            items.append(sub())
        return items[0] if len(items) == 1 else self.call(self.lib.op(kw), items)

    def expr(self):
        return self.nary("OR", self.and_expr)

    def and_expr(self):
        return self.nary("AND", self.not_expr)

    def not_expr(self):
        if self.peek("kw", "NOT"):
            self.take()
            return self.call(self.lib.op("NOT"), [self.not_expr()])
        return self.cmp()

    def resolve(self, left: Expression, items: List[Expression]) -> List[Expression]:
        """Строки рядом с параметром-перечислением превращаются в значения перечисления"""
        if isinstance(left, ParamExpr) and left.p["тип"] == "ENUM":
            vals = self.enums.get(left.p["перечисление_id"], {})
            out = []
            for e in items:
                if isinstance(e, StrLit):
                    key = e.s.strip().lower()
                    if key not in vals:
                        raise ConfigError(f"У параметра {left.p['обозначение']} нет значения «{e.s}». "
                                          f"Допустимо: {', '.join(v[1] for v in vals.values())}")
                    e = EnumExpr(vals[key][0], vals[key][1])
                out.append(e)
            return out
        return items

    def cmp(self):
        left = self.add()
        t = self.peek("op")
        if t and t[1] in (">", ">=", "<", "<=", "=", "<>"):
            self.take()
            right = self.add()
            right = self.resolve(left, [right])[0]
            left = self.resolve(right, [left])[0]
            return self.call(self.lib.op(t[1]), [left, right])
        if self.peek("kw", "IN"):
            self.take()
            self.take("op", "(")
            items = [self.add()]
            while self.peek("op", ","):
                self.take()
                items.append(self.add())
            self.take("op", ")")
            return self.call(self.lib.op("IN"), [left] + self.resolve(left, items))
        return left

    def fold(self, sub, ops):
        left = sub()
        while self.peek("op") and self.peek("op")[1] in ops:
            o = self.take()[1]
            right = sub()
            if o in ("+", "*") and isinstance(left, CallExpr) and left.f["оператор"] == o:
                left = self.call(left.f, left.args + [right])
            else:
                left = self.call(self.lib.op(o), [left, right])
        return left

    def add(self):
        return self.fold(self.mul, ("+", "-"))

    def mul(self):
        return self.fold(self.unary, ("*", "/"))

    def unary(self):
        if self.peek("op", "-"):
            self.take()
            e = self.unary()
            if isinstance(e, ConstExpr):
                return ConstExpr(-e.value)
            return self.call(self.lib.op("-"), [ConstExpr(0.0), e])
        return self.primary()

    def primary(self):
        t = self.take()
        k, v = t
        if k == "num":
            return ConstExpr(v)
        if k == "str":
            return StrLit(v)
        if k == "op" and v == "(":
            e = self.expr()
            self.take("op", ")")
            return e
        if k == "id":
            if self.peek("op", "("):
                f = self.lib.by_name.get(v.upper()) or self.lib.by_name.get({"ЕСЛИ": "IF"}.get(v.upper(), ""))
                if not f:
                    raise ConfigError(f"Функция «{v}» не найдена в библиотеке функций")
                self.take()
                args = []
                if not self.peek("op", ")"):
                    args.append(self.expr())
                    while self.peek("op", ","):
                        self.take()
                        args.append(self.expr())
                self.take("op", ")")
                if f["оператор"] in ("=", "<>") and len(args) == 2:
                    args = [args[0]] + self.resolve(args[0], [args[1]])
                if f["оператор"] == "IN" and args:
                    args = [args[0]] + self.resolve(args[0], args[1:])
                return self.call(f, args)
            n = self.names.get(v.lower())
            if not n:
                raise ConfigError(f"«{v}» — не параметр конфигурации этого изделия и не аргумент функции. "
                                  f"Доступно: {', '.join(x['обозначение'] if 'обозначение' in x else x['имя'] for x in self.names.values()) or 'нет'}")
            return ArgExpr(n) if "имя" in n else ParamExpr(n)
        raise ConfigError(f"Неожиданный элемент «{v}»")


# =============================================================================== Прототип
class VariantPrototype:
    """Прототип варианта исполнения: шаблон (или готовый вариант) клонируется с новыми значениями параметров"""

    def __init__(self, svc: "ConfigService", db: Session, product_id: int):
        p = db.get(Product, product_id)
        if not p or p.вид_конфигурации not in ("ТИПОВОЕ", "ВАРИАНТ"):
            raise ConfigError("Прототипом может быть типовое изделие или вариант исполнения")
        self.svc, self.db = svc, db
        self.template_id = p.id if p.вид_конфигурации == "ТИПОВОЕ" else p.шаблон_id
        self.values = {} if p.вид_конфигурации == "ТИПОВОЕ" else svc.variant_values(db, p.id)

    def clone(self, changes: Dict[int, Any]) -> int:
        vals = {**self.values, **{int(k): v for k, v in changes.items()}}
        return self.svc.sql_create_variant(self.db, self.template_id, vals)


# =============================================================================== сервис
class ConfigService:

    # ------------------------------------------------------------ общие
    def lib(self, db: Session) -> Library:
        return Library(db)

    def constant_id(self, db: Session, value: Any) -> int:
        lib = Library(db)
        is_num = isinstance(value, (int, float))
        q = db.query(Constant)
        c = (q.filter(Constant.значение_число == float(value)) if is_num
             else q.filter(Constant.значение_строка == str(value))).first()
        if c:
            return c.id
        c = Constant(наименование=_num_text(value) if is_num else str(value), тип_id=lib.type_id[T_NUM if is_num else T_STR],
                     значение_число=float(value) if is_num else None, значение_строка=None if is_num else str(value))
        db.add(c)
        db.flush()
        return c.id

    def config_params(self, db: Session, product_id: int) -> List[Dict[str, Any]]:
        rows = db.execute(text("SELECT * FROM get_config_params(:p) ORDER BY порядок, параметр_id"),
                          {"p": product_id}).mappings().all()
        enums = self._enum_values(db)
        return [{"параметр_класса_id": r["параметр_класса_id"], "id": r["параметр_id"], "обозначение": r["обозначение"],
                 "полное_имя": r["полное_имя"], "тип": r["тип_параметра"], "ед_изм": r["единица_измерения"],
                 "перечисление_id": r["перечисление_id"], "мин": r["мин_значение"], "макс": r["макс_значение"],
                 "по_умолчанию": r["значение_по_умолчанию"], "обязательный": r["обязательный"],
                 "значения": [{"id": i, "value": n} for i, n in enums.get(r["перечисление_id"], [])]}
                for r in rows]

    def _enum_values(self, db: Session) -> Dict[int, List[Tuple[int, str]]]:
        out: Dict[int, List[Tuple[int, str]]] = {}
        for v in db.query(EnumValue).order_by(EnumValue.enumeration_id, EnumValue.sort_order, EnumValue.id).all():
            out.setdefault(v.enumeration_id, []).append((v.id, v.value))
        return out

    def _template(self, db: Session, product_id: int) -> Product:
        p = db.get(Product, product_id)
        if not p:
            raise ConfigError("Изделие не найдено")
        if p.вид_конфигурации != "ТИПОВОЕ":
            raise ConfigError(f"«{p.наименование}» не является типовым изделием с конфигуратором")
        return p

    def _parser(self, db: Session, src: str, product_id: Optional[int] = None,
                args: Optional[List[Dict[str, Any]]] = None) -> Parser:
        lib = Library(db)
        names: Dict[str, Dict[str, Any]] = {}
        if product_id:
            for p in self.config_params(db, product_id):
                names[p["обозначение"].lower()] = p
        for a in args or []:
            names[a["имя"].lower()] = a
        enums = {eid: {n.lower(): (i, n) for i, n in vals} for eid, vals in self._enum_values(db).items()}
        return Parser(src, lib, names, enums)

    def parse(self, db: Session, src: str, product_id: Optional[int] = None, want: Optional[str] = None,
              args: Optional[List[Dict[str, Any]]] = None) -> Expression:
        e = self._parser(db, src, product_id, args).parse()
        if want and e.type_name() not in (want, T_ANY):
            raise ConfigError(f"Выражение должно давать «{want}», а даёт «{e.type_name()}»")
        if not isinstance(e, CallExpr):
            raise ConfigError("Выражение должно содержать хотя бы одну функцию (сравнение, логическую или арифметическую операцию)")
        return e

    def load_call(self, db: Session, call_id: int, lib: Optional[Library] = None) -> CallExpr:
        lib = lib or Library(db)
        call = db.get(FunctionCall, call_id)
        f = lib.funcs[call.функция_id]
        args: List[Expression] = []
        for fp in call.params:
            if fp.параметр_id:
                p = db.get(Parameter, fp.параметр_id)
                args.append(ParamExpr({"id": p.id, "обозначение": p.обозначение, "полное_имя": p.полное_имя,
                                       "тип": p.тип_параметра, "перечисление_id": p.перечисление_id}))
            elif fp.константа_id:
                c = db.get(Constant, fp.константа_id)
                args.append(ConstExpr(c.значение_число if c.значение_число is not None else c.значение_строка, c.id))
            elif fp.значение_перечисления_id:
                ev = db.get(EnumValue, fp.значение_перечисления_id)
                args.append(EnumExpr(ev.id, ev.value))
            elif fp.вложенный_вызов_id:
                args.append(self.load_call(db, fp.вложенный_вызов_id, lib))
            else:
                a = next(x for fx in lib.funcs.values() for x in fx["args"] if x["id"] == fp.аргумент_id)
                args.append(ArgExpr(a))
        return CallExpr(f, args, lib)

    def delete_call(self, db: Session, call_id: Optional[int]) -> None:
        if not call_id:
            return
        call = db.get(FunctionCall, call_id)
        if not call:
            return
        nested = [fp.вложенный_вызов_id for fp in call.params if fp.вложенный_вызов_id]
        db.delete(call)
        db.flush()
        for n in nested:
            self.delete_call(db, n)

    def _expr_json(self, db: Session, call_id: Optional[int], lib: Library) -> Optional[Dict[str, Any]]:
        if not call_id:
            return None
        e = self.load_call(db, call_id, lib)
        return {"вызов_id": call_id, "текст": e.to_text(), "дерево": e.to_tree()}

    @staticmethod
    def _values(raw: Dict[Any, Any]) -> Dict[int, Any]:
        out = {}
        for k, v in (raw or {}).items():
            if v is None or v == "":
                continue
            out[int(k)] = v
        return out

    # ------------------------------------------------------------ справочники
    def references(self, db: Session) -> Dict[str, Any]:
        lib = Library(db)
        return {"типы": [{"id": i, "name": n} for i, n in lib.types.items()],
                "классы_функций": [{"id": i, "name": n} for i, n in lib.classes.items()],
                "заказчики": [{"id": s.id, "name": s.наименование, "контактное_лицо": s.контактное_лицо,
                               "телефон": s.телефон} for s in db.query(Subject).filter(Subject.инн.isnot(None), Subject.инн != "")
                               .order_by(Subject.наименование).all()],
                "перечисления": [{"id": e.id, "name": e.name,
                                  "значения": [{"id": v.id, "value": v.value} for v in
                                               sorted(e.values, key=lambda x: (x.sort_order or 0, x.id))]}
                                 for e in db.query(Enumeration).filter(Enumeration.id.in_(
                                     db.query(Parameter.перечисление_id).filter(Parameter.перечисление_id.isnot(None))))
                                 .order_by(Enumeration.name).all()]}

    def products(self, db: Session, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        q = db.query(Product)
        if kind:
            q = q.filter(Product.вид_конфигурации == kind)
        cls = {c.id: c.название for c in db.query(Classificator).all()}
        return [{"id": p.id, "наименование": p.наименование, "артикул": p.артикул, "класс": cls.get(p.класс_id),
                 "тип_изделия": p.тип_изделия, "вид_конфигурации": p.вид_конфигурации, "цена": p.цена,
                 "шаблон_id": p.шаблон_id}
                for p in q.order_by(Product.вид_конфигурации, Product.наименование).all()]

    def set_kind(self, db: Session, product_id: int, kind: str, price: Optional[float]) -> Dict[str, Any]:
        """Описание шаблона: изделие становится типовым с конфигуратором (или снова простым)"""
        p = db.get(Product, product_id)
        if not p:
            raise ConfigError("Изделие не найдено")
        if kind not in ("ПРОСТОЕ", "ТИПОВОЕ"):
            raise ConfigError("Вид может быть ПРОСТОЕ или ТИПОВОЕ; вариант исполнения создаётся из шаблона")
        if p.вид_конфигурации == "ВАРИАНТ":
            raise ConfigError("Вариант исполнения нельзя перевести в другой вид")
        if kind == "ПРОСТОЕ" and p.вид_конфигурации == "ТИПОВОЕ":
            if db.query(Product).filter(Product.шаблон_id == p.id).count():
                raise ConfigError("По шаблону уже созданы варианты исполнения — снять признак нельзя")
            if db.query(ProductConstraint).filter(ProductConstraint.изделие_id == p.id).count():
                raise ConfigError("У шаблона есть ограничения — сначала удалите их")
        if kind == "ТИПОВОЕ" and db.query(OrderItem).filter(OrderItem.изделие_id == p.id).count():
            raise ConfigError("Изделие уже есть в заказах — сделать его шаблоном нельзя")
        if price is not None and price < 0:
            raise ConfigError("Цена не может быть отрицательной")
        p.вид_конфигурации = kind
        if price is not None:
            p.цена = price
        db.commit()
        return {"success": True}

    # ------------------------------------------------------------ типовые изделия (шаблоны)
    def templates(self, db: Session) -> List[Dict[str, Any]]:
        rows = db.execute(text("""
            SELECT p.id, p."наименование", p."артикул", p."цена", k."название" AS класс,
                   (SELECT count(*) FROM get_config_params(p.id)) AS параметров,
                   (SELECT count(*) FROM "ограничение" o WHERE o."изделие_id" = p.id) AS ограничений,
                   (SELECT count(*) FROM "изделие" v WHERE v."шаблон_id" = p.id) AS вариантов
            FROM "изделие" p LEFT JOIN "классификатор" k ON k.id = p."класс_id"
            WHERE p."вид_конфигурации" = 'ТИПОВОЕ' ORDER BY p."наименование" """)).mappings().all()
        return [dict(r) for r in rows]

    def template_card(self, db: Session, product_id: int) -> Dict[str, Any]:
        p = self._template(db, product_id)
        lib = Library(db)
        cls = db.get(Classificator, p.класс_id)
        # все параметры класса (с наследованием) — для выбора параметров конфигурации
        rows = db.execute(text("""
            WITH RECURSIVE anc(id, depth) AS (SELECT CAST(:c AS integer), 0 UNION ALL
                SELECT k."родительский_id", anc.depth + 1 FROM anc JOIN "классификатор" k ON k.id = anc.id
                WHERE k."родительский_id" IS NOT NULL)
            SELECT pc.id, pc."класс_id", kk."название" AS класс, par.id AS параметр_id, par."обозначение",
                   par."полное_имя", par."тип_параметра", par."единица_измерения", pc."мин_значение",
                   pc."макс_значение", pc."флаг_конфигурации", anc.depth
            FROM anc JOIN "параметр_класса" pc ON pc."класс_id" = anc.id
            JOIN "параметр" par ON par.id = pc."параметр_id" JOIN "классификатор" kk ON kk.id = pc."класс_id"
            ORDER BY anc.depth, pc."порядковый_номер", pc.id"""), {"c": p.класс_id}).mappings().all()
        constraints = []
        for c in db.query(ProductConstraint).filter(ProductConstraint.изделие_id == p.id) \
                .order_by(ProductConstraint.порядок, ProductConstraint.id).all():
            constraints.append({"id": c.id, "наименование": c.наименование, "сообщение": c.сообщение,
                                "активно": c.активно, "порядок": c.порядок, **self._expr_json(db, c.вызов_id, lib)})
        variants = [{"id": v.id, "наименование": v.наименование, "артикул": v.артикул, "цена": v.цена,
                     "в_заказах": db.query(OrderItem).filter(OrderItem.изделие_id == v.id).count()}
                    for v in db.query(Product).filter(Product.шаблон_id == p.id).order_by(Product.id).all()]
        return {"id": p.id, "наименование": p.наименование, "артикул": p.артикул, "цена": p.цена,
                "класс_id": p.класс_id, "класс": cls.название if cls else None,
                "параметры_класса": [dict(r) for r in rows], "параметры_конфигурации": self.config_params(db, p.id),
                "ограничения": constraints, "формула_цены": self._expr_json(db, p.формула_цены_id, lib),
                "варианты": variants}

    def set_config_param(self, db: Session, pc_id: int, flag: bool, mn: Optional[float], mx: Optional[float],
                         required: Optional[bool] = None) -> Dict[str, Any]:
        """Описание состава параметров конфигурации: флаг FLAG_CONF и диапазон Min/Max"""
        pc = db.get(ParameterClass, pc_id)
        if not pc:
            raise ConfigError("Параметр класса не найден")
        par = db.get(Parameter, pc.параметр_id)
        if par.тип_параметра not in ("REAL", "INTEGER", "ENUM"):
            raise ConfigError("Параметром конфигурации может быть число или перечисление")
        if par.тип_параметра == "ENUM" and (mn is not None or mx is not None):
            raise ConfigError("Для перечисления диапазон не задаётся")
        if mn is not None and mx is not None and mn > mx:
            raise ConfigError("Минимум больше максимума")
        if not flag:
            used = db.execute(text("""
                WITH RECURSIVE cls(id) AS (SELECT CAST(:k AS integer) UNION ALL
                    SELECT k.id FROM "классификатор" k JOIN cls ON k."родительский_id" = cls.id),
                roots(id) AS (SELECT o."вызов_id" FROM "ограничение" o JOIN "изделие" t ON t.id = o."изделие_id"
                              WHERE t."класс_id" IN (SELECT id FROM cls)
                              UNION SELECT t."формула_цены_id" FROM "изделие" t
                              WHERE t."формула_цены_id" IS NOT NULL AND t."класс_id" IN (SELECT id FROM cls)),
                calls(id) AS (SELECT id FROM roots UNION ALL
                    SELECT fp."вложенный_вызов_id" FROM "фактический_параметр" fp JOIN calls c ON fp."вызов_id" = c.id
                    WHERE fp."вложенный_вызов_id" IS NOT NULL)
                SELECT count(*) FROM "фактический_параметр" fp JOIN calls c ON fp."вызов_id" = c.id
                WHERE fp."параметр_id" = :p"""), {"p": par.id, "k": pc.класс_id}).scalar()
            if used:
                raise ConfigError(f"Параметр {par.обозначение} используется в ограничениях или формуле цены")
        pc.флаг_конфигурации = flag
        pc.мин_значение, pc.макс_значение = mn, mx
        if required is not None:
            pc.обязательный = 1 if required else 0
        db.commit()
        return {"success": True}

    def add_constraint(self, db: Session, product_id: int, name: str, src: str, message: Optional[str]) -> Dict[str, Any]:
        """Описание ограничения: текст → дерево вызовов функций → таблицы"""
        self._template(db, product_id)
        e = self.parse(db, src, product_id, T_BOOL)
        call_id = e.save(db, self)
        order = (db.query(ProductConstraint).filter(ProductConstraint.изделие_id == product_id).count() + 1) * 10
        c = ProductConstraint(изделие_id=product_id, вызов_id=call_id, наименование=name.strip(),
                              сообщение=(message or "").strip() or None, активно=True, порядок=order)
        db.add(c)
        db.commit()
        return {"success": True, "id": c.id, "текст": e.to_text()}

    def update_constraint(self, db: Session, cid: int, name: str, src: Optional[str], message: Optional[str],
                          active: bool) -> Dict[str, Any]:
        c = db.get(ProductConstraint, cid)
        if not c:
            raise ConfigError("Ограничение не найдено")
        if src:
            e = self.parse(db, src, c.изделие_id, T_BOOL)
            old = c.вызов_id
            c.вызов_id = e.save(db, self)
            db.flush()
            self.delete_call(db, old)
        c.наименование, c.сообщение, c.активно = name.strip(), (message or "").strip() or None, active
        db.commit()
        return {"success": True}

    def delete_constraint(self, db: Session, cid: int) -> Dict[str, Any]:
        c = db.get(ProductConstraint, cid)
        if not c:
            raise ConfigError("Ограничение не найдено")
        call = c.вызов_id
        db.delete(c)
        db.flush()
        self.delete_call(db, call)
        db.commit()
        return {"success": True}

    def set_price_formula(self, db: Session, product_id: int, src: Optional[str], price: Optional[float]) -> Dict[str, Any]:
        p = self._template(db, product_id)
        old = p.формула_цены_id
        if src and src.strip():
            e = self.parse(db, src, product_id, T_NUM)
            p.формула_цены_id = e.save(db, self)
        else:
            p.формула_цены_id = None
        if price is not None:
            p.цена = price
        db.flush()
        self.delete_call(db, old)
        db.commit()
        return {"success": True}

    def preview(self, db: Session, src: str, product_id: Optional[int], values: Dict[Any, Any],
                args: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Разобрать выражение без сохранения: текст, дерево, тип и значение на заданных значениях"""
        if args:
            lib = Library(db)
            args = [{"id": None, "номер": i, "имя": a["имя"].strip(), "тип": lib.types.get(a.get("тип_id")) or T_ANY,
                     "повторяемый": False} for i, a in enumerate(args, 1) if a.get("имя", "").strip()]
        e = self._parser(db, src, product_id, args).parse()
        out = {"текст": e.to_text(), "тип": e.type_name(), "дерево": e.to_tree()}
        vals = self._values(values)
        if vals:
            try:
                out["значение"] = e.interpret({"values": vals, "args": [], "db": db, "svc": self})
            except (ConfigError, KeyError, TypeError, ValueError) as ex:
                out["ошибка_вычисления"] = str(ex)
        return out

    def check(self, db: Session, product_id: int, values: Dict[Any, Any]) -> Dict[str, Any]:
        """CHECK_CONSTRAINTS — проверка ограничений для набора значений"""
        self._template(db, product_id)
        vals = self._values(values)
        rows = db.execute(text("SELECT * FROM check_constraints(:p, CAST(:v AS jsonb))"),
                          {"p": product_id, "v": json.dumps(vals)}).mappings().all()
        ok = all(r["результат"] for r in rows)
        price = None
        if ok:
            price = db.execute(text("SELECT variant_price(:p, CAST(:v AS jsonb))"),
                               {"p": product_id, "v": json.dumps(vals)}).scalar()
        return {"success": True, "допустимо": ok, "цена": price, "проверки": [dict(r) for r in rows]}

    def sql_create_variant(self, db: Session, template_id: int, vals: Dict[int, Any]) -> int:
        try:
            vid = db.execute(text("SELECT create_variant(:p, CAST(:v AS jsonb))"),
                             {"p": template_id, "v": json.dumps({str(k): v for k, v in vals.items()})}).scalar()
        except Exception as ex:   # RAISE EXCEPTION из процедуры
            db.rollback()
            raise ConfigError(_pg_msg(ex))
        return vid

    def create_variant(self, db: Session, product_id: int, values: Dict[Any, Any]) -> Dict[str, Any]:
        """CREATE_VARIANT через Прототип: клон шаблона с заданными значениями"""
        vid = VariantPrototype(self, db, product_id).clone(self._values(values))
        db.commit()
        return {"success": True, **self.variant_card(db, vid)}

    def variant_values(self, db: Session, variant_id: int) -> Dict[int, Any]:
        rows = db.execute(text("""SELECT pc."параметр_id", v."значение_число", v."значение_перечисление_id"
            FROM "значение_параметра" v JOIN "параметр_класса" pc ON pc.id = v."параметр_класса_id"
            WHERE v."изделие_id" = :v"""), {"v": variant_id}).all()
        return {pid: (en if en is not None else num) for pid, num, en in rows}

    def variant_card(self, db: Session, variant_id: int) -> Dict[str, Any]:
        v = db.get(Product, variant_id)
        if not v or v.вид_конфигурации != "ВАРИАНТ":
            raise ConfigError("Вариант исполнения не найден")
        vals = self.variant_values(db, v.id)
        params = self.config_params(db, v.шаблон_id)
        enum_names = {ev.id: ev.value for ev in db.query(EnumValue).all()}
        shown = [{"параметр_id": p["id"], "обозначение": p["обозначение"], "полное_имя": p["полное_имя"],
                  "ед_изм": p["ед_изм"], "значение": vals.get(p["id"]),
                  "текст": enum_names.get(vals.get(p["id"])) if p["тип"] == "ENUM" else _num_text(vals.get(p["id"]))}
                 for p in params]
        return {"id": v.id, "наименование": v.наименование, "артикул": v.артикул, "цена": v.цена,
                "шаблон_id": v.шаблон_id, "шаблон": db.get(Product, v.шаблон_id).наименование,
                "значения": {str(k): x for k, x in vals.items()}, "параметры": shown}

    # ------------------------------------------------------------ библиотека функций
    def functions(self, db: Session) -> List[Dict[str, Any]]:
        lib = Library(db)
        used = dict(db.execute(text("""SELECT "функция_id", count(*) FROM "вызов_функции" GROUP BY 1""")).all())
        out = []
        for f in sorted(lib.funcs.values(), key=lambda x: (x["класс"] or "", x["обозначение"])):
            body = self._expr_json(db, f["тело_вызов_id"], lib)
            sig = ", ".join(a["имя"] + ("…" if a["повторяемый"] else "") for a in f["args"])
            out.append({**{k: v for k, v in f.items() if k != "args"}, "аргументы": f["args"],
                        "сигнатура": f"{f['обозначение']}({sig})", "тело": body, "составная": bool(f["тело_вызов_id"]),
                        "вызовов": used.get(f["id"], 0)})
        return out

    def add_function(self, db: Session, code: str, name: str, class_id: int, args: List[Dict[str, Any]],
                     body: str, description: Optional[str]) -> Dict[str, Any]:
        """Новая функция библиотеки с формальными параметрами: тело — выражение над аргументами"""
        lib = Library(db)
        code = code.strip().upper()
        if not re.fullmatch(r"[A-ZА-ЯЁ_][A-ZА-ЯЁ_0-9]*", code):
            raise ConfigError("Обозначение функции: буквы, цифры и «_», начинается с буквы")
        if code in lib.by_name or code in KW:
            raise ConfigError(f"Функция {code} уже есть в библиотеке")
        if class_id not in lib.classes:
            raise ConfigError("Укажите класс функции из классификатора функций")
        if not args:
            raise ConfigError("Нужен хотя бы один формальный параметр")
        names = [a["имя"].strip() for a in args]
        if len({n.lower() for n in names}) != len(names):
            raise ConfigError("Имена аргументов повторяются")
        f = ConstraintFunction(обозначение=code, наименование=name.strip(), класс_id=class_id,
                               тип_результата_id=lib.type_id[T_ANY], описание=description)
        db.add(f)
        db.flush()
        formal = []
        for i, a in enumerate(args, 1):
            if a.get("тип_id") not in lib.types:
                raise ConfigError(f"Тип аргумента {a['имя']} не задан")
            fa = FunctionArgument(функция_id=f.id, номер=i, имя=a["имя"].strip(), тип_id=a["тип_id"], повторяемый=False)
            db.add(fa)
            db.flush()
            formal.append({"id": fa.id, "номер": i, "имя": fa.имя, "тип": lib.types[a["тип_id"]], "повторяемый": False})
        e = self.parse(db, body, None, None, formal)
        f.тело_вызов_id = e.save(db, self)
        f.тип_результата_id = lib.type_id.get(e.type_name(), lib.type_id[T_ANY])
        db.commit()
        return {"success": True, "id": f.id, "тело": e.to_text()}

    def evaluate_function(self, db: Session, fid: int, values: List[Any]) -> Dict[str, Any]:
        """Функция_ограничения.Вычислить(аргументы): временный вызов с константами вычисляется EVAL_FUNCTION"""
        lib = Library(db)
        f = lib.funcs.get(fid)
        if not f:
            raise ConfigError("Функция не найдена")
        fa = f["args"]
        rep = bool(fa) and fa[-1]["повторяемый"]
        if (rep and len(values) < len(fa)) or (not rep and len(values) != len(fa)):
            raise ConfigError(f"Функция {f['обозначение']} ожидает {'не менее ' if rep else ''}{len(fa)} аргумент(а), "
                              f"передано {len(values)}")
        enum_names = {ev.id: ev.value for ev in db.query(EnumValue).all()}
        sources, shown = [], []
        for i, raw in enumerate(values):
            formal = fa[min(i, len(fa) - 1)]
            t = formal["тип"] or T_ANY
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                raise ConfigError(f"Не задано значение аргумента {formal['имя']}")
            if t == T_ENUM:
                try:
                    ev = int(raw)
                except (TypeError, ValueError):
                    raise ConfigError(f"Аргумент {formal['имя']}: выберите значение перечисления")
                if ev not in enum_names:
                    raise ConfigError(f"Аргумент {formal['имя']}: значение перечисления не найдено")
                sources.append(("enum", ev)); shown.append(f"'{enum_names[ev]}'")
            elif t == T_BOOL:
                b = raw if isinstance(raw, bool) else str(raw).strip().lower() in ("true", "1", "да", "истина")
                sources.append(("bool", b)); shown.append("истина" if b else "ложь")
            else:
                try:
                    num = float(str(raw).replace(",", "."))
                    sources.append(("num", num)); shown.append(_num_text(num))
                except ValueError:
                    if t == T_NUM:
                        raise ConfigError(f"Аргумент {formal['имя']}: ожидается число, получено «{raw}»")
                    sources.append(("str", str(raw))); shown.append(f"'{raw}'")
        sp = db.begin_nested()       # временный вызов не сохраняется
        try:
            call = FunctionCall(функция_id=fid)
            db.add(call)
            db.flush()
            for i, (kind, v) in enumerate(sources, 1):
                if kind == "enum":
                    db.add(ActualParameter(вызов_id=call.id, номер=i, значение_перечисления_id=v))
                    continue
                if kind == "bool":
                    c = Constant(наименование="истина" if v else "ложь", тип_id=lib.type_id[T_BOOL], значение_число=1.0 if v else 0.0)
                else:
                    c = Constant(наименование=_num_text(v) if kind == "num" else v,
                                 тип_id=lib.type_id[T_NUM if kind == "num" else T_STR],
                                 значение_число=v if kind == "num" else None, значение_строка=v if kind == "str" else None)
                db.add(c)
                db.flush()
                db.add(ActualParameter(вызов_id=call.id, номер=i, константа_id=c.id))
            db.flush()
            res = db.execute(text("SELECT eval_function(:c, '{}'::jsonb)"), {"c": call.id}).scalar()
        except Exception as ex:
            sp.rollback()
            raise ConfigError(_pg_msg(ex))
        sp.rollback()
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except ValueError:
                pass
        if f["тип"] == T_BOOL and isinstance(res, (int, float)) and not isinstance(res, bool):
            res = bool(res)
        text_res = ("истина" if res else "ложь") if isinstance(res, bool) else \
            (_num_text(res) if isinstance(res, (int, float)) else str(res))
        return {"success": True, "вызов": f"{f['обозначение']}({', '.join(shown)})", "результат": res,
                "результат_текст": text_res, "тип": f["тип"]}

    def delete_function(self, db: Session, fid: int) -> Dict[str, Any]:
        f = db.get(ConstraintFunction, fid)
        if not f:
            raise ConfigError("Функция не найдена")
        if not f.тело_вызов_id:
            raise ConfigError("Встроенную функцию (с оператором) удалить нельзя")
        if db.query(FunctionCall).filter(FunctionCall.функция_id == fid).count():
            raise ConfigError("Функция используется в ограничениях — сначала удалите их")
        body = f.тело_вызов_id
        f.тело_вызов_id = None
        db.flush()
        self.delete_call(db, body)
        db.delete(f)
        db.commit()
        return {"success": True}

    # ------------------------------------------------------------ заказы
    def orders(self, db: Session) -> List[Dict[str, Any]]:
        rows = db.execute(text("""
            SELECT z.id, z."номер", z."дата_регистрации", z."срок_изготовления", z."статус", s."наименование" AS заказчик,
                   (SELECT count(*) FROM "позиция_заказа" p WHERE p."заказ_id" = z.id) AS позиций,
                   order_total(z.id) AS сумма
            FROM "заказ" z JOIN "субъект_хоз_деятельности" s ON s.id = z."заказчик_id"
            ORDER BY z."дата_регистрации" DESC, z.id DESC""")).mappings().all()
        return [dict(r) for r in rows]

    def _order(self, db: Session, oid: int, draft: bool = False) -> Order:
        o = db.get(Order, oid)
        if not o:
            raise ConfigError("Заказ не найден")
        if draft and o.статус != "ЧЕРНОВИК":
            raise ConfigError(f"Заказ {o.номер} согласован — изменять его нельзя")
        return o

    def save_order(self, db: Session, oid: Optional[int], data: Dict[str, Any]) -> Dict[str, Any]:
        cust = db.get(Subject, data.get("заказчик_id") or 0)
        if not cust:
            raise ConfigError("Выберите заказчика")
        if not (cust.инн or "").strip():
            raise ConfigError(f"«{cust.наименование}» – не внешний контрагент (не указан ИНН (идентификационный номер налогоплательщика)) и не может быть заказчиком")
        reg = data.get("дата_регистрации") or date.today()
        due = data.get("срок_изготовления")
        if due and due < reg:
            raise ConfigError("Срок изготовления раньше даты регистрации")
        if oid:
            o = self._order(db, oid, draft=True)
        else:
            o = Order(статус="ЧЕРНОВИК")
            n = db.execute(text("""SELECT count(*) FROM "заказ" WHERE extract(year FROM "дата_регистрации") = :y"""),
                           {"y": reg.year}).scalar()
            o.номер = data.get("номер") or f"З-{reg.year}-{n + 1:03d}"
            db.add(o)
        if data.get("номер"):
            o.номер = data["номер"].strip()
        o.дата_регистрации, o.срок_изготовления, o.заказчик_id = reg, due, data["заказчик_id"]
        o.контактное_лицо, o.телефон, o.примечание = data.get("контактное_лицо"), data.get("телефон"), data.get("примечание")
        db.commit()
        return {"success": True, "id": o.id, "номер": o.номер}

    def delete_order(self, db: Session, oid: int) -> Dict[str, Any]:
        o = self._order(db, oid, draft=True)
        db.delete(o)
        db.commit()
        return {"success": True}

    def set_status(self, db: Session, oid: int, status: str) -> Dict[str, Any]:
        """Согласование заказа (отдел сбыта) или возврат в черновик"""
        o = self._order(db, oid)
        if status not in ORDER_STATUSES:
            raise ConfigError("Статус: ЧЕРНОВИК или СОГЛАСОВАН")
        if status == "СОГЛАСОВАН" and not o.items:
            raise ConfigError("Нельзя согласовать пустой заказ")
        o.статус = status
        db.commit()
        return {"success": True}

    def order_card(self, db: Session, oid: int) -> Dict[str, Any]:
        o = self._order(db, oid)
        s = db.get(Subject, o.заказчик_id)
        items = []
        for it in o.items:
            p = db.get(Product, it.изделие_id)
            params = self.variant_card(db, p.id)["параметры"] if p.вид_конфигурации == "ВАРИАНТ" else []
            items.append({"id": it.id, "номер": it.номер, "изделие_id": p.id, "изделие": p.наименование,
                          "артикул": p.артикул, "вид_конфигурации": p.вид_конфигурации, "шаблон_id": p.шаблон_id,
                          "шаблон": db.get(Product, p.шаблон_id).наименование if p.шаблон_id else None,
                          "параметры": params, "количество": it.количество, "цена": it.цена,
                          "стоимость": it.количество * it.цена})
        total = db.execute(text("SELECT order_total(:o)"), {"o": o.id}).scalar()
        return {"id": o.id, "номер": o.номер, "дата_регистрации": o.дата_регистрации,
                "срок_изготовления": o.срок_изготовления, "статус": o.статус, "заказчик_id": o.заказчик_id,
                "заказчик": s.наименование, "контактное_лицо": o.контактное_лицо, "телефон": o.телефон,
                "примечание": o.примечание, "позиции": items, "сумма": total}

    def add_item(self, db: Session, oid: int, product_id: int, qty: float) -> Dict[str, Any]:
        """ADD_TO_ORDER"""
        self._order(db, oid, draft=True)
        try:
            pos = db.execute(text("SELECT add_to_order(:o, :p, :q)"), {"o": oid, "p": product_id, "q": qty}).scalar()
        except Exception as ex:
            db.rollback()
            raise ConfigError(_pg_msg(ex))
        db.commit()
        return {"success": True, "позиция_id": pos}

    def configure_item(self, db: Session, oid: int, product_id: int, values: Dict[Any, Any], qty: float) -> Dict[str, Any]:
        """Задание варианта исполнения прямо в заказе: Прототип.clone → CREATE_VARIANT → ADD_TO_ORDER"""
        self._order(db, oid, draft=True)
        if qty is None or qty <= 0:
            raise ConfigError("Количество должно быть больше нуля")
        vid = VariantPrototype(self, db, product_id).clone(self._values(values))
        res = self.add_item(db, oid, vid, qty)
        return {**res, "вариант": self.variant_card(db, vid)}

    def update_item(self, db: Session, item_id: int, qty: float) -> Dict[str, Any]:
        it = db.get(OrderItem, item_id)
        if not it:
            raise ConfigError("Позиция заказа не найдена")
        self._order(db, it.заказ_id, draft=True)
        if qty is None or qty <= 0:
            raise ConfigError("Количество должно быть больше нуля")
        it.количество = qty
        db.commit()
        return {"success": True}

    def delete_item(self, db: Session, item_id: int) -> Dict[str, Any]:
        it = db.get(OrderItem, item_id)
        if not it:
            raise ConfigError("Позиция заказа не найдена")
        oid = it.заказ_id
        self._order(db, oid, draft=True)
        db.delete(it)
        db.flush()
        for i, x in enumerate(db.query(OrderItem).filter(OrderItem.заказ_id == oid).order_by(OrderItem.номер).all(), 1):
            x.номер = -i
        db.flush()
        for x in db.query(OrderItem).filter(OrderItem.заказ_id == oid).all():
            x.номер = -x.номер
        db.commit()
        return {"success": True}


config_service = ConfigService()


# =============================================================================== демо-данные
def load_config_test_data(db: Session, classifier) -> None:
    if db.query(ConstraintFunction).count():
        print("  [ПР7] данные конфигуратора уже загружены")
        return
    svc = config_service

    def node(name, parent, kind="терминальный"):
        ex = db.query(Classificator).filter(Classificator.название == name).first()
        if ex:
            return ex.id
        r = classifier.add_node(db, name, kind, parent)
        if not r["success"]:
            raise ConfigError(r["message"])
        return r["node_id"]

    def enum(name, values, descr=None):
        e = db.query(Enumeration).filter(Enumeration.name == name).first()
        eid = e.id if e else classifier.add_enumeration(db, name, descr)["enum_id"]
        have = {v.value for v in db.query(EnumValue).filter(EnumValue.enumeration_id == eid).all()}
        for i, v in enumerate(values, 1):
            if v not in have:
                classifier.add_enum_value(db, eid, v, 100 + i if have else i)
        return eid, {v.value: v.id for v in db.query(EnumValue).filter(EnumValue.enumeration_id == eid).all()}

    # классификатор функций и типов значений
    root_f = node(ROOT_FUNCTIONS, None, "промежуточный")
    FC = {n: node(n, root_f) for n in (FN_PREDICATE, FN_LOGIC, FN_ARITH, FN_CHOICE)}
    root_t = node(ROOT_TYPES, None, "промежуточный")
    TY = {n: node(n, root_t) for n in (T_NUM, T_BOOL, T_STR, T_ENUM, T_ANY)}
    OP = {}
    for en, vals in OPERATOR_ENUMS.items():
        OP.update(enum(en, vals, "Операторы функций ограничений")[1])

    def fn(code, name, cls, op, res, args, descr=None):
        f = ConstraintFunction(обозначение=code, наименование=name, класс_id=FC[cls], оператор_id=OP[op],
                               тип_результата_id=TY[res], описание=descr)
        db.add(f)
        db.flush()
        for i, (n, t, rep) in enumerate(args, 1):
            db.add(FunctionArgument(функция_id=f.id, номер=i, имя=n, тип_id=TY[t], повторяемый=rep))
        db.flush()

    N, B, A = T_NUM, T_BOOL, T_ANY
    for code, name, op in [("GT", "Больше", ">"), ("GE", "Больше или равно", ">="), ("LT", "Меньше", "<"),
                           ("LE", "Меньше или равно", "<=")]:
        fn(code, name, FN_PREDICATE, op, B, [("a", N, False), ("b", N, False)])
    fn("EQ", "Равно", FN_PREDICATE, "=", B, [("a", A, False), ("b", A, False)])
    fn("NE", "Не равно", FN_PREDICATE, "<>", B, [("a", A, False), ("b", A, False)])
    fn("IN", "Входит в список", FN_PREDICATE, "IN", B, [("x", A, False), ("список", A, True)])
    fn("AND", "Логическое И", FN_LOGIC, "AND", B, [("условие", B, True)])
    fn("OR", "Логическое ИЛИ", FN_LOGIC, "OR", B, [("условие", B, True)])
    fn("NOT", "Логическое НЕ", FN_LOGIC, "NOT", B, [("условие", B, False)])
    fn("ADD", "Сумма", FN_ARITH, "+", N, [("слагаемое", N, True)])
    fn("SUB", "Разность", FN_ARITH, "-", N, [("a", N, False), ("b", N, False)])
    fn("MUL", "Произведение", FN_ARITH, "*", N, [("множитель", N, True)])
    fn("DIV", "Частное", FN_ARITH, "/", N, [("a", N, False), ("b", N, False)])
    fn("MIN", "Минимум", FN_ARITH, "MIN", N, [("x", N, True)])
    fn("MAX", "Максимум", FN_ARITH, "MAX", N, [("x", N, True)])
    fn("IF", "Если – то – иначе", FN_CHOICE, "IF", A, [("условие", B, False), ("если_да", A, False), ("если_нет", A, False)])
    db.commit()
    svc.add_function(db, "BETWEEN", "Значение в диапазоне", FC[FN_PREDICATE],
                     [{"имя": "x", "тип_id": TY[N]}, {"имя": "lo", "тип_id": TY[N]}, {"имя": "hi", "тип_id": TY[N]}],
                     "x >= lo AND x <= hi", "lo ≤ x ≤ hi")
    svc.add_function(db, "RATIO_IN_RANGE", "Отношение в диапазоне", FC[FN_PREDICATE],
                     [{"имя": "a", "тип_id": TY[N]}, {"имя": "b", "тип_id": TY[N]}, {"имя": "lo", "тип_id": TY[N]},
                      {"имя": "hi", "тип_id": TY[N]}],
                     "a / b >= lo AND a / b <= hi", "Проверка соотношения сторон: lo ≤ a / b ≤ hi")

    # перечисления и параметры конфигурации
    color_id, colors = enum("Цвет", ["Красный", "Синий", "Зелёный", "Белый", "Чёрный", "Жёлтый", "Серый", "Прозрачный"])
    series_id, _ = enum("Серия мини-фигурки", ["Star Wars", "Harry Potter", "City"], "Серия (тематика) мини-фигурки")
    acc_id, _ = enum("Аксессуар мини-фигурки", ["Без аксессуара", "Световой меч", "Волшебная палочка", "Бластер", "Рация"])

    def param(code, name, tip, unit=None, enum_id=None):
        p = db.query(Parameter).filter(Parameter.обозначение == code).first()
        if p:
            return p.id
        return classifier.add_parameter(db, code, name, tip, unit, enum_id)["param_id"]

    P = {"W": param("W", "Ширина в штырьках", "INTEGER", "шт."), "L": param("L", "Длина в штырьках", "INTEGER", "шт."),
         "H": param("H", "Высота в пластинах", "INTEGER", "пл."),
         "цвет": param("цвет", "Цвет изделия", "ENUM", None, color_id),
         "серия": param("серия", "Серия мини-фигурки", "ENUM", None, series_id),
         "аксессуар": param("аксессуар", "Аксессуар мини-фигурки", "ENUM", None, acc_id)}

    root_cfg = node("Детали по индивидуальному заказу", db.query(Classificator).filter(Classificator.название == "Детали").first().id,
                    "промежуточный")
    K_PLATE = node("Пластины на заказ", root_cfg)
    K_BRICK = node("Кирпичи на заказ", root_cfg)
    K_MF = node("Мини-фигурки на заказ", db.query(Classificator).filter(Classificator.название == "Мини-фигурки").first().id)

    def class_params(cls, items):
        for code, mn, mx in items:
            r = classifier.add_param_to_class(db, cls, P[code], mn, mx, None, True)
            pc = db.get(ParameterClass, r["param_class_id"]) if r.get("param_class_id") else db.query(ParameterClass) \
                .filter(ParameterClass.класс_id == cls, ParameterClass.параметр_id == P[code]).first()
            pc.флаг_конфигурации = True
        db.commit()

    # общий параметр «цвет» описан один раз у надкласса и наследуется пластинами и кирпичами (GET_CONFIG_PARAMS)
    class_params(root_cfg, [("цвет", None, None)])
    db.query(ParameterClass).filter(ParameterClass.класс_id == root_cfg).update({"порядковый_номер": 100})
    db.commit()
    class_params(K_PLATE, [("W", 1, 16), ("L", 1, 32)])
    class_params(K_BRICK, [("W", 1, 4), ("L", 1, 16), ("H", 1, 12)])
    class_params(K_MF, [("серия", None, None), ("аксессуар", None, None), ("цвет", None, None)])

    sht = db.query(UnitOfMeasure).filter(UnitOfMeasure.обозначение == "шт").first()

    def template(name, sku, cls, kind, price):
        p = Product(класс_id=cls, наименование=name, артикул=sku, тип_изделия=kind, ед_изм_id=sht.id if sht else None,
                    вид_конфигурации="ТИПОВОЕ", цена=price)
        db.add(p)
        db.commit()
        return p.id

    T_PL = template("Пластина на заказ", "PLATE-CFG", K_PLATE, "ДЕТАЛЬ", None)
    T_BR = template("Кирпич на заказ", "BRICK-CFG", K_BRICK, "ДЕТАЛЬ", None)
    T_MF = template("Мини-фигурка на заказ", "MF-CFG", K_MF, "УЗЕЛ", None)
    for pid, rules, price in [
        (T_PL, [("Ширина не больше длины", "W <= L", "Ширина W должна быть не больше длины L"),
                ("Стандартная ширина пластины", "W IN (1, 2, 4, 6, 8, 16)", "Ширина W: 1, 2, 4, 6, 8 или 16 штырьков"),
                ("Площадь не более 256 штырьков", "W * L <= 256", "Площадь W × L не должна превышать 256 штырьков"),
                ("Соотношение сторон от 1 до 8", "RATIO_IN_RANGE(L, W, 1, 8)", "Длина должна быть от 1 до 8 ширин"),
                ("Прозрачные пластины – длина до 8", "NOT (цвет = 'Прозрачный') OR L <= 8",
                 "Прозрачные пластины изготавливаются длиной не более 8 штырьков")],
         "(0.8 + 0.12 * W * L) * IF(цвет = 'Прозрачный', 1.3, 1)"),
        (T_BR, [("Высота кратна кирпичу", "H IN (3, 6, 12)", "Высота H: 3, 6 или 12 пластин (1, 2 или 4 кирпича)"),
                ("Длина от ширины до 16", "BETWEEN(L, W, 16)", "Длина L должна быть от W до 16 штырьков"),
                ("Объём не более 64 кирпичей 1x1", "W * L * H / 3 <= 64", "Объём W × L × H / 3 не должен превышать 64")],
         "1 + 0.25 * W * L * H / 3"),
        (T_MF, [("Световой меч – только Star Wars", "NOT (аксессуар = 'Световой меч') OR серия = 'Star Wars'",
                 "Световой меч доступен только в серии Star Wars"),
                ("Волшебная палочка – только Harry Potter", "аксессуар <> 'Волшебная палочка' OR серия = 'Harry Potter'",
                 "Волшебная палочка доступна только в серии Harry Potter"),
                ("Цвет корпуса серии City", "серия <> 'City' OR цвет IN ('Синий', 'Красный', 'Жёлтый', 'Белый')",
                 "Корпус фигурки City: синий, красный, жёлтый или белый")],
         "IF(аксессуар = 'Без аксессуара', 350, 420)")]:
        for n, src, msg in rules:
            svc.add_constraint(db, pid, n, src, msg)
        svc.set_price_formula(db, pid, price, None)

    # цены простых изделий: себестоимость по маршрутной технологии (ПР6) с наценкой 35 %
    db.execute(text("""UPDATE "изделие" p SET "цена" = round((c."на_единицу" * 1.35)::numeric, 2)
        FROM (SELECT x.id, (SELECT на_единицу FROM calc_cost(x.id, 1000) WHERE статья LIKE 'Итого%') AS на_единицу
              FROM "изделие" x WHERE x."вид_конфигурации" = 'ПРОСТОЕ'
                AND EXISTS (SELECT 1 FROM "изделие_операция" o WHERE o."изделие_id" = x.id AND o."вид" = 'ТЕХ')) c
        WHERE c.id = p.id AND c."на_единицу" > 0"""))
    db.commit()

    # заказчики и заказы
    def customer(name, inn, person, phone):
        s = db.query(Subject).filter(Subject.наименование == name).first()
        return s.id if s else classifier.add_subject(db, name, inn, person, phone)["subject_id"]
    C1 = customer("ООО «Детский мир»", "7729355614", "Орлова Е. В.", "+7 812 555-10-20")
    C2 = customer("ГБОУ Школа № 239 (кружок робототехники)", "7808020155", "Смирнов А. П.", "+7 812 555-33-44")
    customer("ИП Петров А. С. (магазин «Кубики»)", "781012345678", "Петров А. С.", "+7 921 555-77-88")
    pid = lambda sku: db.query(Product).filter(Product.артикул == sku).first().id  # noqa: E731
    o1 = svc.save_order(db, None, {"номер": "З-2026-001", "заказчик_id": C1, "дата_регистрации": date(2026, 10, 20),
                                   "срок_изготовления": date(2026, 12, 1), "контактное_лицо": "Орлова Е. В.",
                                   "телефон": "+7 812 555-10-20", "примечание": "Новогодняя партия"})["id"]
    svc.add_item(db, o1, pid("SET-75257"), 20)
    svc.configure_item(db, o1, T_PL, {P["W"]: 4, P["L"]: 8, P["цвет"]: colors["Красный"]}, 500)
    svc.configure_item(db, o1, T_MF, _mf(db, P, "Star Wars", "Световой меч", "Белый"), 50)
    svc.set_status(db, o1, "СОГЛАСОВАН")
    o2 = svc.save_order(db, None, {"номер": "З-2026-002", "заказчик_id": C2, "дата_регистрации": date(2026, 11, 2),
                                   "срок_изготовления": date(2026, 11, 30), "контактное_лицо": "Смирнов А. П.",
                                   "телефон": "+7 812 555-33-44"})["id"]
    svc.configure_item(db, o2, T_BR, {P["W"]: 2, P["L"]: 6, P["H"]: 3, P["цвет"]: colors["Синий"]}, 200)
    svc.add_item(db, o2, pid("SET-60266"), 3)
    print("  [ПР7] библиотека функций, 3 типовых изделия с ограничениями и 2 заказа добавлены")


def _mf(db: Session, P: Dict[str, int], series: str, acc: str, color: str) -> Dict[int, int]:
    def ev(param_code, value):
        p = db.get(Parameter, P[param_code])
        return db.query(EnumValue).filter(EnumValue.enumeration_id == p.перечисление_id, EnumValue.value == value).first().id
    return {P["серия"]: ev("серия", series), P["аксессуар"]: ev("аксессуар", acc), P["цвет"]: ev("цвет", color)}


def clear_config_tables() -> List[str]:
    return ["позиция_заказа", "заказ", "ограничение", "фактический_параметр", "вызов_функции", "аргумент_функции",
            "функция_ограничения", "константа"]
