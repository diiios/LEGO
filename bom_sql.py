# bom_sql.py
"""
Задание 5. Материальная спецификация изделий (Bill of materials).

DDL-миграции и хранимые функции PostgreSQL, реализующие бизнес-логику:
  * bom_effective(pIdProd)          — действующая спецификация 1-го уровня с учётом модификаций;
  * find_bom(pIdProd)               — FIND_BOM: полный состав изделия на всю глубину вложенности;
  * calc_bom(pIdProd, pQ, pIdClass) — CALC_BOM: расчёт сводных норм расхода;
  * create_modification(...)        — CREATE_MODIFICATION: создание модификации базового изделия;
  * register_change(...)            — REGISTER_CHANGE: регистрация изменения спецификации.
"""

# Миграция существующей БД (таблица «изделие» уже создана в заданиях 1.3–1.4)
MIGRATION_SQL = """
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "тип_изделия" VARCHAR(30) NOT NULL DEFAULT 'ДЕТАЛЬ';
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "базовое_изделие_id" INTEGER
    REFERENCES "изделие"(id) ON DELETE SET NULL;
ALTER TABLE "изделие" ADD COLUMN IF NOT EXISTS "ед_изм_id" INTEGER
    REFERENCES "единица_измерения"(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_позиция_спец_изделие   ON "позиция_спецификации"("изделие_id");
CREATE INDEX IF NOT EXISTS ix_позиция_спец_компонент ON "позиция_спецификации"("компонент_id");
CREATE INDEX IF NOT EXISTS ix_изменение_спец_изделие ON "изменение_спецификации"("изделие_id");
-- ЕИ количества класса (Классификатор_изделий -> Единица_измерения): ссылочная целостность
UPDATE "классификатор" SET "базовая_ед_измерения" = NULL
    WHERE "базовая_ед_измерения" IS NOT NULL
      AND "базовая_ед_измерения" NOT IN (SELECT id FROM "единица_измерения");
ALTER TABLE "классификатор" DROP CONSTRAINT IF EXISTS fk_классификатор_ед_изм;
ALTER TABLE "классификатор" ADD CONSTRAINT fk_классификатор_ед_изм
    FOREIGN KEY ("базовая_ед_измерения") REFERENCES "единица_измерения"(id) ON DELETE SET NULL;
-- ЕИ количества изделия (кратность 1): если не задана — берётся ЕИ класса, иначе «шт»
UPDATE "изделие" и SET "ед_изм_id" = COALESCE(
        (SELECT k."базовая_ед_измерения" FROM "классификатор" k WHERE k.id = и."класс_id"),
        (SELECT u.id FROM "единица_измерения" u WHERE u."обозначение" = 'шт'))
    WHERE и."ед_изм_id" IS NULL;
"""

FUNCTIONS_SQL = r"""
-- ---------------------------------------------------------------------------
-- Наследуемая (базовая) часть спецификации изделия pIdProd.
-- Базовая часть = собственные позиции с флагом базы
--               + базовая часть его базового изделия, кроме компонентов,
--                 переопределённых (заменённых/исключённых) в самом изделии.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bom_base_part(pIdProd integer, pDepth integer DEFAULT 0)
RETURNS TABLE(позиция_id integer, источник_id integer, компонент_id integer,
              расход double precision, для_количества double precision,
              ед_изм_id integer, флаг_базы boolean, вид_позиции varchar)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    vBase integer;
BEGIN
    IF pDepth > 30 THEN RETURN; END IF;           -- защита от циклов в цепочке модификаций
    RETURN QUERY
        SELECT b.id, b."изделие_id", b."компонент_id", b."расход", b."для_количества",
               b."ед_изм_id", b."флаг_базы", b."вид_позиции"
        FROM "позиция_спецификации" b
        WHERE b."изделие_id" = pIdProd AND b."флаг_базы" AND b."вид_позиции" <> 'ИСКЛЮЧЕНИЕ';

    SELECT p."базовое_изделие_id" INTO vBase FROM "изделие" p WHERE p.id = pIdProd;
    IF vBase IS NOT NULL THEN
        RETURN QUERY
            SELECT bp.*
            FROM bom_base_part(vBase, pDepth + 1) bp
            WHERE NOT EXISTS (SELECT 1 FROM "позиция_спецификации" o
                              WHERE o."изделие_id" = pIdProd AND o."компонент_id" = bp.компонент_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Действующая спецификация 1-го уровня изделия pIdProd:
--   собственные позиции (кроме исключений) + унаследованная базовая часть
--   базового изделия (если компонент не был изменён в модификации).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bom_effective(pIdProd integer)
RETURNS TABLE(позиция_id integer, источник_id integer, компонент_id integer,
              расход double precision, для_количества double precision,
              ед_изм_id integer, флаг_базы boolean, вид_позиции varchar,
              унаследовано boolean)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    vBase integer;
BEGIN
    RETURN QUERY
        SELECT o.id, o."изделие_id", o."компонент_id", o."расход", o."для_количества",
               o."ед_изм_id", o."флаг_базы", o."вид_позиции", FALSE
        FROM "позиция_спецификации" o
        WHERE o."изделие_id" = pIdProd AND o."вид_позиции" <> 'ИСКЛЮЧЕНИЕ';

    SELECT p."базовое_изделие_id" INTO vBase FROM "изделие" p WHERE p.id = pIdProd;
    IF vBase IS NOT NULL THEN
        RETURN QUERY
            SELECT bp.позиция_id, bp.источник_id, bp.компонент_id, bp.расход, bp.для_количества,
                   bp.ед_изм_id, bp.флаг_базы, bp.вид_позиции, TRUE
            FROM bom_base_part(vBase) bp
            WHERE NOT EXISTS (SELECT 1 FROM "позиция_спецификации" o
                              WHERE o."изделие_id" = pIdProd AND o."компонент_id" = bp.компонент_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- FIND_BOM: полный состав изделия на всю глубину вложенности (рекурсивный CTE).
-- количество — потребность компонента на 1 единицу изделия верхнего уровня.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION find_bom(pIdProd integer)
RETURNS TABLE(уровень integer, родитель_id integer, компонент_id integer,
              расход double precision, для_количества double precision,
              норма_на_единицу double precision, количество double precision,
              ед_изм_id integer, унаследовано boolean, путь integer[])
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE t AS (
        SELECT 1 AS уровень, pIdProd AS родитель_id, e.компонент_id, e.расход, e.для_количества,
               e.расход / e.для_количества AS норма_на_единицу,
               e.расход / e.для_количества AS количество,
               e.ед_изм_id, e.унаследовано,
               ARRAY[pIdProd, e.компонент_id] AS путь
        FROM bom_effective(pIdProd) e
        UNION ALL
        SELECT t.уровень + 1, t.компонент_id, e.компонент_id, e.расход, e.для_количества,
               e.расход / e.для_количества,
               t.количество * e.расход / e.для_количества,
               e.ед_изм_id, e.унаследовано,
               t.путь || e.компонент_id
        FROM t CROSS JOIN LATERAL bom_effective(t.компонент_id) e
        WHERE t.уровень < 50 AND NOT (e.компонент_id = ANY(t.путь))   -- защита от циклов
    )
    SELECT * FROM t;
$$;

-- ---------------------------------------------------------------------------
-- CALC_BOM: сводные (суммарные) нормы расхода на pQ единиц изделия.
--   pIdClass IS NULL  — по всем конечным компонентам (материалам/покупным изделиям,
--                       у которых нет собственной спецификации);
--   pIdClass задан    — по всем компонентам любого уровня, класс которых входит
--                       в поддерево pIdClass классификатора.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION calc_bom(pIdProd integer, pQ double precision,
                                    pIdClass integer DEFAULT NULL)
RETURNS TABLE(компонент_id integer, ед_изм_id integer,
              норма_на_единицу double precision, сводная_норма double precision,
              вхождений bigint)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE классы AS (
        SELECT k.id FROM "классификатор" k WHERE k.id = pIdClass
        UNION
        SELECT k.id FROM "классификатор" k JOIN классы c ON k."родительский_id" = c.id
    ),
    состав AS (SELECT * FROM find_bom(pIdProd))
    SELECT s.компонент_id, s.ед_изм_id,
           SUM(s.количество)       AS норма_на_единицу,
           SUM(s.количество) * pQ  AS сводная_норма,
           COUNT(*)                AS вхождений
    FROM состав s
    JOIN "изделие" p ON p.id = s.компонент_id
    WHERE (pIdClass IS NULL
           AND NOT EXISTS (SELECT 1 FROM bom_effective(s.компонент_id)))
       OR (pIdClass IS NOT NULL AND p."класс_id" IN (SELECT id FROM классы))
    GROUP BY s.компонент_id, s.ед_изм_id;
$$;

-- ---------------------------------------------------------------------------
-- REGISTER_CHANGE: регистрация факта изменения спецификации изделия.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION register_change(pIdProd integer, pChangeDesc text,
                                           pType varchar DEFAULT 'ПРОЧЕЕ',
                                           pIdComp integer DEFAULT NULL,
                                           pOld varchar DEFAULT NULL,
                                           pNew varchar DEFAULT NULL,
                                           pAuthor varchar DEFAULT NULL)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    vId integer;
    vNum integer;
BEGIN
    SELECT COALESCE(MAX(id), 0) + 1 INTO vNum FROM "изменение_спецификации";
    INSERT INTO "изменение_спецификации"("изделие_id", "номер", "дата", "тип_изменения",
                                         "компонент_id", "старое_значение", "новое_значение",
                                         "описание", "автор")
    VALUES (pIdProd, 'ИИ-' || lpad(vNum::text, 4, '0'), now(), pType,
            pIdComp, pOld, pNew, pChangeDesc, pAuthor)
    RETURNING id INTO vId;
    RETURN vId;
END $$;

-- ---------------------------------------------------------------------------
-- CREATE_MODIFICATION: создание модификации на основе базового изделия.
-- Базовая спецификация не дублируется: модификация наследует её через
-- ссылку на базовое изделие и хранит только собственные отличия.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION create_modification(pIdBase integer, pName varchar,
                                               pArticle varchar DEFAULT NULL,
                                               pReason text DEFAULT NULL,
                                               pAuthor varchar DEFAULT NULL)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    vId integer;
    vBase "изделие"%ROWTYPE;
BEGIN
    SELECT * INTO vBase FROM "изделие" WHERE id = pIdBase;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Базовое изделие % не найдено', pIdBase;
    END IF;
    INSERT INTO "изделие"("класс_id", "наименование", "артикул", "created_at",
                          "тип_изделия", "базовое_изделие_id", "ед_изм_id")
    VALUES (vBase."класс_id", pName, pArticle, now(),
            vBase."тип_изделия", pIdBase, vBase."ед_изм_id")
    RETURNING id INTO vId;

    PERFORM register_change(vId,
        COALESCE(pReason, 'Создана модификация на основе изделия «' || vBase."наименование" || '»'),
        'МОДИФИКАЦИЯ', pIdBase, NULL, pName, pAuthor);
    RETURN vId;
END $$;
"""
