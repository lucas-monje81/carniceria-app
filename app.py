import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_para_sesiones'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DB_NAME = 'carniceria.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de configuración y datos generales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Tabla de cortes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cortes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            kilos REAL,
            precio_hist REAL,
            precio_mod REAL,
            oferta INTEGER
        )
    ''')

    # Tabla de usuarios para el control de acceso y comercialización
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            nombre_negocio TEXT,
            activo INTEGER DEFAULT 1
        )
    ''')

    # Crear un usuario administrador por defecto si no existe
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (username, password, nombre_negocio, activo) VALUES (?, ?, ?, ?)",
                       ('admin', '1234', 'CARNICERÍA LA ESPERANZA', 1))

    conn.commit()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ? AND activo = 1", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['negocio'] = user[3]
            return redirect(url_for('index'))
        else:
            error = 'Usuario o contraseña incorrectos, o cuenta inactiva.'
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT nombre, kilos, precio_hist, precio_mod, oferta FROM cortes")
    rows = cursor.fetchall()
    cortes = [{'nombre': r[0], 'kilos': r[1], 'precio_hist': r[2], 'precio_mod': r[3], 'oferta': r[4]} for r in rows]
    
    cursor.execute("SELECT key, value FROM config")
    config_rows = cursor.fetchall()
    params = {}
    empresa = {'nombre': session.get('negocio', 'CARNICERÍA LA ESPERANZA'), 'datos': 'Av. San Martín 1234 - Tel: 351-1234567', 'logo': ''}
    
    for k, v in config_rows:
        if k == 'precio_media_res': params['precio_media_res'] = v
        elif k == 'kilos_media_res': params['kilos_media_res'] = v
        elif k == 'margen_deseado': params['margen_deseado'] = v
        elif k == 'cant_semanal': params['cant_semanal'] = v
        elif k == 'empresa_nombre': empresa['nombre'] = v
        elif k == 'empresa_datos': empresa['datos'] = v
        elif k == 'empresa_logo': empresa['logo'] = v
        
    conn.close()
    return jsonify({'cortes': cortes, 'params': params, 'empresa': empresa})

@app.route('/api/save', methods=['POST'])
def save_data():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if 'params' in data:
        p = data['params']
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('precio_media_res', ?)", (p.get('precioMediaRes'),))
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('kilos_media_res', ?)", (p.get('kilosMediaRes'),))
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('margen_deseado', ?)", (p.get('margenDeseadoGen'),))
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('cant_semanal', ?)", (p.get('cantSemanal'),))
        
    if 'empresa' in data:
        e = data['empresa']
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('empresa_nombre', ?)", (e.get('nombre'),))
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('empresa_datos', ?)", (e.get('datos'),))
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('empresa_logo', ?)", (e.get('logo'),))
        
    if 'cortes' in data:
        cursor.execute("DELETE FROM cortes")
        for c in data['cortes']:
            cursor.execute("INSERT INTO cortes (nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, ?, ?, ?, ?)",
                           (c.get('nombre'), c.get('kilos'), c.get('precio_hist'), c.get('precio_mod'), c.get('oferta')))
                           
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/upload-logo', methods=['POST'])
def upload_logo():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    if 'logo' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logo_url = f'/{filepath}'
        return jsonify({'status': 'success', 'logo': logo_url})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
