import os
from datetime import timedelta

# Determine the folder of the top-level directory of this project


# Base Configuration
class Config(object):
    FLASK_ENV = 'development'
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', default='BAD_SECRET_KEY')
    WTF_CSRF_ENABLED = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    # The "sqlite:" prefix indicates that the database is a SQLite database.
    # The three forward slashes are a convention used to indicate the absolute path to the SQLite database file.
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL',
                                        default=f"sqlite:///{os.path.join(BASEDIR, 'instance', 'app.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALPHA_VANTAGE_API_KEY = os.getenv(
        'ALPHA_VANTAGE_API_KEY', default='demo')


# Production Configuration
class ProductionConfig(Config):
    FLASK_ENV = 'production'


# Development Configuration
class DevelopmentConfig(Config):
    DEBUG = True


# Testing Configuration
class TestingConfig(Config):
    TESTING = True
