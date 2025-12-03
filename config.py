import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_URI',
        'mysql+pymysql://root:@localhost/quick_hire_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False