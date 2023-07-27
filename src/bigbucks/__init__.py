import os
from flask import Flask
from logging.handlers import RotatingFileHandler
import logging
from flask.logging import default_handler
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bootstrap import Bootstrap4


database = SQLAlchemy()
migration = Migrate()
login_manager = LoginManager()


# Factory function for creating app instance
def create_app():
    # Create the Flask application as an instance of the Flask class
    app = Flask(__name__)

    # Set the configuration variables
    config_type = os.getenv('CONFIG_TYPE', default='config.DevelopmentConfig')
    app.config.from_object(config_type)

    register_blueprints(app)

    # Bind the Flask extension instances to the Flask application instance
    database.init_app(app)
    migration.init_app(app, database)
    login_manager.init_app(app)
    Bootstrap4(app)

    import sqlalchemy as sa

    # Check if the database needs to be initialized
    engine = sa.create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    inspector = sa.inspect(engine)
    if not inspector.has_table("users"):
        with app.app_context():
            database.drop_all()
            database.create_all()

    return app


# Help function for bp registration
def register_blueprints(app):
    # Import the blueprints
    from bigbucks.home import home_bp
    from bigbucks.stocks import stocks_bp
    from bigbucks.users import users_bp

    # Register blueprints to the created Flask application instance (app)
    app.register_blueprint(home_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(users_bp, url_prefix='/users')


def configure_logging(app):
    # Logging Configuration
    file_handler = RotatingFileHandler('instance/bigbucks.log',
                                       maxBytes=16384,
                                       backupCount=20)
    file_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    # Remove the default logger configured by Flask
    # app.logger.removeHandler(default_handler)

    app.logger.info('Starting BigBucks...')
