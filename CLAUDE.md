# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

KeyByMe is a personal Django app (in Spanish) for managing contacts, encrypted passwords, bookmarked URLs, media files (documents/photos/videos), and reminders — organized by user-defined categories — with centralized user administration and per-user storage quotas.

## Commands

```bash
# Activate venv (Windows)
venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Run dev server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user (must then be flagged is_admin_principal=True via /admin)
python manage.py createsuperuser

# Tests (per-app, standard Django test runner — no test framework config beyond default)
python manage.py test
python manage.py test vault
```

Config comes from a `.env` file at the repo root (see `.env.example`), loaded via `django-environ` in `config/settings.py`. Required vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `VAULT_ENCRYPTION_KEY`. Losing `VAULT_ENCRYPTION_KEY` makes all stored vault passwords permanently unrecoverable.

Database is PostgreSQL only (no SQLite fallback).

## Architecture

Three apps, each with a distinct responsibility:

- **`accounts`** — `CustomUser` (`AUTH_USER_MODEL = "accounts.CustomUser"`), extending `AbstractUser` with `is_admin_principal`, `role`, `storage_quota_gb`/`storage_used_bytes`, `is_suspended`, `created_by`. Storage quota checks go through `user.has_space_for(bytes)` / `storage_available_bytes`, not ad-hoc math. Permission checks go through `user.has_permission(submodule_codename)`, which checks `UserPermissionOverride` first (per-user grant/revoke), then falls back to the user's `Role`.
- **`menus`** — dynamic permission/menu system: `Module` → `SubModule` (e.g. codename `docs.upload`) → `Role` (reusable permission sets, via `RolePermission`) → optional per-user `UserPermissionOverride`. This is the source of truth for what a user can see/do; it's independent of Django's built-in `auth.Permission`.
- **`vault`** — the actual user-facing data: `Contact`, `VaultPassword`, `Url`, `MediaFile`, `Reminder`, plus `Category`. All are owned via an `owner` FK to `CustomUser`.

### Categories

`Category` (`vault/models.py`) is a per-user catalog (`owner` FK, unique per owner) shared across `Contact`, `VaultPassword`, `Url`, `MediaFile`, and `Reminder` via a nullable `category` FK (`on_delete=SET_NULL`) — one category per record, not M2M. Forms filter the `category` choice to the current user's categories via `UserCategoryFormMixin` (`vault/forms.py`), which needs a `user` kwarg — views get this from `UserFormKwargsMixin` (`vault/mixins.py`). List views support `?category=<id>` and `?q=<text>` filtering via `SearchableListMixin`.

### Ownership + access pattern in `vault`

All class-based views use one of two mixins from `vault/mixins.py` (stacked with `LoginRequiredMixin`):
- `OwnerQuerysetMixin` (list/detail/update/delete) — filters `get_queryset()` to `owner=request.user` so a user can never reach another user's row via URL manipulation.
- `OwnerCreateMixin` (create) — force-sets `form.instance.owner = request.user` on save.

Any new vault view touching per-user data should use one of these rather than re-deriving the filter.

### VaultPassword encryption

Passwords are stored reversibly (not hashed) via Fernet symmetric encryption (`cryptography` lib), because users need to retrieve the plaintext. `VaultPassword._encrypted_password` is a `BinaryField`; use `instance.set_password(raw)` / `instance.get_password()` — never touch `_encrypted_password` directly. The Fernet key comes from `settings.VAULT_ENCRYPTION_KEY` via `get_fernet()` in `vault/models.py`.

Both `VaultPasswordForm` (`vault/forms.py`) and `VaultPasswordAdminForm` (`vault/admin.py`) duplicate the same pattern: a write-only `password` `CharField` (blank = "don't change"), required only on create, with `save()` calling `instance.set_password()` when a value was entered. Keep both in sync if this pattern changes.

`PasswordRevealView` is a separate, dedicated view/template from the list view specifically so plaintext exposure stays isolated to one auditable code path — list/detail views for `VaultPassword` must never render `get_password()`.

### MediaFile storage quota

Quota enforcement is manual, not signal-based: `MediaFileCreateView.form_valid` and `MediaFileUpdateView.form_valid` (`vault/views.py`) check `user.storage_quota_gb`/`storage_used_bytes` against the incoming file size *before* saving, then adjust `storage_used_bytes` after save. `MediaFile.delete()` (`vault/models.py`) decrements it symmetrically. If you add another way to create/delete/replace `MediaFile` rows, replicate both sides of this bookkeeping or it will drift.

Only files with an extension in `ALLOWED_MEDIA_EXTENSIONS` (`vault/models.py`, whitelist, not blacklist) can be uploaded — this is what blocks executables. Add new extensions there, never loosen it to a blacklist.

**Gotcha:** in `MediaFileUpdateView.form_valid`, `self.object` is the same instance as `form.instance` — by the time `form_valid` runs, `form.is_valid()` has already mutated `self.object.file` in place with the *new* upload (via `ModelForm._post_clean`/`construct_instance`). So the pre-edit file name/size must be fetched with a fresh query (`MediaFile.objects.values_list(...).get(pk=...)`), not read off `self.object` — reading it off `self.object` silently grabs the new value, breaking both quota accounting and old-file cleanup.

### Deployment

Runs on a plain AWS EC2 Ubuntu instance (`~/websites/keymyme2`, venv at `env/`), not a PaaS. nginx listens on :80 and reverse-proxies everything to gunicorn on `127.0.0.1:8000`; gunicorn itself is managed by a systemd unit (`keybyme.service`) rather than a `Procfile` (the `Procfile` is unused there — it's leftover from an earlier DigitalOcean App Platform plan). `whitenoise` still serves static files, but unlike `manage.py runserver`, gunicorn requires `python manage.py collectstatic --noinput` after every deploy or new/changed static assets 404.

Deploy flow on the EC2 box: `git pull`, `pip install -r requirements.txt`, `python manage.py migrate`, `collectstatic`, then `sudo systemctl restart keybyme`. There's no domain/TLS wired up yet (nginx has `server_name _`, plain HTTP by IP) — `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` are therefore overridable via env (`.env`) independently of `DEBUG`, since forcing `Secure` cookies without HTTPS breaks login. `MediaFile` uploads currently stay on the instance's local disk (`USE_SPACES=False`); the `django-storages`/S3 path in this codebase talks to DigitalOcean Spaces specifically, not plain AWS S3, so switching it on would need adjusting `SPACES_ENDPOINT_URL` or generalizing that config.

There's no cron/scheduled job on the box itself. `manage.py send_due_reminders` (email + SMS for due Reminders) is triggered externally by a GitHub Actions workflow (`.github/workflows/send-reminders.yml`) that POSTs to `/vault/cron/send-reminders/` every 15 minutes, authenticated via a shared `X-Cron-Token` header checked against `CRON_SECRET`.

## Localization

User-facing strings, model `verbose_name`s, help text, and comments are in Spanish (`LANGUAGE_CODE = 'es'`, `TIME_ZONE = 'America/Mexico_City'`). Match this convention for new user-facing text and Django admin config.
