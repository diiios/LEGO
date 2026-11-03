# config_sql.py
"""
Задание 7 (усложнённый уровень). Хранимые функции PostgreSQL — процедуры поддержки бизнес-логики.

  GET_CONFIG_PARAMS(pIdProd)              — параметры конфигурации типового изделия (FLAG_CONF), с наследованием
  EVAL_FUNCTION(pIdCall, pVals, pArgs)    — рекурсивное вычисление вызова функции (паттерн «Интерпретатор»)
  CHECK_CONSTRAINTS(pIdBaseProd, pVals)   — проверка диапазонов параметров и всех ограничений шаблона
  VARIANT_PRICE(pIdBaseProd, pVals)       — цена варианта по формуле цены шаблона
  CREATE_VARIANT(pIdBaseProd, pVals)      — проверить ограничения и создать (или найти) вариант исполнения
  ADD_TO_ORDER(pIdOrder, pIdProd, pQ)     — добавить изделие или вариант исполнения в заказ
  ORDER_TOTAL(pIdOrder)                   — сумма заказа

pVals — jsonb {"<id параметра>": значение}; для параметров-перечислений значение — id значения перечисления.
"""

MIGRATION_SQL = """
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "вид_конфигурации" VARCHAR(10) NOT NULL DEFAULT 'ПРОСТОЕ';
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "шаблон_id" INTEGER REFERENCES "изделие"(id) ON DELETE RESTRICT;
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "цена" DOUBLE PRECISION;
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "формула_цены_id" INTEGER REFERENCES "вызов_функции"(id) ON DELETE SET NULL;
ALTER TABLE "изделие" DROP CONSTRAINT IF EXISTS ck_изделие_вид_конфигурации;
ALTER TABLE "изделие" ADD CONSTRAINT ck_изделие_вид_конфигурации
    CHECK ("вид_конфигурации" IN ('ПРОСТОЕ', 'ТИПОВОЕ', 'ВАРИАНТ')
           AND (("вид_конфигурации" = 'ВАРИАНТ') = ("шаблон_id" IS NOT NULL)));
ALTER TABLE "параметр_класса" ADD COLUMN IF NOT EXISTS "флаг_конфигурации" BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS ix_изделие_шаблон ON "изделие"("шаблон_id");
CREATE INDEX IF NOT EXISTS ix_фактический_параметр_вызов ON "фактический_параметр"("вызов_id");
CREATE INDEX IF NOT EXISTS ix_ограничение_изделие ON "ограничение"("изделие_id");
CREATE INDEX IF NOT EXISTS ix_позиция_заказа_заказ ON "позиция_заказа"("заказ_id")
"""

FUNCTIONS_SQL = r"""
CREATE OR REPLACE FUNCTION get_config_params(pIdProd integer)
RETURNS TABLE(параметр_класса_id integer, параметр_id integer, обозначение varchar, полное_имя varchar,
              тип_параметра varchar, единица_измерения varchar, перечисление_id integer,
              мин_значение double precision, макс_значение double precision, значение_по_умолчанию text,
              обязательный boolean, порядок integer)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE anc(id, depth) AS (
        SELECT p."класс_id", 0 FROM "изделие" p WHERE p.id = pIdProd
        UNION ALL
        SELECT k."родительский_id", anc.depth + 1 FROM anc JOIN "классификатор" k ON k.id = anc.id
        WHERE k."родительский_id" IS NOT NULL AND anc.depth < 30)
    SELECT DISTINCT ON (par.id) pc.id, par.id, par."обозначение", par."полное_имя", par."тип_параметра",
           par."единица_измерения", par."перечисление_id", pc."мин_значение", pc."макс_значение",
           pc."значение_по_умолчанию", COALESCE(pc."обязательный", 0) = 1, COALESCE(pc."порядковый_номер", 0)
    FROM anc JOIN "параметр_класса" pc ON pc."класс_id" = anc.id
    JOIN "параметр" par ON par.id = pc."параметр_id"
    WHERE pc."флаг_конфигурации"
    ORDER BY par.id, anc.depth;
$$;

CREATE OR REPLACE FUNCTION eval_function(pIdCall integer, pVals jsonb, pArgs jsonb DEFAULT '[]'::jsonb,
                                         pDepth integer DEFAULT 0)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE
    f record; r record; a jsonb := '[]'::jsonb; v jsonb; op text; n integer; i integer;
    num double precision; ok boolean;
BEGIN
    IF pDepth > 40 THEN
        RAISE EXCEPTION 'Слишком глубокая вложенность вызовов функций';
    END IF;
    SELECT fn.id, fn."обозначение", fn."тело_вызов_id", ev.value AS op INTO f
    FROM "вызов_функции" c JOIN "функция_ограничения" fn ON fn.id = c."функция_id"
    LEFT JOIN "значение_перечисления" ev ON ev.id = fn."оператор_id"
    WHERE c.id = pIdCall;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Вызов функции % не найден', pIdCall;
    END IF;
    -- фактические параметры: терминальные выражения и вложенные вызовы
    FOR r IN SELECT fp.*, k."значение_число" AS kn, k."значение_строка" AS ks, par."обозначение" AS pname,
                    af."номер" AS argno
             FROM "фактический_параметр" fp
             LEFT JOIN "константа" k ON k.id = fp."константа_id"
             LEFT JOIN "параметр" par ON par.id = fp."параметр_id"
             LEFT JOIN "аргумент_функции" af ON af.id = fp."аргумент_id"
             WHERE fp."вызов_id" = pIdCall ORDER BY fp."номер" LOOP
        IF r."параметр_id" IS NOT NULL THEN
            v := pVals -> r."параметр_id"::text;
            IF v IS NULL OR v = 'null'::jsonb THEN
                RAISE EXCEPTION 'Не задано значение параметра %', r.pname;
            END IF;
        ELSIF r."константа_id" IS NOT NULL THEN
            v := COALESCE(to_jsonb(r.kn), to_jsonb(r.ks));
        ELSIF r."значение_перечисления_id" IS NOT NULL THEN
            v := to_jsonb(r."значение_перечисления_id");
        ELSIF r."вложенный_вызов_id" IS NOT NULL THEN
            v := eval_function(r."вложенный_вызов_id", pVals, pArgs, pDepth + 1);
        ELSE
            v := pArgs -> (r.argno - 1);
        END IF;
        a := a || jsonb_build_array(v);
    END LOOP;
    -- составная функция: тело вычисляется с фактическими параметрами вместо формальных
    IF f."тело_вызов_id" IS NOT NULL THEN
        RETURN eval_function(f."тело_вызов_id", pVals, a, pDepth + 1);
    END IF;
    op := f.op;
    n := jsonb_array_length(a);
    IF op IN ('+', '*', 'MIN', 'MAX') THEN
        num := (a ->> 0)::double precision;
        FOR i IN 1 .. n - 1 LOOP
            num := CASE op WHEN '+' THEN num + (a ->> i)::double precision
                           WHEN '*' THEN num * (a ->> i)::double precision
                           WHEN 'MIN' THEN least(num, (a ->> i)::double precision)
                           ELSE greatest(num, (a ->> i)::double precision) END;
        END LOOP;
        RETURN to_jsonb(num);
    ELSIF op = '-' THEN
        RETURN to_jsonb((a ->> 0)::double precision - (a ->> 1)::double precision);
    ELSIF op = '/' THEN
        IF (a ->> 1)::double precision = 0 THEN
            RAISE EXCEPTION 'Деление на ноль в функции %', f."обозначение";
        END IF;
        RETURN to_jsonb((a ->> 0)::double precision / (a ->> 1)::double precision);
    ELSIF op IN ('>', '>=', '<', '<=') THEN
        RETURN to_jsonb(CASE op WHEN '>' THEN (a ->> 0)::double precision > (a ->> 1)::double precision
                                WHEN '>=' THEN (a ->> 0)::double precision >= (a ->> 1)::double precision
                                WHEN '<' THEN (a ->> 0)::double precision < (a ->> 1)::double precision
                                ELSE (a ->> 0)::double precision <= (a ->> 1)::double precision END);
    ELSIF op = '=' THEN
        RETURN to_jsonb(a -> 0 = a -> 1);
    ELSIF op = '<>' THEN
        RETURN to_jsonb(a -> 0 <> a -> 1);
    ELSIF op = 'IN' THEN
        ok := false;
        FOR i IN 1 .. n - 1 LOOP
            IF a -> 0 = a -> i THEN ok := true; END IF;
        END LOOP;
        RETURN to_jsonb(ok);
    ELSIF op IN ('AND', 'OR') THEN
        ok := (op = 'AND');
        FOR i IN 0 .. n - 1 LOOP
            IF op = 'AND' THEN ok := ok AND (a ->> i)::boolean; ELSE ok := ok OR (a ->> i)::boolean; END IF;
        END LOOP;
        RETURN to_jsonb(ok);
    ELSIF op = 'NOT' THEN
        RETURN to_jsonb(NOT (a ->> 0)::boolean);
    ELSIF op = 'IF' THEN
        RETURN CASE WHEN (a ->> 0)::boolean THEN a -> 1 ELSE a -> 2 END;
    END IF;
    RAISE EXCEPTION 'Неизвестный оператор % функции %', op, f."обозначение";
END;
$$;

CREATE OR REPLACE FUNCTION check_constraints(pIdBaseProd integer, pVals jsonb)
RETURNS TABLE(вид varchar, объект_id integer, наименование varchar, результат boolean, сообщение text)
LANGUAGE plpgsql STABLE AS $$
DECLARE p record; c record; v jsonb; res jsonb;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM "изделие" WHERE id = pIdBaseProd AND "вид_конфигурации" = 'ТИПОВОЕ') THEN
        RAISE EXCEPTION 'Изделие % не является типовым изделием с конфигуратором', pIdBaseProd;
    END IF;
    -- 1) параметры конфигурации: заданность, тип, диапазон Min/Max (базовый уровень)
    FOR p IN SELECT * FROM get_config_params(pIdBaseProd) ORDER BY порядок, параметр_id LOOP
        v := pVals -> p.параметр_id::text;
        вид := 'ПАРАМЕТР'; объект_id := p.параметр_id;
        наименование := p.полное_имя || ' (' || p.обозначение || ')';
        результат := true; сообщение := NULL;
        IF v IS NULL OR v = 'null'::jsonb THEN
            результат := false; сообщение := 'значение не задано';
        ELSIF p.тип_параметра = 'ENUM' THEN
            IF jsonb_typeof(v) <> 'number' OR NOT EXISTS (
                SELECT 1 FROM "значение_перечисления" e
                WHERE e.id = (v #>> '{}')::integer AND e.enumeration_id = p.перечисление_id) THEN
                результат := false; сообщение := 'значение не из перечисления';
            END IF;
        ELSIF jsonb_typeof(v) <> 'number' THEN
            результат := false; сообщение := 'требуется число';
        ELSIF p.тип_параметра = 'INTEGER' AND (v #>> '{}')::double precision <> trunc((v #>> '{}')::double precision) THEN
            результат := false; сообщение := 'требуется целое число';
        ELSIF p.мин_значение IS NOT NULL AND (v #>> '{}')::double precision < p.мин_значение THEN
            результат := false; сообщение := 'меньше минимального ' || p.мин_значение;
        ELSIF p.макс_значение IS NOT NULL AND (v #>> '{}')::double precision > p.макс_значение THEN
            результат := false; сообщение := 'больше максимального ' || p.макс_значение;
        END IF;
        RETURN NEXT;
    END LOOP;
    -- 2) сложные ограничения: вычисление корневого вызова логической функции
    FOR c IN SELECT * FROM "ограничение" o WHERE o."изделие_id" = pIdBaseProd AND o."активно"
             ORDER BY o."порядок", o.id LOOP
        вид := 'ОГРАНИЧЕНИЕ'; объект_id := c.id; наименование := c."наименование"; сообщение := NULL;
        BEGIN
            res := eval_function(c."вызов_id", pVals);
            результат := COALESCE((res #>> '{}')::boolean, false);
            IF NOT результат THEN
                сообщение := COALESCE(c."сообщение", 'ограничение не выполнено');
            END IF;
        EXCEPTION WHEN OTHERS THEN
            результат := false; сообщение := SQLERRM;
        END;
        RETURN NEXT;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION variant_price(pIdBaseProd integer, pVals jsonb)
RETURNS double precision LANGUAGE plpgsql STABLE AS $$
DECLARE t record;
BEGIN
    SELECT * INTO t FROM "изделие" WHERE id = pIdBaseProd;
    IF t."формула_цены_id" IS NULL THEN
        RETURN COALESCE(t."цена", 0);
    END IF;
    RETURN round((eval_function(t."формула_цены_id", pVals) #>> '{}')::numeric, 2)::double precision;
END;
$$;

CREATE OR REPLACE FUNCTION variant_value_text(pTip varchar, pVal jsonb)
RETURNS text LANGUAGE sql STABLE AS $$
    SELECT CASE WHEN pTip = 'ENUM' THEN (SELECT e.value FROM "значение_перечисления" e WHERE e.id = (pVal #>> '{}')::integer)
                ELSE trim(trailing '.' FROM trim(trailing '0' FROM to_char((pVal #>> '{}')::numeric, 'FM999999990.######')))
           END;
$$;

CREATE OR REPLACE FUNCTION create_variant(pIdBaseProd integer, pVals jsonb)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    t record; p record; errors text; key text := ''; label text := ''; vid integer; v jsonb;
BEGIN
    SELECT string_agg(наименование || ': ' || сообщение, '; ') INTO errors
    FROM check_constraints(pIdBaseProd, pVals) WHERE NOT результат;
    IF errors IS NOT NULL THEN
        RAISE EXCEPTION 'Вариант исполнения недопустим — %', errors;
    END IF;
    SELECT * INTO t FROM "изделие" WHERE id = pIdBaseProd;
    FOR p IN SELECT * FROM get_config_params(pIdBaseProd) ORDER BY порядок, параметр_id LOOP
        v := pVals -> p.параметр_id::text;
        key := key || '/' || variant_value_text(p.тип_параметра, v);
        label := label || CASE WHEN label = '' THEN '' ELSE '; ' END
                 || p.обозначение || '=' || variant_value_text(p.тип_параметра, v);
    END LOOP;
    key := COALESCE(t."артикул", 'T' || t.id) || key;
    -- такой вариант уже создавался (другим заказом) — повторно не создаём
    SELECT id INTO vid FROM "изделие" WHERE "артикул" = key AND "шаблон_id" = pIdBaseProd;
    IF vid IS NOT NULL THEN
        RETURN vid;
    END IF;
    INSERT INTO "изделие"("класс_id", "наименование", "артикул", "тип_изделия", "ед_изм_id",
                          "вид_конфигурации", "шаблон_id", "цена", created_at)
    VALUES (t."класс_id", t."наименование" || ' (' || label || ')', key, t."тип_изделия", t."ед_изм_id",
            'ВАРИАНТ', pIdBaseProd, variant_price(pIdBaseProd, pVals), now())
    RETURNING id INTO vid;
    INSERT INTO "значение_параметра"("изделие_id", "параметр_класса_id", "значение_число", "значение_перечисление_id")
    SELECT vid, g.параметр_класса_id,
           CASE WHEN g.тип_параметра = 'ENUM' THEN NULL ELSE (pVals ->> g.параметр_id::text)::double precision END,
           CASE WHEN g.тип_параметра = 'ENUM' THEN (pVals ->> g.параметр_id::text)::integer END
    FROM get_config_params(pIdBaseProd) g;
    RETURN vid;
END;
$$;

CREATE OR REPLACE FUNCTION add_to_order(pIdOrder integer, pIdProd integer, pQ double precision)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE o record; p record; pos integer;
BEGIN
    SELECT * INTO o FROM "заказ" WHERE id = pIdOrder;
    IF NOT FOUND THEN RAISE EXCEPTION 'Заказ % не найден', pIdOrder; END IF;
    IF o."статус" <> 'ЧЕРНОВИК' THEN
        RAISE EXCEPTION 'Заказ % согласован — состав изменять нельзя', o."номер";
    END IF;
    SELECT * INTO p FROM "изделие" WHERE id = pIdProd;
    IF NOT FOUND THEN RAISE EXCEPTION 'Изделие % не найдено', pIdProd; END IF;
    IF p."вид_конфигурации" = 'ТИПОВОЕ' THEN
        RAISE EXCEPTION 'Типовое изделие «%» нельзя добавить в заказ напрямую — задайте вариант исполнения', p."наименование";
    END IF;
    IF pQ IS NULL OR pQ <= 0 THEN RAISE EXCEPTION 'Количество должно быть больше нуля'; END IF;
    -- то же изделие уже есть в заказе — увеличиваем количество
    SELECT id INTO pos FROM "позиция_заказа" WHERE "заказ_id" = pIdOrder AND "изделие_id" = pIdProd;
    IF pos IS NOT NULL THEN
        UPDATE "позиция_заказа" SET "количество" = "количество" + pQ WHERE id = pos;
        RETURN pos;
    END IF;
    INSERT INTO "позиция_заказа"("заказ_id", "номер", "изделие_id", "количество", "цена")
    VALUES (pIdOrder, COALESCE((SELECT max("номер") FROM "позиция_заказа" WHERE "заказ_id" = pIdOrder), 0) + 1,
            pIdProd, pQ, COALESCE(p."цена", 0))
    RETURNING id INTO pos;
    RETURN pos;
END;
$$;

CREATE OR REPLACE FUNCTION order_total(pIdOrder integer)
RETURNS double precision LANGUAGE sql STABLE AS $$
    SELECT COALESCE(sum("количество" * "цена"), 0) FROM "позиция_заказа" WHERE "заказ_id" = pIdOrder;
$$;
"""
