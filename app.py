import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_para_sesiones'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_NAME = 'carniceria.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        nombre_negocio TEXT,
        datos_contacto TEXT,
        logo TEXT,
        precio_media_res TEXT,
        kilos_media_res TEXT,
        margen_deseado TEXT,
        cant_semanal TEXT,
        vencimiento TEXT,
        activo INTEGER DEFAULT 1,
        es_admin INTEGER DEFAULT 0
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cortes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tipo TEXT DEFAULT 'vacuna',
        nombre TEXT,
        kilos REAL,
        precio_hist REAL,
        precio_mod REAL,
        oferta INTEGER
    )
    ''')
    cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
        INSERT INTO usuarios (username, password, nombre_negocio, datos_contacto, logo, precio_media_res, kilos_media_res, margen_deseado, cant_semanal, vencimiento, activo, es_admin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('admin', '1234', 'ADMINISTRADOR GENERAL', 'Av. San Martín 1234 - Tel: 351-1234567', '', '10.000', '92', '40', '16', '2099-12-31', 1, 1))
    else:
        cursor.execute("UPDATE usuarios SET password = '1234', es_admin = 1, activo = 1 WHERE username = 'admin'")
    conn.commit()
    conn.close()

def cargar_cortes_iniciales_si_necesario(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cortes WHERE user_id = ? AND tipo = 'vacuna'", (user_id,))
    if cursor.fetchone()[0] == 0:
        cortes_vacuna = [
            ("MATAMBRE", 1.495, 20000, 0, 0),
            ("PALETA", 3.855, 14500, 22000, 1),
            ("FALDA", 5.020, 7500, 13000, 0),
            ("COSTILLA / ASADO", 7.095, 14000, 23000, 1),
            ("COSTELETA", 7.470, 14000, 20000, 0),
            ("VACIO", 2.445, 14000, 23000, 0),
            ("TAPA DE ASADO", 1.710, 14000, 23000, 0),
            ("PUCHERO ESPECIAL", 5.140, 8500, 11000, 0),
            ("PUCHERO COMUN", 4.325, 6500, 7900, 0),
            ("GRASA", 6.885, 3500, 3500, 0),
            ("MOLIDA ESPECIAL", 5.670, 14500, 22000, 1),
            ("MOLIDA COMUN", 4.725, 7900, 11000, 0),
            ("BLANDO ESPECIAL", 10.035, 16000, 26000, 0),
            ("LOMO", 1.520, 17000, 26000, 0),
            ("CUADRIL", 2.935, 17000, 26000, 0),
            ("PECETO", 1.505, 17000, 26000, 0),
            ("AGUJAS", 8.580, 7500, 13000, 0),
            ("TAPA CUADRIL", 0.920, 16000, 26000, 0)
        ]
        for c in cortes_vacuna:
            cursor.execute("INSERT INTO cortes (user_id, tipo, nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, 'vacuna', ?, ?, ?, ?, ?)", (user_id, c[0], c[1], c[2], c[3], c[4]))

    cursor.execute("SELECT COUNT(*) FROM cortes WHERE user_id = ? AND tipo = 'cerdo'", (user_id,))
    if cursor.fetchone()[0] == 0:
        cortes_cerdo = [
            ("BLANDO DE CERDO", 7.405, 12000, 16000, 1),
            ("BONDIOLA DE CERDO", 2.255, 12000, 16000, 1),
            ("CHORIZO DE CERDO", 8.750, 10000, 13000, 1),
            ("GRASA DE CERDO", 5.030, 4500, 5900, 0),
            ("COSTELETA DE CERDO", 5.705, 8990, 10000, 1),
            ("VACIO DE CERDO", 2.040, 10000, 13000, 1),
            ("COSTILLA DE CERDO", 4.630, 9000, 10000, 1),
            ("MATAMBRE DE CERDO", 1.550, 15900, 18000, 1)
        ]
        for c in cortes_cerdo:
            cursor.execute("INSERT INTO cortes (user_id, tipo, nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, 'cerdo', ?, ?, ?, ?, ?)", (user_id, c[0], c[1], c[2], c[3], c[4]))
    conn.commit()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, nombre_negocio, vencimiento, activo, es_admin FROM usuarios WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            user_id, uname, negocio, vencimiento, activo, es_admin = user
            if activo == 0:
                error = 'Su cuenta se encuentra desactivada.'
            else:
                session['user_id'] = user_id
                session['username'] = uname
                session['es_admin'] = es_admin
                cargar_cortes_iniciales_si_necesario(user_id)
                return redirect(url_for('index'))
        else:
            error = 'Usuario o contraseña incorrectos.'
    return render_template('login.html', error=error)

@app.route('/admin/licencias')
def admin_licencias():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nombre_negocio, vencimiento, activo FROM usuarios WHERE es_admin = 0")
    clientes = cursor.fetchall()
    conn.close()
    return render_template('admin_licencias.html', clientes=clientes)

@app.route('/admin/crear-cliente', methods=['POST'])
def crear_cliente():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    username = request.form.get('username') or request.form.get('usuario')
    password = request.form.get('password')
    negocio = request.form.get('negocio') or request.form.get('nombre_negocio')
    vencimiento = request.form.get('vencimiento') or '2026-12-31'
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO usuarios (username, password, nombre_negocio, datos_contacto, logo, precio_media_res, kilos_media_res, margen_deseado, cant_semanal, vencimiento, activo, es_admin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """, (username, password, negocio, 'Av. San Martín 1234', '', '10.000', '92', '40', '16', vencimiento))
        conn.commit()
    except Exception as e:
        print("Error al crear cliente:", e)
    conn.close()
    return redirect(url_for('admin_licencias'))

@app.route('/admin/toggle/<int:id>')
def toggle_cliente(id):
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_licencias'))

@app.route('/admin/eliminar/<int:id>')
def eliminar_cliente(id):
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cortes WHERE user_id = ?", (id,))
    cursor.execute("DELETE FROM usuarios WHERE id = ? AND es_admin = 0", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_licencias'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', es_admin=session.get('es_admin', 0), active_page='vacuna_precios')

@app.route('/desposte')
def desposte():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('desposte.html', es_admin=session.get('es_admin', 0), active_page='vacuna_desposte')

@app.route('/cerdo')
def cerdo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('cerdo.html', es_admin=session.get('es_admin', 0), active_page='cerdo_precios')

@app.route('/cerdo/desposte')
def cerdo_desposte():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('cerdo_desposte.html', es_admin=session.get('es_admin', 0), active_page='cerdo_desposte')

@app.route('/empresa')
def empresa():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('empresa.html', es_admin=session.get('es_admin', 0), active_page='empresa')

@app.route('/api/data', methods=['GET'])
def get_data():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    user_id = session['user_id']
    tipo = request.args.get('tipo', 'vacuna')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_negocio, datos_contacto, logo, precio_media_res, kilos_media_res, margen_deseado, cant_semanal FROM usuarios WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    params = {}
    empresa = {'nombre': 'CARNICERÍA', 'datos': '', 'logo': ''}
    if user_row:
        empresa = {
            'nombre': user_row[0] or 'CARNICERÍA',
            'datos': user_row[1] or '',
            'logo': user_row[2] or ''
        }
        params = {
            'precio_media_res': user_row[3] or '10.000',
            'kilos_media_res': user_row[4] or '92',
            'margen_deseado': user_row[5] or '40',
