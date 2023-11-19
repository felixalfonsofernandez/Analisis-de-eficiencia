# app.py
from flask import Flask
from models import db_session, init_db  # No necesitamos importar Usuario aquí

app = Flask(__name__)

app.secret_key = 'una_llave_secreta_muy_segura'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Importa las rutas después de crear la instancia de la aplicación
from routes import *

if __name__ == '__main__':
    init_db()  # Inicializa las tablas de la base de datos
    app.run(debug=True)
