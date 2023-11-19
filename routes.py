# routes.py
from datetime import datetime
from flask import render_template, request, redirect, url_for, session
from app import app  # Importa la instancia de la aplicación que creaste
from models import Usuario, db_session, Jefe, Tareas # Importa tus modelos y sesión de db
import tensorflow as tf
from sqlalchemy import case
from sqlalchemy import func, cast, Date, text
from sqlalchemy import literal_column
import joblib
import json
from flask import render_template, jsonify

model = tf.keras.models.load_model('regresion_logistica.h5')
#model25 = joblib.load('modelo_entrenado_regresion_logistica.joblib')

@app.route('/')
def bienvenida():
    return render_template('bienvenida.html')

# ... (otras rutas y funciones de vistas)

@app.route('/inicio', methods=['GET', 'POST'])
def inicio():
    # Verifica si el usuario ya está logueado
    if 'usuario' in session:
        return redirect(url_for('tareas'))

    mensaje_error = ""
    if request.method == 'POST':
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']

        # Consulta la base de datos para verificar las credenciales
        usuario_valido = db_session.query(Usuario).filter_by(Usuario=usuario, Contraseña=contraseña).first()

        if usuario_valido:
            session['usuario'] = usuario  # Almacenas el nombre de usuario en la sesión
            return redirect(url_for('tareas'))
        else:
            mensaje_error = "Usuario o contraseña incorrectos"

    return render_template('inicio.html', mensaje_error=mensaje_error)


@app.route('/inicio/jefe', methods=['GET', 'POST'])
def inicio_jefe():
    mensaje_error = ""
    if request.method == 'POST':
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']

        # Consulta la base de datos para verificar las credenciales
        jefe_valido = db_session.query(Jefe).filter_by(Usuario=usuario, Contraseña=contraseña).first()

        if jefe_valido:
            session['jefe'] = usuario
            return redirect(url_for('creacion_tareas'))
        else:
            mensaje_error = "Usuario o contraseña incorrectos"

    return render_template('jefe.html', mensaje_error=mensaje_error)


@app.route('/creacion', methods=['POST'])
def crear_tarea():
    if request.method == 'POST':
        creador = request.form['creador']
        contenido = request.form['contenido']
        usuario_designado = request.form['usuario_designado']  # Captura el ID del usuario designado
        dificultad = request.form['dificultad']  # Asume que hay un campo 'dificultad' en tu formulario
        fecha_creacion = datetime.strptime(request.form['fecha_creacion'], '%Y-%m-%d')
        cantidad = int(request.form['cantidad'])  # Convierte a entero

        nueva_tarea = Tareas(
            Creador=creador,
            Contenido=contenido,
            Designado=usuario_designado,  # Asigna el ID del usuario designado
            Dificultad=dificultad,  # Asigna la dificultad de la tarea
            creacion=fecha_creacion,
            Realizado=False,
            EnProgreso=False,
            NUMERO_TRABAJADORES=cantidad
        )

        db_session.add(nueva_tarea)
        db_session.commit()

        return redirect(url_for('tareas'))
    return render_template('creacion_tareas.html')  # Asegúrate de manejar esto adecuadamente

@app.route('/tareas')
def tareas():
    if 'usuario' not in session and 'jefe' not in session:
        return redirect(url_for('inicio'))

    usuario_actual = session['usuario']

    usuario_obj = db_session.query(Usuario).filter_by(Usuario=usuario_actual).first()
    if usuario_obj is None:
        return redirect(url_for('logout'))

    usuario_id = usuario_obj.Id

    tareas_no_realizadas = db_session.query(Tareas).filter_by(Realizado=False, EnProgreso=False, Designado=usuario_id).all()
    tareas_en_progreso = db_session.query(Tareas).filter_by(EnProgreso=True, Designado=usuario_id).all()
    tareas_realizadas = db_session.query(Tareas).filter_by(Realizado=True, Designado=usuario_id).all()

    return render_template(
        'tareas.html',
        tareas_no_realizadas=tareas_no_realizadas,
        tareas_en_progreso=tareas_en_progreso,
        tareas_realizadas=tareas_realizadas
    )

@app.route('/creacion_tareas')
def creacion_tareas():
    usuarios = db_session.query(Usuario).all()
    resultados_json = json.dumps([])  # cadena JSON vacía para evitar errores
    print(usuarios)
    return render_template('creacion_tareas.html', usuarios=usuarios, resultados_json=resultados_json)


@app.route('/logout', methods=['POST'])
def logout():
    # Elimina el nombre de usuario de la sesión si está presente
    session.pop('usuario', None)
    # Redirige al usuario a la página de inicio o a la página que desees después del deslogueo
    return redirect(url_for('inicio'))


@app.route('/prediccion', methods=['POST'])
def prediccion():
    dificultad_valores = case([
        (Tareas.Dificultad == 'Bajo', 40),
        (Tareas.Dificultad == 'Medio', 45),
        ], else_=50)

    tareas_pendientes = db_session.query(Tareas, dificultad_valores.label("Dificultad_numerica")).filter(Tareas.Realizado == False).all()

    cantidad_tareas = db_session.query(Tareas).filter(Tareas.EnProgreso == True).count()

    # Cambio en la consulta de duracion_promedio
    stmt = text("SELECT AVG(DATEDIFF(MINUTE, creacion, fecha_termino)) FROM Tareas WHERE Realizado = 1")
    promedio_minutos = db_session.execute(stmt).scalar()

    resultados = []

    for tarea, dificultad_num in tareas_pendientes:
        X = [[0.75, dificultad_num, promedio_minutos, 0, tarea.NUMERO_TRABAJADORES]]

        prediction = model.predict(X)
        resultados.append({
            'Tarea_Id': tarea.Id,
            'Contenido': tarea.Contenido,
            'Prediccion': str(prediction[0][0])
        })

    resultados_json = json.dumps(resultados)

    # Decodificar la cadena JSON a un objeto Python
    resultados_obj = json.loads(resultados_json)

    usuarios = db_session.query(Usuario).all()

    return render_template('creacion_tareas.html', resultados_json=resultados, usuarios=usuarios)


@app.route('/tarea/<int:tarea_id>')
def detalle_tarea(tarea_id):
    # Obtener detalles de la tarea de la base de datos
    tarea = db_session.query(Tareas).filter_by(Id=tarea_id).first()
    if tarea is None:
        # Si no se encuentra la tarea, redirige o muestra un error
        return "Tarea no encontrada", 404
    return render_template('detalle.html', tarea=tarea)


@app.route('/tarea/<int:tarea_id>/detalles')
def detalle_tarea_json(tarea_id):
    # Obtener detalles de la tarea de la base de datos
    tarea = db_session.query(Tareas).filter_by(Id=tarea_id).first()
    if tarea is None:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    # Convierte el objeto de tarea a un diccionario y luego a JSON
    tarea_dict = {
        'Creador': tarea.Creador,
        'Contenido': tarea.Contenido,
        'Estado': 'Realizada' if tarea.Realizado else 'En Progreso' if tarea.EnProgreso else 'No Realizada',
        'Fecha_de_creación': tarea.creacion.strftime('%d/%m/%Y, %H:%M:%S'),
        'Fecha_de_termino': tarea.fecha_termino.strftime('%d/%m/%Y, %H:%M:%S') if tarea.fecha_termino else 'No especificado',
        'Usuario_Designado': tarea.usuario_designado.Nombres if tarea.usuario_designado else 'No asignado',
        'Dificultad': tarea.Dificultad
        # Añade aquí más campos según sea necesario
    }
    return jsonify(tarea_dict)