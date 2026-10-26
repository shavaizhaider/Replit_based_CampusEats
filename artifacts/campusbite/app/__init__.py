import os

from flask import Flask, g, jsonify, render_template, request, session
from flask_wtf.csrf import CSRFError

from .config import Config
from .extensions import csrf, db, enable_sqlite_foreign_keys, limiter
from .models import Admin


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "Set SECRET_KEY (or SESSION_SECRET) before running CampusBite in production."
        )

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    enable_sqlite_foreign_keys(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from .admin.routes import admin_bp
    from .public.routes import public_bp
    from .reviews.routes import reviews_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reviews_bp)

    @app.before_request
    def load_admin() -> None:
        admin_id = session.get("admin_id")
        g.current_admin = db.session.get(Admin, admin_id) if admin_id else None
        if g.current_admin is not None and not g.current_admin.is_active:
            session.clear()
            g.current_admin = None

    @app.context_processor
    def inject_shared_template_values() -> dict:
        return {"current_admin": getattr(g, "current_admin", None)}

    @app.template_filter("money")
    def format_money(value: object) -> str:
        from decimal import Decimal, InvalidOperation

        try:
            amount = Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            amount = Decimal("0.00")
        formatted = f"{amount:,.2f}"
        if formatted.endswith(".00"):
            formatted = formatted[:-3]
        return f"Rs. {formatted}"

    @app.template_filter("campus_time")
    def format_campus_time(value: object) -> str:
        if value is None:
            return ""
        return value.strftime("%I:%M %p").lstrip("0")

    @app.template_filter("local_datetime")
    def format_local_datetime(value: object) -> str:
        from datetime import timezone
        from zoneinfo import ZoneInfo

        if value is None:
            return "Not updated yet"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("Asia/Karachi")).strftime("%b %-d, %I:%M %p")

    @app.after_request
    def add_security_and_cache_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if request.path.startswith("/admin") or request.path == "/admin/login":
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        return (
            render_template(
                "errors/400.html",
                message="Your form session expired. Refresh the page and try again.",
            ),
            400,
        )

    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Invalid request."), 400
        return render_template("errors/400.html", message="Please check your request."), 400

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found."), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify(error="Something went wrong. Please try again."), 500
        return render_template("errors/500.html"), 500

    return app
