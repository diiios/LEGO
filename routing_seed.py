# routing_seed.py
"""
Задание 6. Демонстрационные данные маршрутной технологии (поверх данных задания 5):
справочники (классы ТО, профессии, оборудование, инструмент, квалификация), ГРЦ,
инструмент и оснастка, типовые ТП (Flyweight), позиции закупки с ценами и
технологические маршруты всех изделий, у которых есть спецификация.
"""
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import BOMItem, Classificator, Enumeration, EnumValue, Product, Subject
from routing_models import InputResource, ProductOperation, TypicalProcess, WorkCenter, Tool
from routing_service import (QUALIFICATION_ENUM, ROOT_EQUIPMENT, ROOT_OPERATIONS, ROOT_PROFESSIONS, ROOT_TOOLS,
                             RoutingError, routing_service as svc)

PRICES = {  # цена закупки за основную ЕИ изделия, руб.
    "MAT-ABS": 185.0, "MAT-PC": 340.0, "MAT-SBR": 160.0, "MAT-CORD-1": 4.5,
    "PKG-BOX-75257": 48.0, "PKG-GIFT-75257": 95.0, "PKG-BOX-60266": 52.0, "PKG-BAG": 1.3,
    "DOC-MAN-75257": 22.0, "DOC-MAN-60266": 18.0, "DOC-STK-75257": 7.5, "EL-MOTOR-L": 980.0,
    "EL-HUB": 1450.0, "PKG-BOX-42110": 64.0, "PKG-BOX-42110-L": 41.0, "DOC-MAN-42110": 30.0,
    "DOC-MAN-60266-ML": 26.0, "DOC-CERT": 15.0, "PKG-STAND": 210.0,
}
DYE_PRICE = 2.4   # руб/г красителя-концентрата


def load_routing_test_data(db: Session, classifier) -> None:
    if db.query(TypicalProcess).count():
        print("  [ТМ] данные маршрутной технологии уже загружены")
        return

    # ---------------------------------------------------------------- классификаторы
    def node(name, parent, kind="терминальный", order=None):
        ex = db.query(Classificator).filter(Classificator.название == name).first()
        if ex:
            return ex.id
        r = classifier.add_node(db, name, kind, parent, sort_order=order)
        if not r["success"]:
            raise RoutingError(r["message"])
        return r["node_id"]

    root_ops = node(ROOT_OPERATIONS, None, "промежуточный")
    C = {k: node(v, root_ops, order=i) for i, (k, v) in enumerate([
        ("DRY", "Подготовка материала"), ("MOLD", "Литьё под давлением"), ("VULC", "Литьё резины (вулканизация)"),
        ("PRINT", "Тампопечать"), ("TRIM", "Механическая обработка"), ("ASM", "Сборочная операция"),
        ("KIT", "Комплектация"), ("PACK", "Упаковывание"), ("QC", "Технический контроль"),
        ("BUY", "Закупка")], 1)}
    root_prof = node(ROOT_PROFESSIONS, None, "промежуточный")
    PR = {k: node(v, root_prof, order=i) for i, (k, v) in enumerate([
        ("OPER", "Оператор термопластавтомата"), ("SETUP", "Наладчик литьевого оборудования"),
        ("PRN", "Тампопечатник"), ("ASM", "Сборщик изделий из пластмасс"), ("KIT", "Комплектовщик"),
        ("PACK", "Упаковщик"), ("QC", "Контролёр ОТК")], 1)}
    root_eq = node(ROOT_EQUIPMENT, None, "промежуточный")
    EQ = {k: node(v, root_eq, order=i) for i, (k, v) in enumerate([
        ("DRY", "Сушилки гранулята"), ("TPA", "Термопластавтоматы"), ("RUB", "Литьевые машины для резины"),
        ("PRN", "Тампопечатные машины"), ("ASM", "Сборочные столы и линии"), ("PACK", "Упаковочные линии"),
        ("QC", "Контрольные посты")], 1)}
    root_tl = node(ROOT_TOOLS, None, "промежуточный")
    TC = {k: node(v, root_tl, order=i) for i, (k, v) in enumerate([
        ("MOLD", "Пресс-формы"), ("CLICHE", "Клише и тампоны"), ("FIX", "Сборочные приспособления"),
        ("GAUGE", "Контрольно-измерительный инструмент"), ("HAND", "Ручной инструмент")], 1)}

    # квалификация — перечисление с тарифной ставкой (руб/ч)
    e = db.query(Enumeration).filter(Enumeration.name == QUALIFICATION_ENUM).first()
    if not e:
        eid = classifier.add_enumeration(db, QUALIFICATION_ENUM, "Тарифный разряд рабочего; ставка — руб/ч")["enum_id"]
        for i, (v, rate) in enumerate([("2 разряд", 260), ("3 разряд", 300), ("4 разряд", 350),
                                        ("5 разряд", 410), ("6 разряд", 480)], 1):
            classifier.add_enum_value(db, eid, v, i, {"ставка": rate})
        e = db.get(Enumeration, eid)
    Q = {v.value.split()[0]: v.id for v in db.query(EnumValue).filter(EnumValue.enumeration_id == e.id).all()}

    # подразделения (субъекты хозяйственной деятельности)
    def subject(name):
        s = db.query(Subject).filter(Subject.наименование == name).first()
        return s.id if s else classifier.add_subject(db, name)["subject_id"]
    S = {k: subject(v) for k, v in [("MOLD", "Цех литья пластмасс"), ("DEC", "Участок декорирования"),
                                     ("ASM", "Сборочный цех"), ("PACK", "Цех комплектации и упаковки"),
                                     ("QC", "Отдел технического контроля")]}

    # ---------------------------------------------------------------- ГРЦ
    G = {}
    for key, code, name, cls, subj, n, rate in [
        ("DRY", "СШ-01", "Сушилки гранулята Moretto", "DRY", "MOLD", 4, 120),
        ("TPA", "ТПА-80", "Термопластавтоматы Engel 80 т", "TPA", "MOLD", 12, 950),
        ("TPA2", "ТПА-150", "Термопластавтоматы Arburg 150 т (крупные детали)", "TPA", "MOLD", 4, 1250),
        ("RUB", "ЛМР-01", "Литьевые машины для резины Desma", "RUB", "MOLD", 2, 1100),
        ("PRN", "ТПМ-01", "Тампопечатные машины Tampoprint", "PRN", "DEC", 3, 600),
        ("ASM", "СБ-МФ", "Линия сборки мини-фигурок", "ASM", "ASM", 2, 380),
        ("ASM2", "СБ-МД", "Участок сборки модулей", "ASM", "ASM", 8, 150),
        ("KIT", "КМ-01", "Комплектовочный конвейер", "PACK", "PACK", 2, 420),
        ("PACK", "УП-01", "Упаковочная линия (термоусадка)", "PACK", "PACK", 2, 520),
        ("QC", "ОТК-01", "Пост выходного контроля", "QC", "QC", 3, 90)]:
        r = svc.save_work_center(db, None, {"код": code, "наименование": name, "класс_id": EQ[cls],
                                            "субъект_id": S[subj], "количество_ед": n, "ставка_часа": rate})
        G[key] = r["id"]

    # ---------------------------------------------------------------- инструмент и оснастка
    T = {}
    for key, code, name, kind, cls in [
        ("PF-BR2X4", "ПФ-3001", "Пресс-форма «Кирпич 2x4», 8 гнёзд", "ОСНАСТКА", "MOLD"),
        ("PF-BR2X2", "ПФ-3003", "Пресс-форма «Кирпич 2x2», 16 гнёзд", "ОСНАСТКА", "MOLD"),
        ("PF-PL1X2", "ПФ-3023", "Пресс-форма «Плита 1x2», 32 гнезда", "ОСНАСТКА", "MOLD"),
        ("PF-WH", "ПФ-4624", "Пресс-форма «Колесо 30 мм», 4 гнезда", "ОСНАСТКА", "MOLD"),
        ("PF-MF", "ПФ-9730", "Пресс-форма элементов мини-фигурок (семейная)", "ОСНАСТКА", "MOLD"),
        ("PF-TP", "ПФ-3270", "Пресс-форма деталей Technic (семейная)", "ОСНАСТКА", "MOLD"),
        ("PF-TIRE", "ПФ-4415", "Пресс-форма «Шина 81x35»", "ОСНАСТКА", "MOLD"),
        ("CL-LUKE", "КЛ-0101", "Клише «Люк Скайуокер»", "ОСНАСТКА", "CLICHE"),
        ("CL-VADER", "КЛ-0102", "Клише «Дарт Вейдер»", "ОСНАСТКА", "CLICHE"),
        ("CL-POL", "КЛ-0201", "Клише «Полицейский»", "ОСНАСТКА", "CLICHE"),
        ("TAMPON", "ТМ-20", "Тампон силиконовый 20 мм", "ИНСТРУМЕНТ", "CLICHE"),
        ("FIX-MF", "ПС-0007", "Приспособление для сборки мини-фигурок", "ОСНАСТКА", "FIX"),
        ("FIX-WH", "ПС-0012", "Оправка для монтажа шин", "ОСНАСТКА", "FIX"),
        ("GAUGE", "КИ-0005", "Калибр контроля силы сцепления (clutch power)", "ИНСТРУМЕНТ", "GAUGE"),
        ("CALIP", "КИ-0001", "Штангенциркуль цифровой 0–150 мм", "ИНСТРУМЕНТ", "GAUGE"),
        ("SCALE", "КИ-0010", "Весы контрольные (комплектность по массе)", "ИНСТРУМЕНТ", "GAUGE"),
        ("CUTTER", "РИ-0003", "Кусачки для удаления литника", "ИНСТРУМЕНТ", "HAND")]:
        T[key] = svc.save_tool(db, None, {"обозначение": code, "наименование": name, "вид": kind,
                                          "класс_id": TC[cls]})["id"]

    # ---------------------------------------------------------------- изделия
    prods: Dict[str, Product] = {p.артикул: p for p in db.query(Product).filter(Product.артикул.isnot(None)).all()}

    def pid(sku):
        return prods[sku].id if sku in prods else None

    # позиции закупки (материалы и комплектующие) с ценой
    for p in prods.values():
        if p.тип_изделия in ("МАТЕРИАЛ", "КОМПЛЕКТУЮЩЕЕ"):
            price = PRICES.get(p.артикул, DYE_PRICE if p.артикул.startswith("MAT-DYE") else 10.0)
            svc.add_operation(db, p.id, "ЗАКУПКА", {"наименование": "Закупка", "цена": price})

    # ---------------------------------------------------------------- типовые ТП (Flyweight)
    def typical(code, name, cls, descr, params, ops, res):
        tp = svc.save_typical(db, None, {"обозначение": code, "наименование": name, "класс_то_id": C[cls],
                                         "описание": descr})["id"]
        P = {}
        for pc, pn, unit, mn, mx, df in params:
            P[pc] = svc.add_typical_param(db, tp, {"обозначение": pc, "наименование": pn, "ед_изм": unit,
                                                   "мин": mn, "макс": mx, "по_умолчанию": df})["id"]
        for num, on, ocls, grc, prof, q, tpz, base, coef, prm in ops:
            svc.add_typical_operation(db, tp, {"номер": num, "наименование": on, "класс_то_id": C[ocls],
                                               "грц_id": G[grc], "профессия_id": PR[prof], "квалификация_id": Q[q],
                                               "тпз": tpz, "тшт_база": base, "тшт_коэф": coef,
                                               "параметр_id": P.get(prm)})
        for sku, base, coef, prm in res:
            if pid(sku):
                svc.add_typical_resource(db, tp, {"изделие_id": pid(sku), "норма_база": base, "норма_коэф": coef,
                                                  "параметр_id": P.get(prm)})
        return tp, P

    mold_ops = lambda grc: [  # noqa: E731
        (10, "Сушка гранулята", "DRY", "DRY", "OPER", "2", 10, 0.002, 0.0008, "m"),
        (20, "Литьё под давлением", "MOLD", grc, "OPER", "3", 45, 0.06, 0.011, "m"),
        (30, "Удаление литника, визуальный контроль", "QC", "QC", "QC", "3", 0, 0.015, 0.0, None)]
    mass = [("m", "Масса отливки", "г", 0.1, 120.0, 2.0)]
    TP_ABS, PA = typical("ТТП-01", "Литьё детали из ABS-пластика", "MOLD",
                         "Тшт литья = 0,06 + 0,011·m мин; расход ABS = 1,05·m г (5 % — литники и брак)",
                         mass, mold_ops("TPA"), [("MAT-ABS", 0.0, 0.00105, "m")])
    TP_ABS2, PA2 = typical("ТТП-02", "Литьё крупной детали из ABS (ТПА 150 т)", "MOLD",
                           "Для деталей массой свыше 5 г: Тшт = 0,08 + 0,012·m мин",
                           [("m", "Масса отливки", "г", 5.0, 120.0, 7.5)],
                           [(10, "Сушка гранулята", "DRY", "DRY", "OPER", "2", 10, 0.002, 0.0008, "m"),
                            (20, "Литьё под давлением", "MOLD", "TPA2", "OPER", "4", 60, 0.08, 0.012, "m"),
                            (30, "Удаление литника, визуальный контроль", "QC", "QC", "QC", "3", 0, 0.02, 0.0, None)],
                           [("MAT-ABS", 0.0, 0.00105, "m")])
    TP_PC, PP = typical("ТТП-03", "Литьё прозрачной детали из поликарбоната", "MOLD",
                        "Поликарбонат сушится дольше: Тшт сушки = 0,004 + 0,0015·m", mass,
                        [(10, "Сушка гранулята", "DRY", "DRY", "OPER", "2", 20, 0.004, 0.0015, "m"),
                         (20, "Литьё под давлением", "MOLD", "TPA", "OPER", "4", 50, 0.07, 0.013, "m"),
                         (30, "Удаление литника, визуальный контроль", "QC", "QC", "QC", "3", 0, 0.015, 0.0, None)],
                        [("MAT-PC", 0.0, 0.00108, "m")])
    TP_RUB, PRB = typical("ТТП-04", "Литьё резиновой детали с вулканизацией", "VULC",
                          "Тшт = 0,2 + 0,018·m мин; расход SBR = 1,08·m г",
                          [("m", "Масса отливки", "г", 1.0, 80.0, 5.0)],
                          [(10, "Литьё и вулканизация", "VULC", "RUB", "OPER", "4", 40, 0.2, 0.018, "m"),
                           (20, "Обрезка облоя, контроль", "QC", "QC", "QC", "3", 0, 0.03, 0.0, None)],
                          [("MAT-SBR", 0.0, 0.00108, "m")])
    TP_ASM, PS = typical("ТТП-10", "Ручная сборка узла", "ASM",
                         "Тшт сборки = 0,1 + 0,05·N мин, N — число устанавливаемых деталей",
                         [("N", "Число устанавливаемых деталей", "шт", 1, 500, 10)],
                         [(10, "Сборка", "ASM", "ASM2", "ASM", "2", 5, 0.1, 0.05, "N"),
                          (20, "Контроль сборки", "QC", "QC", "QC", "3", 0, 0.05, 0.004, "N")], [])

    # ---------------------------------------------------------------- маршруты
    def spec(product_id):
        return db.execute(text("SELECT * FROM bom_effective(:p)"), {"p": product_id}).mappings().all()

    def op(product_id, num, name, cls, grc=None, prof=None, q=None, tpz=0.0, tsht=0.0):
        return svc.add_operation(db, product_id, "ТЕХ", {
            "номер": num, "наименование": name, "класс_то_id": C[cls], "грц_id": G.get(grc),
            "профессия_id": PR.get(prof), "квалификация_id": Q.get(q), "тпз": tpz, "тшт": tsht})["id"]

    def tool(op_id, *keys):
        for k in keys:
            svc.add_tool(db, op_id, T[k], 1)

    def move_inputs(product_id, to_op, pred):
        """перенос входных ресурсов на операцию, где компонент реально потребляется"""
        for r in db.query(InputResource).join(ProductOperation, ProductOperation.id == InputResource.выход_id) \
                .filter(ProductOperation.изделие_id == product_id).all():
            if pred(r.input_op.product):
                r.выход_id = to_op
        db.commit()

    # Детали: материал по типовому ТП (литьё), краситель — по спецификации
    mold_of = {"BR-2X4": "PF-BR2X4", "BR-2X2": "PF-BR2X2", "PL-1X2": "PF-PL1X2", "WH-30": "PF-WH",
               "MFE": "PF-MF", "TP": "PF-TP"}
    details = [p for p in prods.values() if p.тип_изделия == "ДЕТАЛЬ" and spec(p.id)]
    for p in sorted(details, key=lambda x: x.артикул):
        rows = spec(p.id)
        mat = {db.get(Product, r["компонент_id"]).артикул: r for r in rows}
        if "MAT-SBR" in mat:
            tp, params, grams = TP_RUB, PRB, mat["MAT-SBR"]
        elif "MAT-PC" in mat:
            tp, params, grams = TP_PC, PP, mat["MAT-PC"]
        else:
            grams = mat.get("MAT-ABS")
            if not grams:
                continue
            tp, params = (TP_ABS2, PA2) if grams["расход"] / grams["для_количества"] * 1000 > 5 else (TP_ABS, PA)
        m = round(grams["расход"] / grams["для_количества"] * 1000, 3)   # кг на 1000 шт = г на 1 шт
        o10 = op(p.id, 10, "Деталь отлита", "MOLD")
        svc.apply_typical(db, o10, tp, {params["m"]: m})
        svc.build_from_bom(db, p.id, o10)          # краситель-концентрат — из спецификации задания 5
        fam = "TIRE" if p.артикул.startswith("TP-TIRE") else \
            next((v for k, v in mold_of.items() if p.артикул.startswith(k)), None)
        if fam == "TIRE":
            tool(o10, "PF-TIRE")
        elif fam:
            tool(o10, fam, "CUTTER")
        last = o10
        if p.артикул.startswith("MFE-TORSO"):
            last = op(p.id, 20, "Нанесена печать", "PRINT", "PRN", "PRN", "3", 25, 0.18)
            tool(last, {"LUKE": "CL-LUKE", "VADER": "CL-VADER", "POLICE": "CL-POL"}[p.артикул.rsplit("-", 1)[1]],
                 "TAMPON")
        if p.артикул.startswith("TP-GEAR"):
            last = op(p.id, 20, "Зубчатый венец зачищен", "TRIM", "QC", "QC", "4", 5, 0.08)
            tool(last, "CALIP")
        if p.артикул.startswith("BR-"):
            tool(o10, "GAUGE")

    # Узлы и комплексы — в порядке «снизу вверх» (сначала компоненты)
    done = {p.id for p in details} | {p.id for p in prods.values() if p.тип_изделия in ("МАТЕРИАЛ", "КОМПЛЕКТУЮЩЕЕ")}
    rest = [p for p in prods.values() if p.тип_изделия in ("УЗЕЛ", "КОМПЛЕКС") and spec(p.id)]
    packaging = {"PKG-BOX-75257", "PKG-GIFT-75257", "PKG-BOX-60266", "PKG-BOX-42110", "PKG-BOX-42110-L", "PKG-BAG",
                 "PKG-STAND"}
    while rest:
        ready = [p for p in rest if all(r["компонент_id"] in done for r in spec(p.id))]
        if not ready:
            print("  [ТМ] не удалось упорядочить:", [p.артикул for p in rest])
            break
        for p in sorted(ready, key=lambda x: x.артикул):
            rows = spec(p.id)
            parts = int(sum(r["расход"] / r["для_количества"] for r in rows
                            if db.get(Product, r["компонент_id"]).ед_изм_id == p.ед_изм_id
                            and db.get(Product, r["компонент_id"]).артикул not in packaging))
            if p.артикул == "TP-WHEEL-81":
                o10 = op(p.id, 10, "Шина смонтирована на диск", "ASM", "ASM2", "ASM", "2", 5, 0.25)
                tool(o10, "FIX-WH")
                svc.build_from_bom(db, p.id, o10)
            elif p.тип_изделия == "УЗЕЛ":
                o10 = op(p.id, 10, "Узел собран", "ASM")
                svc.apply_typical(db, o10, TP_ASM, {PS["N"]: max(parts, 1)})
                svc.build_from_bom(db, p.id, o10)
                if p.артикул.startswith("MF-"):
                    tool(o10, "FIX-MF")
                else:
                    o20 = op(p.id, 20, "Модуль упакован в пакет", "PACK", "KIT", "PACK", "2", 10, 0.35)
                    move_inputs(p.id, o20, lambda c: c.артикул == "PKG-BAG")
            else:   # КОМПЛЕКС: комплектация -> упаковка -> приёмка ОТК
                o10 = op(p.id, 10, "Набор скомплектован", "KIT", "KIT", "KIT", "3", 30, 1.6)
                svc.build_from_bom(db, p.id, o10)
                o20 = op(p.id, 20, "Набор упакован в коробку", "PACK", "PACK", "PACK", "3", 20, 0.9)
                move_inputs(p.id, o20, lambda c: c.артикул in packaging)
                o30 = op(p.id, 30, "Набор принят ОТК", "QC", "QC", "QC", "4", 0, 0.4)
                tool(o30, "SCALE")
            done.add(p.id)
            rest.remove(p)
    db.commit()


def clear_routing_tables() -> List[str]:
    """Таблицы задания 6 в порядке очистки (для LegoClassifier.clear_database)"""
    return ["значение_параметра_тпп", "инструмент_операции", "входной_ресурс", "изделие_операция",
            "типовой_ресурс", "типовая_операция", "параметр_тпп", "типовой_тп", "инструмент", "грц"]
