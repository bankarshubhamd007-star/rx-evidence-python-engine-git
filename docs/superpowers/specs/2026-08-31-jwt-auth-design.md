# JWT Authentication — Design Spec

Date: 2026-08-31
Repos affected: `rx-evidence-engine-py` (backend, owns all auth logic), `rx-evidence-physician-dashboard-github` (frontend, login/signup/logout UI only)

## Goal

Replace the mock login screen (any credentials sign in) with real authentication.
Two user roles: `physician` and `patient`. Signup + login + logout, backed by
MongoDB, JWT-based sessions. Backend is the sole owner of auth logic — password
hashing, JWT issuance/verification, cookie management, role checks. Frontend
only implements the login/signup/logout UI flow and calls the backend.

Out of scope (YAGNI for this pass): refresh tokens, email verification,
password reset, OAuth/social login, rate limiting on auth endpoints.

## Architecture

```
Browser (Next.js frontend)
  │  fetch(..., { credentials: "include" })
  ▼
FastAPI backend  /v1/auth/*
  │  bcrypt hash/verify, JWT sign/verify, Set-Cookie
  ▼
MongoDB  `users` collection
```

Session token travels as an **httpOnly cookie** set directly by the FastAPI
response — never exposed to frontend JS, never stored in localStorage. The
frontend never parses or holds the JWT; it just relies on the browser sending
the cookie automatically on subsequent requests (`credentials: "include"`).

## Backend — `rx-evidence-engine-py`

### New dependencies
- `bcrypt` — password hashing
- `pyjwt` — JWT sign/verify

### Config (`app/shared/core/config.py`)
Add to `Settings`:
- `jwt_secret_key: str` (required, no default — fail fast if missing)
- `jwt_algorithm: str = "HS256"`
- `jwt_expire_minutes: int = 10080` (7 days)
- `cors_allowed_origin: str = "http://localhost:3000"` (frontend origin; required because `allow_credentials=True` cannot pair with `allow_origins=["*"]`)

### Schemas (`app/shared/models/schemas.py`)
```python
class UserRole(str, Enum):
    PHYSICIAN = "physician"
    PATIENT = "patient"

class SignupRequest(CamelModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8, max_length=128)
    role: UserRole

class LoginRequest(CamelModel):
    email: EmailStr
    password: str

class UserPublic(CamelModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    role: UserRole

class AuthResponse(CamelModel):
    user: UserPublic
```
(No token in the JSON body — it only ever goes out as a cookie.)

### Module layout
Follows existing `app/chrome_extension` / `app/physician_dashboard` pattern:

```
app/auth/
  controllers/
    auth_controller.py     # /signup /login /logout /me
  dependencies.py          # get_current_user, require_role
app/shared/services/auth_service.py   # hash_password, verify_password, create_token, decode_token
app/shared/repositories/user_repository.py  # Mongo CRUD on `users` collection
```

### `user_repository.py`
- Collection: `users` in `settings.mongodb_db_name`
- Unique index on `email` (created at repo import / startup)
- `create_user(doc) -> dict`
- `get_by_email(email) -> dict | None`
- `get_by_id(user_id) -> dict | None`

User document shape:
```
{ id: str (uuid4 hex), email: str, password_hash: str, full_name: str,
  phone: str | None, role: "physician" | "patient", created_at: float }
```

### `auth_service.py`
- `hash_password(password: str) -> str` — bcrypt
- `verify_password(password: str, password_hash: str) -> bool`
- `create_access_token(user_id: str, role: str) -> str` — JWT with `sub`, `role`, `exp`
- `decode_access_token(token: str) -> dict` — raises on invalid/expired

### `dependencies.py`
- `get_current_user(request: Request) -> UserPublic` — reads `session` cookie,
  decodes JWT, loads user from repo, 401 if missing/invalid/expired/user gone
- `require_role(role: UserRole)` — dependency factory wrapping `get_current_user`,
  403 if role mismatch. Available for future protected routes; not retrofitted
  onto existing endpoints in this pass.

### `auth_controller.py` — mounted at `/v1/auth`

- `POST /signup` — body `SignupRequest`. 409 if email exists. Hash password,
  insert user, issue token, set cookie, return `AuthResponse`.
- `POST /login` — body `LoginRequest`. 401 on bad email/password (same generic
  message for both to avoid user enumeration). Issue token, set cookie, return
  `AuthResponse`.
- `POST /logout` — clears the cookie. Returns 204.
- `GET /me` — protected via `get_current_user`. Returns `AuthResponse`.

Cookie settings: `httponly=True`, `samesite="lax"`, `secure=False` for local
dev (document that this must become `True` behind HTTPS in prod), `max_age`
matching `jwt_expire_minutes`, name `session`.

### `main.py`
- `app.include_router(auth_controller.router, prefix="/v1/auth", tags=["Auth"])`
- CORS: `allow_origins=[settings.cors_allowed_origin]`, keep `allow_credentials=True`.
  Drop the `"*"` origin (incompatible with credentials, and no longer needed —
  chrome extension calls don't carry cookies/credentials).

### `.env.example`
Add `JWT_SECRET_KEY`, `CORS_ALLOWED_ORIGIN=http://localhost:3000`.

## Frontend — `rx-evidence-physician-dashboard-github`

No auth logic here — only UI flow calling the backend.

### `src/lib/api.ts` (new)
Thin wrapper:
```ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authFetch(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${API_BASE}/v1/auth${path}`, {
    ...opts,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...opts.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? "Request failed");
  }
  return res.status === 204 ? null : res.json();
}

export const signup = (payload) => authFetch("/signup", { method: "POST", body: JSON.stringify(payload) });
export const login = (payload) => authFetch("/login", { method: "POST", body: JSON.stringify(payload) });
export const logout = () => authFetch("/logout", { method: "POST" });
export const getMe = () => authFetch("/me");
```

### `login-form.tsx`
Replace hardcoded demo defaults with empty fields. Call `login({ email, password })`.
On error, show inline message under the form. On success, call `onSubmit(user)`.

### `signup-form.tsx`
Map form fields to `SignupRequest` shape (`fullName`, `email`, `phone`,
`password`, `role`). Add client-side check: `newPassword === repeatPassword`
before calling API. Call `signup(payload)`, same error/success handling.

### `auth-view.tsx`
- Role mapping: `doctor` → `physician`, `consumer` → `patient`
- `handleAuthRedirect` becomes `handleAuthSuccess(user)`: routes by
  `user.role` (`physician` → `/doctor/dashboard`, `patient` → `/consumer/home`)
- Remove "Any credentials will sign in directly" demo footer text
- `isLoading` driven by the actual fetch, errors surfaced from child forms

### `middleware.ts` (new, repo root)
Presence-only cookie check for redirect UX (backend still enforces real auth
on every API call — this is just to avoid flashing protected pages):
```ts
export function middleware(req: NextRequest) {
  const hasSession = req.cookies.has("session");
  const isAuthRoute = req.nextUrl.pathname === "/" || req.nextUrl.pathname.startsWith("/login");
  if (!hasSession && !isAuthRoute) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  return NextResponse.next();
}
export const config = { matcher: ["/((?!_next|api|favicon.ico).*)"] };
```
Note: cookie is set by the backend (different origin in dev, e.g.
`localhost:8000` vs `localhost:3000`), so the browser must actually receive
and store it against the frontend's requests — this works because the browser
attaches cookies per the cookie's own domain, not the page's origin, as long
as `credentials: "include"` is used and the cookie's `SameSite`/`domain`
allow cross-site sending in dev (`SameSite=Lax` + no explicit `Domain` means
the cookie is scoped to the backend host, sent on requests *to* that host,
readable by `middleware.ts` only if it's the same host the browser is on).

**Constraint surfaced by this:** with backend on `localhost:8000` and frontend
on `localhost:3000`, the cookie set by the backend lives on the `8000` host
and will NOT be visible to Next.js `middleware.ts` (which inspects cookies
sent to `3000`). The presence-check middleware therefore cannot work across
different ports/hosts in dev.

Resolution: keep auth entirely backend-owned as decided, but make the
presence-check practical by having `getMe()` drive client-side gating instead
of edge middleware — e.g., a small client component wraps `app-layout-shell.tsx`,
calls `GET /me` on mount, and redirects to `/login` on 401. This keeps zero
auth logic in the frontend (it's just calling the backend's own verification
endpoint) while working correctly across origins. `middleware.ts` is dropped
from this design in favor of this approach.

### `app-layout-shell.tsx`
On mount (for non-auth routes), call `getMe()`; on 401 redirect to `/login`.
Render nothing (or a lightweight loading state) until the check resolves to
avoid flashing protected content.

### Sidebar — logout button
Add to `src/components/shared/sidebar.tsx` and
`src/components/consumer/shared/consumer-sidebar.tsx`: button calls `logout()`
then `router.push("/login")`.

### `.env.local` (frontend, gitignored)
`NEXT_PUBLIC_API_URL=http://localhost:8000`

## Error Handling

| Case | Backend status | Frontend behavior |
|---|---|---|
| Signup, email exists | 409 | Inline "Email already registered" |
| Signup, weak password / bad email | 422 | Inline validation message |
| Login, wrong email/password | 401 | Inline "Invalid email or password" |
| `/me` with missing/expired/invalid cookie | 401 | Redirect to `/login` |
| Role mismatch on a `require_role`-protected route (future) | 403 | Not used yet — no protected business routes in this pass |

## Testing

No existing test suite for controllers in this repo. Verification is manual,
via curl, for this pass:
1. Signup physician → 200, `Set-Cookie` present, user in Mongo `users` collection
2. Signup same email again → 409
3. Login correct password → 200, cookie set
4. Login wrong password → 401
5. `GET /me` with cookie → 200, correct user/role
6. `GET /me` without cookie → 401
7. Logout → cookie cleared, subsequent `/me` → 401
8. Frontend: signup as doctor → redirected to `/doctor/dashboard`; signup as
   patient → redirected to `/consumer/home`; refresh page → still logged in;
   logout → redirected to `/login`; visiting `/doctor/dashboard` while logged
   out → redirected to `/login`

curl examples (documented for the user, not part of the spec's test suite):
```bash
# Signup
curl -i -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"fullName":"Dr. Vance","email":"vance@clinic.org","phone":"+1-555-0192","password":"secretpass1","role":"physician"}'

# Login
curl -i -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email":"vance@clinic.org","password":"secretpass1"}'

# Me (reuses cookie jar)
curl -i http://localhost:8000/v1/auth/me -b cookies.txt

# Logout
curl -i -X POST http://localhost:8000/v1/auth/logout -b cookies.txt -c cookies.txt
```
