import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import urllib.request
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_para_sesiones'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

TURSO_URL = os.environ.get("TURSO_URL", "libsql://carniceria-db-lucas-monje81.aws-sa-east-1.turso.io")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "zhv7i_djdHQGps4KMhzjeo6T1kC0E_6jNlesf_pXL9_yJEYFCYwrJvRqWBw")

# Conector HTTP optimizado para Turso
class TursoConnection:
    def __init__(self, url, token):
        self.url = url.replace("libsql://", "https://") + "/v2/pipeline"
        self.token = token

    def execute(self, query, params=None):
        params = params or []
        stmt_params = []
        for p in params:
            if isinstance(p, int):
                stmt_params.append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                stmt_params.append({"type": "float", "value": str(p)})
            else:
                stmt_params.append({"type": "text", "value": str(p) if p is not None else ""})

        body = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": query,
                        "args": stmt_params
                    }
                },
                {
                    "type": "close"
                }
            ]
        }
        
        req = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                results = res_data.get("results", [])
                if results and results[0].get("type") == "ok":
                    res_inner = results[0].get("response", {})
                    rows = []
                    for r in res_inner.get("rows", []):
                        row_vals = []
                        for cell in r:
                            val = None
                            if isinstance(cell, dict):
                                val_str = cell.get("value")
                                v_type = cell.get("type", "").lower()
                                if val_str is None:
                                    val_str = list(cell.values())[0] if cell else None
                                    v_type = "text"
                                
                                if v_type in ("integer", "int"):
                                    val = int(val_str) if val_str is not None and val_str != "" else 0
                                elif v_type in ("float", "real"):
                                    val = float(val_str) if val_str is not None and val_str != "" else 0.0
                                else:
                                    val = val_str
                            else:
                                val = cell
                            row_vals.append(val)
                        rows.append(row_vals)
                    return TursoResult(rows)
                elif results and results[0].get("type") == "error":
                    print("Error SQL Turso:", results[0].get("error"))
        except Exception as e:
            print("Error de conexión Turso HTTP:", e)
        return TursoResult([])

    def commit(self):
        pass

    def close(self):
        pass

class TursoResult:
    def __init__(self, rows):
        self.rows = rows

def get_db_connection():
    return TursoConnection(TURSO_URL, TURSO_AUTH_TOKEN)

def init_db():
    conn = get_db_connection()
    
    conn.execute('''
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

    res = conn.execute("SELECT id FROM usuarios WHERE username = 'admin'")
    if not res.rows:
        conn.execute("""
            INSERT INTO usuarios (username, password, nombre_negocio, datos_contacto, logo, precio_media_res, kilos_media_res, margen_deseado, cant_semanal, vencimiento, activo, es_admin) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('admin', '1234', 'ADMINISTRADOR GENERAL', 'Av. San Martín 1234 - Tel: 351-1234567', '', '10.000', '92', '40', '16', '2099-12-31', 1, 1))

    conn.close()

def cargar_cortes_iniciales_si_necesario(user_id):
    conn = get_db_connection()
    res = conn.execute("SELECT COUNT(*) FROM cortes WHERE user_id = ?", [user_id])
    if res.rows and res.rows[0][0] == 0:
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
        
        if username == 'admin' and password == '1234':
            session['user_id'] = 1
            session['username'] = 'admin'
            session['es_admin'] = 1
            cargar_cortes_iniciales_si_necesario(1)
            return redirect(url_for('index'))
        
        conn = get_db_connection()
        res = conn.execute("SELECT id, username, nombre_negocio, vencimiento, activo, es_admin FROM usuarios WHERE username = ? AND password = ?", [username, password])
        user = res.rows[0] if res.rows else None
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
    res = conn.execute("SELECT id, username, nombre_negocio, vencimiento, activo FROM usuarios WHERE es_admin = 0")
    clientes = res.rows if res.rows else []
    conn.close()
    
    return render_template('admin_licencias.html', clientes=clientes)

@app.route('/admin/crear-cliente', methods=['POST'])
def crear_cliente():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
        
    username = request.form.get('username')
    password = request.form.get('password')
    negocio = request.form.get('negocio')
    vencimiento = request.form.get('vencimiento')
    
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO usuarios (username, password, nombre_negocio, datos_contacto, logo, precio_media_res, kilos_media_res, margen_deseado, cant_semanal, vencimiento, activo, es_admin) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """, [username, password, negocio, 'Av. San Martín 1234', '', '10.000', '92', '40', '16', vencimiento])
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
    
    res_user = conn.execute("SELECT nombre_negocio, datos_contacto, logo, precio_media_res, kilos_media_res, margen_deseado, cant_semanal FROM usuarios WHERE id = ?", [user_id])
    user_row = res_user.rows[0] if res_user.rows else None
    
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
            'cant_semanal': user_row[6] or '16'
        }

    res_cortes = conn.execute("SELECT nombre, kilos, precio_hist, precio_mod, oferta FROM cortes WHERE user_id = ?", [user_id])
    cortes = [{'nombre': r[0], 'kilos': r[1], 'precio_hist': r[2], 'precio_mod': r[3], 'oferta': r[4]} for r in res_cortes.rows] if res_cortes.rows else []
    
    conn.close()
    return jsonify({'cortes': cortes, 'params': params, 'empresa': empresa})

@app.route('/api/save', methods=['POST'])
def save_data():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    user_id = session['user_id']
    data = request.json or {}
    conn = get_db_connection()
    
    if 'params' in data:
        p = data['params']
        conn.execute("""
            UPDATE usuarios SET precio_media_res = ?, kilos_media_res = ?, margen_deseado = ?, cant_semanal = ? WHERE id = ?
        """, [str(p.get('precioMediaRes', '10.000')), str(p.get('kilosMediaRes', '92')), str(p.get('margenDeseadoGen', '40')), str(p.get('cantSemanal', '16')), user_id])
        
    if 'empresa' in data:
        e = data['empresa']
        conn.execute("""
            UPDATE usuarios SET nombre_negocio = ?, datos_contacto = ?, logo = ? WHERE id = ?
        """, [str(e.get('nombre', '')), str(e.get('datos', '')), str(e.get('logo', '')), user_id])
        
    if 'cortes' in data:
        conn.execute("DELETE FROM cortes WHERE user_id = ?", [user_id])
        for c in data['cortes']:
            conn.execute("INSERT INTO cortes (user_id, nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, ?, ?, ?, ?, ?)",
                         [user_id, str(c.get('nombre', '')), float(c.get('kilos', 0)), float(c.get('precio_hist', 0)), float(c.get('precio_mod', 0)), int(c.get('oferta', 0))])
                           
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
        conn.execute("UPDATE usuarios SET logo = ? WHERE id = ?", [logo_url, user_id])
        conn.close()

        return jsonify({'status': 'success', 'logo': logo_url})

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
