# CampusBite workspace

CampusBite is a responsive, installable web app for one campus café. Students browse scheduled food, PKR prices, portions, dietary details, ingredients, allergens, and reviews. Café staff manage foods, categories, schedules, stock, and review moderation.

## Run & operate

- `pnpm --filter @workspace/campusbite run dev` — run the CampusBite web preview.
- `cd artifacts/campusbite && pytest -q` — run its isolated Flask tests.
- `cd artifacts/campusbite && python3 scripts/init_db.py` — create the SQLite tables.
- `cd artifacts/campusbite && python3 scripts/seed_data.py` — add illustrative sample café data.
- `cd artifacts/campusbite && python3 scripts/create_admin.py` — securely bootstrap the first administrator.
- `pnpm --filter @workspace/api-server run dev` — run the existing API Server artifact.

CampusBite reads `SECRET_KEY` or the configured `SESSION_SECRET`. Do not put real secrets in source files. Development seeds sample menu data on first launch; production does not seed sample data.

## Stack

- CampusBite: Python 3, Flask, Jinja2, vanilla JavaScript, SQLite/SQLAlchemy, Flask-WTF CSRF protection, Gunicorn.
- Workspace: pnpm monorepo with separate web, API, and design artifacts.
- Existing API Server: Express, TypeScript, PostgreSQL/Drizzle, and generated OpenAPI client packages.

## Where things live

- `artifacts/campusbite/README.md` — app setup, operation, and deployment notes.
- `artifacts/campusbite/app/models.py` — CampusBite relational model.
- `artifacts/campusbite/app/public/`, `admin/`, `reviews/` — Flask routes by audience.
- `artifacts/campusbite/app/services/` — menu filtering, stock, and demo-data rules.
- `artifacts/campusbite/app/templates/` and `static/` — Jinja pages, styles, JavaScript, and PWA files.
- `artifacts/campusbite/scripts/` — database setup, sample data, admin bootstrap, and icon generation.
- `artifacts/campusbite/tests/` — Flask test-client tests using temporary SQLite databases.
- `artifacts/api-server/` and `lib/` — existing API and shared workspace packages.

## Architecture decisions

- CampusBite is a standalone Flask/Jinja app in its own artifact; it does not depend on the existing API Server.
- SQLite is the initial database. Use the app-specific `CAMPUSBITE_DATABASE_URL` to select another SQLAlchemy database; CampusBite deliberately ignores a workspace-wide `DATABASE_URL`.
- Staff own the authoritative portion count for each meal occurrence. Availability labels combine saved stock with the campus-local serving window.
- Public reviews are visible on submission and can be hidden by staff. Hidden reviews are excluded from public ratings.
- The service worker caches public pages only; it must not cache staff pages or admin data.

## Product

- Student-facing homepage, daily and weekly menus, search and filters, budget matching, food details, ratings, and optional reviews.
- Protected staff dashboard for food/category management, schedules, per-occurrence stock, and review moderation.
- PWA installation, offline fallback, and a clear stale-data notice.
- The first version is for one café and does not handle orders, payments, delivery, or inventory transactions.

## User requirements

- Build CampusBite with Flask, Jinja2, vanilla JavaScript, and SQLite, with accessible responsive pages and a complete staff workflow.
- Keep admin routes protected, hash administrator passwords, validate input, and use CSRF protection for state changes.
- Treat sample food details as illustrative; only staff-confirmed ingredients, allergens, and dietary claims should be shown as café facts.

## Gotchas

- Run app-specific Python commands from `artifacts/campusbite/`; the package scripts and artifact routing are configured for that directory.
- SQLite must live on persistent storage in production. Back up the database before updates; `create_all()` creates missing tables but does not migrate existing columns.
- `scripts/create_admin.py` creates only the first administrator and will not reset an existing account.
- Check the PWA on target devices after publishing; browser install and offline behavior vary by platform.

