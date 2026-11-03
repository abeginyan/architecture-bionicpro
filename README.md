# BionicPRO — SSO / отчёты

Учебный стенд: React-фронтенд + Keycloak (SSO по OAuth 2.0), запускается через
`docker compose`.

## Спринт 9, задача 1 — усиление безопасности: Code Grant → Authorization Code + PKCE (S256)

### Что изменилось

Ранее публичный клиент `reports-frontend` использовал «чистый» Authorization
Code Grant. Теперь включён **Authorization Code Flow с PKCE и методом S256**:

- **Keycloak** (`keycloak/realm-export.json`), клиент `reports-frontend`:
  - публичный клиент (без client secret), **Standard flow — вкл.**;
  - **Implicit flow — выкл.**, **Direct access grants — выкл.** (в репозитории не
    использовались);
  - атрибут **`pkce.code.challenge.method` = `S256`** (в консоли это
    *Proof Key for Code Exchange Code Challenge Method = S256*) — Keycloak
    **отклоняет** запросы авторизации без `code_challenge`;
  - точные (без `*`) redirect URI и web origin для локальной разработки:
    redirect `http://localhost:3000/`, web origin `http://localhost:3000`.
  - Пользователи, роли и клиент `reports-api` оставлены без изменений.
- **Фронтенд** (`frontend/src/App.tsx`): в `ReactKeycloakProvider` передаётся
  `initOptions={{ pkceMethod: 'S256', checkLoginIframe: false }}`. `keycloak-js`
  сам генерирует `code_verifier`, отправляет `code_challenge` и
  `code_challenge_method=S256` в запросе авторизации и `code_verifier` в запросе
  токена. Токены хранятся **в памяти** `keycloak-js` (не в `localStorage`).

> Компромисс по хранению токенов: in-memory безопаснее `localStorage`
> (нет доступа из постороннего JS, нет утечки между вкладками), но токен
> теряется при перезагрузке страницы — повторная тихая аутентификация
> происходит через Keycloak. Полноценное серверное хранение — задача BFF
> (см. «Целевая архитектура»), в рамках этого шага не реализуется.

### Как запустить

```bash
docker compose up -d --build
```

- Фронтенд: http://localhost:3000
- Keycloak: http://localhost:8080 (админ `admin` / `admin`)
- Realm `reports-realm` импортируется автоматически (`--import-realm`).

> Примечание: изменения в `realm-export.json` применяются только при **чистой**
> БД — Keycloak с `--import-realm` пропускает импорт, если realm уже существует.
> Для переимпорта: `docker compose down`, удалить каталог
> `./postgres-keycloak-data`, затем `docker compose up -d`.

Тестовые пользователи (из realm): `user1/password123`, `admin1/admin123`,
`prothetic1/prothetic123` и др.

### Как проверить, что PKCE действительно используется

**1. Запрос авторизации БЕЗ `code_challenge` должен отклоняться** (негативный тест):

```bash
curl -s -o /dev/null -D - \
 "http://localhost:8080/realms/reports-realm/protocol/openid-connect/auth?client_id=reports-frontend&response_type=code&scope=openid&state=neg&redirect_uri=http://localhost:3000/" \
 | grep -i location
# Location: http://localhost:3000/?error=invalid_request&error_description=Missing+parameter%3A+code_challenge_method&state=neg
```

**2. Полный поток с `code_verifier`** (позитивный) и **неверный `code_verifier`**
(негативный): запрос токена с правильным verifier возвращает `access_token`
(HTTP 200), с неверным — `HTTP 400 invalid_grant: PKCE verification failed`.

**3. Через браузер:** открыть http://localhost:3000, нажать *Login*. В DevTools →
Network у запроса `.../openid-connect/auth` в query будут `code_challenge` и
`code_challenge_method=S256`, а у POST `.../openid-connect/token` в теле —
`code_verifier`.

### Целевая архитектура (куда это развивается)

- **Keycloak как identity broker, по одному на страну** — локальное хранение
  персональных данных и соответствие требованиям резидентства.
- **User federation к локальному LDAP/AD** — пользователи остаются в
  корпоративном каталоге, Keycloak федерирует их (в стенде есть пример
  `ldap/config.ldif`).
- **Внешние IdP как Identity Providers** с опцией **«Store Tokens» выключена** —
  Keycloak не хранит токены внешних провайдеров, только транслирует вход.
- **BFF (Backend-for-Frontend)** хранит access/refresh токены на сервере, а
  браузеру отдаёт только **HttpOnly-cookie сессии** — токены не доступны из JS.
  *(BFF в рамках этой задачи не реализуется — это следующий шаг.)*
