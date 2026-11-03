import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import libsql_client
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_para_sesiones'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

TURSO_URL = os.environ.get("TURSO_URL", "libsql://carniceria-db-lucas-monje81.aws-sa-east-1.turso.io")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "zhv7i_djdHQGps4KMhzjeo6T1kC0E_6jNlesf_pXL9_yJEYFCYwrJvRqWBw")

def get_db_connection():
    return libsql_client.connect(
        url=TURSO_URL,
        auth_token=TURSO_AUTH_TOKEN
    )

def init_db():
    conn = get_db_connection()
    
    # Configuración ahora con user_id para independencia total
    conn.execute('''
        CREATE TABLE IF NOT EXISTS config (
            user_id INTEGER,
            key TEXT,
            value TEXT,
            PRIMARY KEY (user_id, key)
        )
    ''')
    
    # Cortes asociados a cada usuario
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cortes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nombre TEXT,
            kilos REAL,
            precio_hist REAL,
            precio_mod REAL,
            oferta INTEGER
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            nombre_negocio TEXT,
            vencimiento TEXT,
            activo INTEGER DEFAULT 1,
            es_admin INTEGER DEFAULT 0
        )
    ''')

    # Crear administrador por defecto si no existe (user_id = 1)
    res = conn.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'admin'")
    if res.rows[0][0] == 0:
        conn.execute("INSERT INTO usuarios (username, password, nombre_negocio, vencimiento, activo, es_admin) VALUES (?, ?, ?, ?, ?, ?)",
                     ('admin', '1234', 'ADMINISTRADOR GENERAL', '2099-12-31', 1, 1))

    conn.close()

def cargar_cortes_iniciales_si_necesario(user_id):
    conn = get_db_connection()
    res = conn.execute("SELECT COUNT(*) FROM cortes WHERE user_id = ?", [user_id])
    if res.rows[0][0] == 0:
        cortes_iniciales = [
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
        for c in cortes_iniciales:
            conn.execute("INSERT INTO cortes (user_id, nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, ?, ?, ?, ?, ?)", 
                         [user_id, c[0], c[1], c[2], c[3], c[4]])
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        res = conn.execute("SELECT id, username, nombre_negocio, vencimiento, activo, es_admin FROM usuarios WHERE username = ? AND password = ?", [username, password])
        user = res.rows[0] if res.rows else None
        conn.close()
        
        if user:
            user_id, uname, negocio, vencimiento, activo, es_admin = user
            
            if activo == 0:
                error = 'Su cuenta se encuentra desactivada. Comuníquese con soporte.'
            elif not es_admin and vencimiento:
                hoy = datetime.now().strftime('%Y-%m-%d')
                if hoy > vencimiento:
                    error = f'Su licencia venció el {vencimiento}. Renueve su suscripción.'
                else:
                    session['user_id'] = user_id
                    session['username'] = uname
                    session['negocio'] = negocio
                    session['es_admin'] = es_admin
                    cargar_cortes_iniciales_si_necesario(user_id)
                    return redirect(url_for('index'))
            else:
                session['user_id'] = user_id
                session['username'] = uname
                session['negocio'] = negocio
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
    res = conn.execute("SELECT id, username, nombre_negocio, vencimiento, activo FROM usuarios WHERE es_admin = 0")
    clientes = res.rows
    conn.close()
    
    return render_template('admin_licencias.html', clientes=clientes)

@app.route('/admin/crear-cliente', methods=['POST'])
def crear_cliente():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
        
    username = request.form['username']
    password = request.form['password']
    negocio = request.form['negocio']
    vencimiento = request.form['vencimiento']
    
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO usuarios (username, password, nombre_negocio, vencimiento, activo, es_admin) VALUES (?, ?, ?, ?, 1, 0)",
                     [username, password, negocio, vencimiento])
    except Exception as e:
        print("Error al crear cliente:", e)
    conn.close()
    
    return redirect(url_for('admin_licencias'))

@app.route('/admin/toggle/<int:id>')
def toggle_cliente(id):
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END WHERE id = ?", [id])
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
    return render_template('index.html', es_admin=session.get('es_admin', 0))

@app.route('/api/data', methods=['GET'])
def get_data():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    user_id = session['user_id']
    conn = get_db_connection()
    
    res_cortes = conn.execute("SELECT nombre, kilos, precio_hist, precio_mod, oferta FROM cortes WHERE user_id = ?", [user_id])
    cortes = [{'nombre': r[0], 'kilos': r[1], 'precio_hist': r[2], 'precio_mod': r[3], 'oferta': r[4]} for r in res_cortes.rows]
    
    res_config = conn.execute("SELECT key, value FROM config WHERE user_id = ?", [user_id])
    params = {}
    empresa = {'nombre': session.get('negocio', 'CARNICERÍA'), 'datos': 'Av. San Martín 1234 - Tel: 351-1234567', 'logo': ''}
    
    for r in res_config.rows:
        k, v = r[0], r[1]
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
        
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    
    if 'params' in data:
        p = data['params']
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'precio_media_res', ?)", [user_id, p.get('precioMediaRes')])
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'kilos_media_res', ?)", [user_id, p.get('kilosMediaRes')])
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'margen_deseado', ?)", [user_id, p.get('margenDeseadoGen')])
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'cant_semanal', ?)", [user_id, p.get('cantSemanal')])
        
    if 'empresa' in data:
        e = data['empresa']
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'empresa_nombre', ?)", [user_id, e.get('nombre')])
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'empresa_datos', ?)", [user_id, e.get('datos')])
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'empresa_logo', ?)", [user_id, e.get('logo')])
        
    if 'cortes' in data:
        conn.execute("DELETE FROM cortes WHERE user_id = ?", [user_id])
        for c in data['cortes']:
            conn.execute("INSERT INTO cortes (user_id, nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, ?, ?, ?, ?, ?)",
                         [user_id, c.get('nombre'), c.get('kilos'), c.get('precio_hist'), c.get('precio_mod'), c.get('oferta')])
                           
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/upload-logo', methods=['POST'])
def upload_logo():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    user_id = session['user_id']
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
        
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO config (user_id, key, value) VALUES (?, 'empresa_logo', ?)", [user_id, logo_url])
        conn.close()

        return jsonify({'status': 'success', 'logo': logo_url})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
