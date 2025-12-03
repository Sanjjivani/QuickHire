from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_login import LoginManager
import eventlet

# Initialize extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()
socketio = SocketIO(async_mode='eventlet', cors_allowed_origins="*", logger=True, engineio_logger=True)
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    
    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # Import and initialize routes
    from app import routes
    routes.init_app(app)
    
    return app

# Create app instance
app = create_app()