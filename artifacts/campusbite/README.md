# CampusBite

CampusBite is a one-café campus menu and food availability site. Students can see scheduled food, prices in PKR, serving times, stock updates, ingredients, allergen notes, dietary details, and reviews without creating an account. Café staff use a protected dashboard to manage foods, categories, schedules, stock, and review moderation.

The implementation uses Python 3, Flask, Jinja2, Flask-SQLAlchemy, SQLite, Flask-WTF CSRF protection, Werkzeug password hashing, and small amounts of vanilla JavaScript. The templates and static assets live in `app/`; the React/Vite scaffold is not used to render this app.

## Development

From `artifacts/campusbite/`:

```bash
python3 -m pip install -r requirements.txt
python3 run.py
```

The Replit preview starts with:

```bash
pnpm --filter @workspace/campusbite run dev
```

On the first development launch, CampusBite creates its SQLite tables and adds idempotent sample categories, food, schedules, and example reviews. The sample menu and its ingredient/allergen notes are illustrative data only—not confirmed information from a real café. Set `CAMPUSBITE_DEMO_DATA=0` to skip sample data.

## Database and administrator setup

SQLite stores its development database at `instance/campusbite.db`. The app deliberately ignores a workspace-wide `DATABASE_URL` and accepts an optional `CAMPUSBITE_DATABASE_URL` override instead.

```bash
python3 scripts/init_db.py
python3 scripts/seed_data.py
python3 scripts/create_admin.py
```

The administrator bootstrap prompts for a username and password; passwords must be at least 12 characters. It refuses to replace an existing administrator and does not print or store a plain-text password. There is no default admin account.

Set `SECRET_KEY` in the environment or Replit Secrets before deployment. The app also accepts the existing `SESSION_SECRET` environment secret. A local development-only fallback is used only outside production. Never put a real secret in `.env.example` or source control.

## Tests

From `artifacts/campusbite/`:

```bash
pytest
```

Tests use temporary SQLite databases and do not touch the development database.

## Included features

- Public homepage, current/future day menus, weekly view, and food detail pages.
- Backend search and combined category, availability, vegetarian, dietary, spice, and PKR budget filters; lowest/highest price sorting.
- Saved per-serving stock with low-stock/sold-out rules and a 20-second visibility-aware public refresh.
- Optional one-to-five-star ratings, short reviews, hashed random browser identifiers, repeat-submit limits, IP rate limiting, and administrator moderation.
- Secure administrator login, expiring sessions, protected routes, POST-only state changes, CSRF protection, and login rate limiting.
- Food and category management, future schedule management, safe food deletion, and stock updates.
- Installable PWA manifest and icons, public page caching, offline fallback, and stale-data notice. Admin pages are excluded from the service-worker cache.
- Responsive accessible templates, keyboard focus, reduced-motion support, and graceful image fallback.

## Stock and availability

Each schedule occurrence has its own authoritative quantity. Quantity zero is Sold Out; one through five is Low Stock by default; quantities above five are Available. Staff stock changes update that occurrence's timestamp. The public polling endpoint reflects saved changes—it does not detect sales or physically count inventory. The UI distinguishes stock from whether the serving window is active now.

Serving times in the sample data are examples. Staff configure the actual dates and time windows. Dates and serving times are treated as campus-local Asia/Karachi time.

## Deployment notes

The artifact has a Flask production run command using Gunicorn. Configure a long random `SECRET_KEY` (or `SESSION_SECRET`) and ensure `FLASK_ENV=production`. The production service binds to the port configured for the artifact.

SQLite is suitable for this first version when the host provides a persistent writable disk. Confirm that the deployment preserves `instance/campusbite.db` across restarts and releases, and back it up before upgrades. If the deployment filesystem is ephemeral or the café needs concurrent multi-instance writes, configure a managed relational database through `CAMPUSBITE_DATABASE_URL` before publishing. The first version intentionally supports one café and does not include orders, payments, delivery tracking, or AI recommendations.

For HTTPS deployments, session and device cookies are marked Secure. Install on Android/desktop from the browser's install prompt. On iPhone/iPad, use Share → Add to Home Screen. Service-worker behavior and platform-specific installation should be checked on target devices after deployment.

## Project structure

```text
app/
  admin/       protected staff routes and workflows
  public/      public menu, weekly view, food details, polling, PWA routes
  reviews/     public review submission and abuse prevention
  services/    menu, stock, and sample-data rules
  static/      CSS, JavaScript, PWA manifest, service worker, icons
  templates/   public, admin, partial, and error pages
  models.py    relational SQLAlchemy models
  config.py    environment and session configuration
scripts/       database setup, sample data, admin bootstrap, icon generation
tests/         isolated Flask test-client tests
```
