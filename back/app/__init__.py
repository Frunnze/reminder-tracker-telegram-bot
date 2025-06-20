from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_cors import CORS


load_dotenv()
db = SQLAlchemy()

def create_app():
    # Create and configure the flask app
    app = Flask(__name__)

    # Define the cross origin resource sharing
    CORS(app)

    # scraped real-estate data
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tracker.db"
    db.init_app(app)

    # Register the apis
    from .apis.stats import stats
    app.register_blueprint(stats)

    # Create the dbs and add initial tables values
    from .models import TrackedTime
    with app.app_context():
        db.create_all()

    return app