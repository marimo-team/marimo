# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "flask",
#     "marimo",
#     "asgiref",
#     "python-dotenv",
#     "flask-session",
#     "werkzeug",
#     "vega-datasets==0.9.0",
# ]
# ///
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import marimo
import os
import logging
from dotenv import load_dotenv
from functools import wraps
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import RedirectResponse

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ui_dir = os.path.join(os.path.dirname(__file__), "..", "..", "ui")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

app = Flask(__name__, template_folder=templates_dir)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "your-secret-key")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Simulated user database (replace with a real database in production)
users = {"admin": generate_password_hash("password123")}

app_names: list[str] = []
marimo_app = marimo.create_asgi_app()

for filename in sorted(os.listdir(ui_dir)):
    if filename.endswith(".py"):
        app_name = os.path.splitext(filename)[0]
        app_path = os.path.join(ui_dir, filename)
        marimo_app = marimo_app.with_app(path=f"/{app_name}", root=app_path)
        app_names.append(app_name)

# Wrap the Flask app with WSGIMiddleware
wsgi_app = WSGIMiddleware(app)

# Create the final ASGI app
asgi_app = Starlette(routes=[
    Route("/", endpoint=lambda request: RedirectResponse(url="/flask/")),
    Mount("/flask", app=wsgi_app),
    Mount("/", app=marimo_app.build()),
])

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username], password):
            session['username'] = username
            logger.info(f"User {username} logged in successfully")
            return redirect(url_for('home'))
        logger.warning(f"Failed login attempt for user {username}")
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    username: str = session.get('username')
    session.clear()
    logger.info(f"User {username} logged out")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('home.html', username=session['username'], app_names=app_names)

@app.route('/ping')
def ping():
    return {"message": "pong"}

@app.errorhandler(401)
def unauthorized(error: Exception):
    logger.error(f"Unauthorized access: {error}")
    return render_template('error.html', detail="Unauthorized access"), 401

@app.errorhandler(404)
def not_found(error: Exception):
    logger.error(f"Page not found: {error}")
    return render_template('error.html', detail="Page not found"), 404

if __name__ == '__main__':
    import uvicorn
    # print valid routes recursively
    for route in asgi_app.routes:
        print(route)
    uvicorn.run(asgi_app, host="0.0.0.0", port=8000)
