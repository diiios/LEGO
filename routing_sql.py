# routing_sql.py
"""
Задание 6. Маршрутная технология — хранимые функции PostgreSQL (процедуры поддержки бизнес-логики).

  tm_final_op(pIdProd)          — итоговая Изделие-Операция изделия (последняя по номеру)
  tm_labor(pIdTO)               — нормы времени операции; для позиции с типовым ТП — развёртывание
                                  типовых операций с учётом значений параметров (Flyweight)
  tm_inputs(pIdTO)              — входные ресурсы операции: явные позиции входного ресурса +
                                  ресурсы типового ТП, рассчитанные по значениям параметров
  FIND_TM(pIdEl)                — весь технологический маршрут изделия на всю глубину вложенности
  MR_Q(pIdTO, pQ)               — нормы расхода материальных ресурсов для конкретной операции
  SUM_MR(pIdEl, pQ)             — сводные нормы материальных ресурсов на всё изделие (с ценой и стоимостью)
  TR_TO(pIdEl, pQ)              — сводные нормы трудовых ресурсов (по профессиям и квалификации)
  GRC_LOAD(pIdEl, pQ)           — загрузка оборудования (машино-часы по ГРЦ)
  CALC_COST(pIdEl, pQ)          — калькуляция себестоимости: материалы + труд + оборудование
"""

MIGRATION_SQL = """
CREATE INDEX IF NOT EXISTS ix_изделие_операция_изделие ON "изделие_операция"("изделие_id");
CREATE INDEX IF NOT EXISTS ix_входной_ресурс_выход ON "входной_ресурс"("выход_id");
CREATE INDEX IF NOT EXISTS ix_входной_ресурс_вход ON "входной_ресурс"("вход_id");
CREATE INDEX IF NOT EXISTS ix_значение_параметра_тпп_оп ON "значение_параметра_тпп"("операция_id")
"""

FUNCTIONS_SQL = r"""
CREATE OR REPLACE FUNCTION tm_final_op(pIdProd integer)
RETURNS integer LANGUAGE sql STABLE AS $$
    SELECT o.id FROM "изделие_операция" o
    WHERE o."изделие_id" = pIdProd
    ORDER BY o."номер" DESC LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION tm_labor(pIdTO integer)
RETURNS TABLE(операция_id integer, типовая_операция_id integer, номер integer, наименование varchar,
              класс_то_id integer, грц_id integer, профессия_id integer, квалификация_id integer,
              тпз double precision, тшт double precision)
LANGUAGE sql STABLE AS $$
    -- обычная позиция тех-маршрута
    SELECT o.id, NULL::integer, o."номер", o."наименование", o."класс_то_id", o."грц_id",
           o."профессия_id", o."квалификация_id", o."тпз", o."тшт"
    FROM "изделие_операция" o
    WHERE o.id = pIdTO AND o."вид" = 'ТЕХ' AND o."типовой_тп_id" IS NULL
    UNION ALL
    -- позиция с типовым ТП: внутреннее состояние (типовые операции) + внешнее (значения параметров)
    SELECT o.id, t.id, t."номер", t."наименование",
           COALESCE(t."класс_то_id", o."класс_то_id"), COALESCE(t."грц_id", o."грц_id"),
           COALESCE(t."профессия_id", o."профессия_id"), COALESCE(t."квалификация_id", o."квалификация_id"),
           t."тпз",
           t."тшт_база" + t."тшт_коэф" * COALESCE(v."значение", p."по_умолчанию", 0)
    FROM "изделие_операция" o
    JOIN "типовая_операция" t ON t."тп_id" = o."типовой_тп_id"
    LEFT JOIN "параметр_тпп" p ON p.id = t."параметр_id"
    LEFT JOIN "значение_параметра_тпп" v ON v."операция_id" = o.id AND v."параметр_id" = t."параметр_id"
    WHERE o.id = pIdTO AND o."вид" = 'ТЕХ';
$$;

CREATE OR REPLACE FUNCTION tm_inputs(pIdTO integer)
RETURNS TABLE(вход_id integer, изделие_id integer, норма double precision, для_количества double precision,
              ед_изм_id integer, источник varchar)
LANGUAGE sql STABLE AS $$
    SELECT r."вход_id", i."изделие_id", r."норма", r."для_количества", r."ед_изм_id", r."источник"
    FROM "входной_ресурс" r JOIN "изделие_операция" i ON i.id = r."вход_id"
    WHERE r."выход_id" = pIdTO
    UNION ALL
    SELECT tm_final_op(tr."изделие_id"), tr."изделие_id",
           tr."норма_база" + tr."норма_коэф" * COALESCE(v."значение", p."по_умолчанию", 0),
           1.0::double precision, tr."ед_изм_id", 'ТИПОВОЙ_ТП'::varchar
    FROM "изделие_операция" o
    JOIN "типовой_ресурс" tr ON tr."тп_id" = o."типовой_тп_id"
    LEFT JOIN "параметр_тпп" p ON p.id = tr."параметр_id"
    LEFT JOIN "значение_параметра_тпп" v ON v."операция_id" = o.id AND v."параметр_id" = tr."параметр_id"
    WHERE o.id = pIdTO
      AND tr."норма_база" + tr."норма_коэф" * COALESCE(v."значение", p."по_умолчанию", 0) > 0;
$$;

-- FIND_TM: технологический маршрут изделия на всю глубину вложенности.
-- Потребность d = (изделие, до какой операции, количество на 1 изделие верхнего уровня).
-- Для каждой операции изделия (номер <= до_номера) входные ресурсы порождают потребность
-- в изделии-компоненте до операции, после которой он поступает.
CREATE OR REPLACE FUNCTION find_tm(pIdEl integer)
RETURNS TABLE(уровень integer, изделие_id integer, операция_id integer, номер integer, вид varchar,
              наименование varchar, типовой_тп_id integer, количество double precision,
              родитель_операция_id integer, путь integer[])
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE d AS (
        SELECT 1 AS уровень, pIdEl AS изделие_id,
               (SELECT max(x."номер") FROM "изделие_операция" x WHERE x."изделие_id" = pIdEl) AS до_номера,
               1.0::double precision AS количество, NULL::integer AS родитель_операция_id,
               ARRAY[pIdEl] AS путь
        UNION ALL
        SELECT d.уровень + 1, io."изделие_id", io."номер",
               d.количество * i.норма / i.для_количества, o.id, d.путь || io."изделие_id"
        FROM d
        JOIN "изделие_операция" o ON o."изделие_id" = d.изделие_id AND o."номер" <= d.до_номера
        CROSS JOIN LATERAL tm_inputs(o.id) i
        JOIN "изделие_операция" io ON io.id = i.вход_id
        WHERE d.уровень < 30 AND NOT (io."изделие_id" = ANY(d.путь))
    )
    SELECT d.уровень, o."изделие_id", o.id, o."номер", o."вид", o."наименование", o."типовой_тп_id",
           d.количество, d.родитель_операция_id, d.путь
    FROM d JOIN "изделие_операция" o ON o."изделие_id" = d.изделие_id AND o."номер" <= d.до_номера;
$$;

-- MR_Q: нормы расхода материальных ресурсов для конкретной операции на pQ единиц её результата
CREATE OR REPLACE FUNCTION mr_q(pIdTO integer, pQ double precision)
RETURNS TABLE(изделие_id integer, вход_id integer, вид varchar, норма double precision,
              для_количества double precision, количество double precision, ед_изм_id integer, источник varchar)
LANGUAGE sql STABLE AS $$
    SELECT i.изделие_id, i.вход_id, io."вид", i.норма, i.для_количества,
           i.норма / i.для_количества * pQ, COALESCE(i.ед_изм_id, p."ед_изм_id"), i.источник
    FROM tm_inputs(pIdTO) i
    LEFT JOIN "изделие_операция" io ON io.id = i.вход_id
    LEFT JOIN "изделие" p ON p.id = i.изделие_id;
$$;

-- SUM_MR: сводные нормы материальных ресурсов (позиции закупки) на pQ изделий
CREATE OR REPLACE FUNCTION sum_mr(pIdEl integer, pQ double precision)
RETURNS TABLE(изделие_id integer, ед_изм_id integer, норма_на_единицу double precision,
              количество double precision, цена double precision, стоимость double precision,
              вхождений bigint)
LANGUAGE sql STABLE AS $$
    SELECT f.изделие_id, COALESCE(max(o."ед_изм_id"), max(p."ед_изм_id")),
           sum(f.количество), sum(f.количество) * pQ,
           COALESCE(max(o."цена"), 0), sum(f.количество) * pQ * COALESCE(max(o."цена"), 0),
           count(*)
    FROM find_tm(pIdEl) f
    JOIN "изделие_операция" o ON o.id = f.операция_id
    JOIN "изделие" p ON p.id = f.изделие_id
    WHERE f.вид = 'ЗАКУПКА'
    GROUP BY f.изделие_id;
$$;

-- Операции маршрута с суммарным количеством (одна операция может встречаться в нескольких ветвях)
CREATE OR REPLACE FUNCTION tm_ops_q(pIdEl integer)
RETURNS TABLE(операция_id integer, количество double precision)
LANGUAGE sql STABLE AS $$
    SELECT f.операция_id, sum(f.количество) FROM find_tm(pIdEl) f WHERE f.вид = 'ТЕХ' GROUP BY f.операция_id;
$$;

-- TR_TO: сводные нормы трудовых ресурсов на pQ изделий (по профессиям и квалификации).
-- Трудоёмкость, ч = (Тпз + Тшт × количество × pQ) / 60; стоимость = часы × тарифная ставка разряда.
CREATE OR REPLACE FUNCTION tr_to(pIdEl integer, pQ double precision)
RETURNS TABLE(профессия_id integer, квалификация_id integer, операций bigint,
              трудоемкость_ч double precision, ставка double precision, стоимость double precision)
LANGUAGE sql STABLE AS $$
    SELECT l.профессия_id, l.квалификация_id, count(*),
           sum((l.тпз + l.тшт * q.количество * pQ) / 60.0),
           COALESCE(max((ev.extra_data ->> 'ставка')::double precision), 0),
           sum((l.тпз + l.тшт * q.количество * pQ) / 60.0)
             * COALESCE(max((ev.extra_data ->> 'ставка')::double precision), 0)
    FROM tm_ops_q(pIdEl) q
    CROSS JOIN LATERAL tm_labor(q.операция_id) l
    LEFT JOIN "значение_перечисления" ev ON ev.id = l.квалификация_id
    GROUP BY l.профессия_id, l.квалификация_id;
$$;

-- GRC_LOAD: загрузка оборудования (машино-часы) по ГРЦ на pQ изделий
CREATE OR REPLACE FUNCTION grc_load(pIdEl integer, pQ double precision)
RETURNS TABLE(грц_id integer, операций bigint, машино_часы double precision,
              ставка double precision, стоимость double precision)
LANGUAGE sql STABLE AS $$
    SELECT l.грц_id, count(*), sum((l.тпз + l.тшт * q.количество * pQ) / 60.0),
           COALESCE(max(g."ставка_часа"), 0),
           sum((l.тпз + l.тшт * q.количество * pQ) / 60.0) * COALESCE(max(g."ставка_часа"), 0)
    FROM tm_ops_q(pIdEl) q
    CROSS JOIN LATERAL tm_labor(q.операция_id) l
    LEFT JOIN "грц" g ON g.id = l.грц_id
    WHERE l.грц_id IS NOT NULL
    GROUP BY l.грц_id;
$$;

-- CALC_COST: калькуляция себестоимости pQ изделий по статьям затрат
CREATE OR REPLACE FUNCTION calc_cost(pIdEl integer, pQ double precision)
RETURNS TABLE(статья varchar, сумма double precision, на_единицу double precision)
LANGUAGE sql STABLE AS $$
    WITH m AS (SELECT COALESCE(sum(стоимость), 0) AS s FROM sum_mr(pIdEl, pQ)),
         t AS (SELECT COALESCE(sum(стоимость), 0) AS s FROM tr_to(pIdEl, pQ)),
         g AS (SELECT COALESCE(sum(стоимость), 0) AS s FROM grc_load(pIdEl, pQ))
    SELECT 'Материалы и покупные изделия'::varchar, m.s, m.s / pQ FROM m
    UNION ALL SELECT 'Оплата труда'::varchar, t.s, t.s / pQ FROM t
    UNION ALL SELECT 'Работа оборудования'::varchar, g.s, g.s / pQ FROM g
    UNION ALL SELECT 'Итого себестоимость'::varchar, m.s + t.s + g.s, (m.s + t.s + g.s) / pQ FROM m, t, g;
$$;
"""
