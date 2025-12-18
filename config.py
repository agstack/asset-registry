import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    USER_REGISTRY_BASE_URL = os.getenv('USER_REGISTRY_BASE_URL')
    DATABASE_URL_FOR_REGION = os.getenv('DATABASE_URL_FOR_REGION')
    MAP_HTML_BASE_URL = os.getenv('MAP_HTML_BASE_URL')

class ProductionConfig(Config):
    DEBUG = False


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
