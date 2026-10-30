# Lego Classifier

Практические работы по дисциплине «Методы и средства проектирования информационных систем»
(СПбГЭТУ «ЛЭТИ», гр. 3376): классификатор изделий LEGO, параметры, хозяйственные операции,
материальные спецификации (ПР №5) и маршрутная технология (ПР №6).

Стек: FastAPI, SQLAlchemy, PostgreSQL 15 (Docker), Jinja2 + Bootstrap.

## Первый запуск (один раз на каждом компьютере)

Нужны: Git, Python 3.12+, Docker Desktop.

```bash
git clone https://github.com/diiios/LEGO.git
cd LEGO

# 1. Локальные настройки (порт БД можно поменять, если 5433 занят)
copy .env.example .env          # macOS / Linux: cp .env.example .env

# 2. База данных в Docker
docker compose up -d

# 3. Виртуальное окружение — своё на каждом компьютере, папку venv не копируем
python -m venv venv
venv\Scripts\activate           # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt

# 4. Запуск
python run.py
```

Приложение: http://localhost:8000, документация API: http://localhost:8000/docs.
При первом запуске на пустой базе тестовые данные загружаются автоматически.
Дозаполнить существующую базу: `python fill_bom_data.py` (ПР №5), `python fill_route_data.py` (ПР №6).

## Работа в команде через ветки

`master` — всегда рабочая версия. Напрямую в `master` не коммитим: каждое задание делается
в отдельной ветке и попадает в `master` через Pull Request.

```bash
# перед началом работы — свежий master
git switch master
git pull

# новая ветка под задачу
git switch -c lab7-название

# ... работаем, проверяем, что запускается ...
git status
git add .
git commit -m "ПР7: таблицы и API ..."
git push -u origin lab7-название      # первый push ветки; дальше просто git push
```

Затем на GitHub: **Compare & pull request** → base: `master` ← compare: `lab7-название` →
товарищ смотрит изменения → **Merge** → **Delete branch**. После слияния у себя:
`git switch master && git pull`.

Если пока вы работали, `master` ушёл вперёд:

```bash
git switch lab7-название
git pull origin master          # подтянуть чужие изменения в свою ветку
# при конфликте: открыть файлы с <<<<<<< ======= >>>>>>>, оставить нужное,
# git add <файл> и git commit
```

Названия веток: `lab7-...` — задание, `fix-...` — исправление, `report-...` — правки отчёта.

## Что не попадает в репозиторий

`venv/`, `.env`, `__pycache__/`, логи, `.DS_Store` (см. `.gitignore`). Окончания строк
выравниваются автоматически (`.gitattributes`), поэтому Windows и macOS не дают «изменений во всём файле».
