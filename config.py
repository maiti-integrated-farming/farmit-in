import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv(os.path.join(basedir, '.env'))


def _fix_db_url(url):
    """Force psycopg2 driver by replacing postgresql:// with postgresql+psycopg2://.
    SQLAlchemy 2.x defaults to psycopg (v3) for bare postgresql:// URLs,
    but we only have psycopg2-binary installed."""
    if url and url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    return url


class Config:
    """Base configuration with common settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'farmit-super-secret-key-change-in-production-2024'

    # Primary Database (Neon DB for active data, SQLite fallback for dev)
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get('NEON_DATABASE_URL') or os.environ.get('DATABASE_URL')
    ) or 'sqlite:///' + os.path.join(basedir, 'farmit.db')

    # Archive Database (Supabase for historical data 1+ years old)
    ARCHIVE_DATABASE_URI = _fix_db_url(os.environ.get('SUPABASE_DATABASE_URL'))
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
    SUPABASE_URL = os.environ.get('SUPABASE_URL')

    # Database Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # Data Lifecycle Management
    DATA_ARCHIVAL_ENABLED = os.environ.get('DATA_ARCHIVAL_ENABLED', 'true').lower() == 'true'
    ARCHIVAL_AGE_YEARS = int(os.environ.get('ARCHIVAL_AGE_YEARS', 1))
    ARCHIVAL_COMPRESSION = os.environ.get('ARCHIVAL_COMPRESSION', 'gzip')

    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    # Use SimpleCache locally; switch to 'redis' when REDIS_URL is explicitly set
    CACHE_TYPE = 'redis' if os.environ.get('REDIS_URL') else 'SimpleCache'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = 300

    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

    # Upload Configuration
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@farmit.com')

    # API Configuration
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '100 per hour')
    API_KEY_HEADER = 'X-API-Key'

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(basedir, 'logs', 'farmit.log')

    # Monitoring
    SENTRY_DSN = os.environ.get('SENTRY_DSN')

    # Feature Flags
    ENABLE_API = os.environ.get('ENABLE_API', 'true').lower() == 'true'
    ENABLE_WEBHOOKS = os.environ.get('ENABLE_WEBHOOKS', 'false').lower() == 'true'
    ENABLE_TWO_FACTOR = os.environ.get('ENABLE_TWO_FACTOR', 'false').lower() == 'true'


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False

    # Neon DB if provided, otherwise SQLite
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get('NEON_DATABASE_URL') or os.environ.get('DATABASE_URL')
    ) or 'sqlite:///' + os.path.join(basedir, 'farmit_dev.db')

    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = os.environ.get('SQL_ECHO', 'false').lower() == 'true'
    DATA_ARCHIVAL_ENABLED = False
    # SQLite doesn't support pool_size / max_overflow
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    DATA_ARCHIVAL_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False

    SQLALCHEMY_DATABASE_URI = _fix_db_url(os.environ.get('NEON_DATABASE_URL')) \
        or 'sqlite:///' + os.path.join(basedir, 'farmit.db')

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')

    @classmethod
    def validate(cls):
        """Call at production startup to assert required env vars are set."""
        if not os.environ.get('NEON_DATABASE_URL'):
            raise ValueError('NEON_DATABASE_URL is required in production')
        if not os.environ.get('SUPABASE_DATABASE_URL'):
            raise ValueError('SUPABASE_DATABASE_URL is required in production')
        if os.environ.get('SECRET_KEY') == 'farmit-super-secret-key-change-in-production-2024':
            raise ValueError('Set a strong SECRET_KEY in production')


class StagingConfig(ProductionConfig):
    """Staging configuration — production-like but with INFO logging."""
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get('NEON_DATABASE_URL') or os.environ.get('DATABASE_URL')
    ) or 'sqlite:///' + os.path.join(basedir, 'farmit_staging.db')
    LOG_LEVEL = 'INFO'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
