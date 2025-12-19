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
    TERRAPIPE_BE_DB_URL=os.getenv('TERRAPIPE_BE_DB_URL')
    TERRAPIPE_LOGIN_URL=os.getenv('TERRAPIPE_LOGIN_URL')
    TERRAPIPE_SIGNUP_URL=os.getenv('TERRAPIPE_SIGNUP_URL')
    FIELD_MAP_HTML_BASE_URL=os.getenv('FIELD_MAP_HTML_BASE_URL')
    TWILIO_SID = os.getenv('TWILIO_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE = os.getenv('TWILIO_PHONE')

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
