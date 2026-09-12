import os

from flask import Flask, render_template

from config import Config
from app.extensions import db, migrate, login_manager, csrf
from app.utils.formatting import register_filters
from app.cli import register_cli


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    register_filters(app)
    register_cli(app)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.admin.routes import bp as admin_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.transactions.routes import bp as transactions_bp
    from app.blueprints.bills.routes import bp as bills_bp
    from app.blueprints.forecast.routes import bp as forecast_bp
    from app.blueprints.wishlist.routes import bp as wishlist_bp
    from app.blueprints.imports.routes import bp as imports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(forecast_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(imports_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.context_processor
    def inject_globals():
        return {"currency_symbol": app.config.get("CURRENCY_SYMBOL", "R")}

    return app
