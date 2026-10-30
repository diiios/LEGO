# Выкладка на сервер (CI/CD)

Как это работает:

```
Pull Request в master ──► GitHub Actions: «Проверка» (запуск приложения на чистой базе)
        │ Merge
        ▼
push в master ──► «Проверка» ──► «Выкладка на сервер»: SSH на VPS → git reset --hard origin/master
                                  → docker compose -f docker-compose.prod.yml up -d --build
```

На сервере работают три контейнера: `postgres` (база, наружу не открыта), `app` (FastAPI) и
`caddy` (приём запросов на 80/443, HTTPS для домена, пароль на сайт). Данные базы хранятся в
Docker-томе и при выкладке новой версии не теряются. На сервере (`ENV=production`) кнопки
«Тестовые данные» и «Очистить БД» отключены, чтобы никто не стёр базу.

Файлы: `Dockerfile`, `docker-compose.prod.yml`, `Caddyfile`, `.github/workflows/deploy.yml`.

---

## 1. Подготовка VPS (один раз, Ubuntu 22.04 / 24.04)

Подключиться под root: `ssh root@IP_СЕРВЕРА`.

```bash
# обновления и Docker
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh

# пользователь для выкладки (от его имени работает GitHub Actions)
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy

# брандмауэр: только SSH и веб
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

## 2. SSH-ключ для GitHub Actions (один раз)

На своём компьютере (PowerShell или терминал):

```bash
ssh-keygen -t ed25519 -C "github-actions-lego" -f lego_deploy -N ""
```

Появятся два файла: `lego_deploy` (закрытый ключ — только в GitHub Secrets, никому не пересылать)
и `lego_deploy.pub` (открытый — на сервер). На сервере под root:

```bash
mkdir -p /home/deploy/.ssh
nano /home/deploy/.ssh/authorized_keys      # вставить содержимое lego_deploy.pub
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

Проверка с компьютера: `ssh -i lego_deploy deploy@IP_СЕРВЕРА` — должно пустить без пароля.

## 3. Проект и настройки на сервере (один раз)

```bash
su - deploy
git clone https://github.com/diiios/LEGO.git ~/LEGO
cd ~/LEGO
cp .env.example .env
docker run --rm caddy:2 caddy hash-password --plaintext 'ПАРОЛЬ_ДЛЯ_САЙТА'   # скопировать хэш
nano .env
```

В `.env` на сервере обязательно поменять:

| Переменная | Значение |
|---|---|
| `DB_PASSWORD` | длинный случайный пароль базы (не `postgres`) |
| `SITE_ADDRESS` | домен (`lego.example.ru`) или `:80`, если домена нет |
| `AUTH_USER` | логин для входа на сайт |
| `AUTH_HASH` | хэш пароля **в одинарных кавычках**: `AUTH_HASH='$2a$14$...'` |

Если у домена есть A-запись на IP сервера, Caddy сам получит HTTPS-сертификат.

Первый запуск вручную:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f app     # Ctrl+C — выйти из логов
```

При первом запуске на пустой базе загружаются тестовые данные (около минуты). Сайт:
`http://IP_СЕРВЕРА` (или `https://домен`), браузер спросит логин и пароль.

Если репозиторий станет приватным: на сервере `ssh-keygen -t ed25519`, открытый ключ добавить в
GitHub → репозиторий → Settings → Deploy keys (только чтение), клонировать по SSH
(`git@github.com:diiios/LEGO.git`).

## 4. Секреты в GitHub (один раз, делает владелец репозитория)

GitHub → репозиторий → **Settings → Secrets and variables → Actions → New repository secret**:

| Секрет | Значение |
|---|---|
| `VPS_HOST` | IP-адрес сервера |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | всё содержимое файла `lego_deploy` (вместе со строками BEGIN/END) |
| `VPS_PORT` | порт SSH, только если не 22 |

## 5. Защита ветки master (один раз, владелец)

**Settings → Branches → Add branch ruleset** (или Branch protection rule) для `master`:
- Require a pull request before merging;
- Require status checks to pass → выбрать проверку **«Проверка (запуск приложения на чистой базе)»**
  (она появится в списке после первого запуска workflow).

Теперь в `master` попадает только то, что прошло Pull Request и проверку, а значит, на сервер не
выкатится версия, которая не запускается.

## 6. Как пользоваться

- Открыли Pull Request — во вкладке PR видно, прошла ли проверка (зелёная галочка / красный крестик).
- Нажали Merge — через 1–3 минуты новая версия на сервере. Ход выкладки: вкладка **Actions**.
- Выложить заново без изменений: **Actions → CI/CD → Run workflow**.
- Откатить неудачную версию: на GitHub открыть слитый PR → **Revert** → слить созданный PR,
  откат выкатится автоматически.

## 7. Полезные команды на сервере

```bash
cd ~/LEGO
docker compose -f docker-compose.prod.yml ps                 # состояние контейнеров
docker compose -f docker-compose.prod.yml logs -f --tail=100 app
docker compose -f docker-compose.prod.yml restart app

# резервная копия базы
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres lego_classifier > backup_$(date +%F).sql
# восстановление
cat backup_2026-11-01.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres lego_classifier

# дозаполнить базу демо-данными без очистки
docker compose -f docker-compose.prod.yml exec app python fill_route_data.py
```

Полностью пересоздать базу на сервере (данные будут потеряны):
`docker compose -f docker-compose.prod.yml down -v && docker compose -f docker-compose.prod.yml up -d --build`.
