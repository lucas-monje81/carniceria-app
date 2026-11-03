from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

DB_NAME = 'carniceria.db'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cortes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            kilos REAL,
            precio_hist REAL,
            precio_mod REAL,
            oferta INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parametros (
            id INTEGER PRIMARY KEY,
            precio_media_res TEXT,
            kilos_media_res TEXT,
            margen_deseado TEXT,
            cant_semanal TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresa (
            id INTEGER PRIMARY KEY,
            nombre TEXT,
            datos TEXT,
            logo TEXT
        )
    ''')
    
    cursor.execute("PRAGMA table_info(empresa)")
    columnas = [col[1] for col in cursor.fetchall()]
    if 'logo' not in columnas:
        cursor.execute("ALTER TABLE empresa ADD COLUMN logo TEXT")
    
    cursor.execute('SELECT COUNT(*) FROM cortes')
    if cursor.fetchone()[0] == 0:
        cortes_default = [
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
        cursor.executemany('INSERT INTO cortes (nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, ?, ?, ?, ?)', cortes_default)
        cursor.execute('INSERT OR REPLACE INTO parametros (id, precio_media_res, kilos_media_res, margen_deseado, cant_semanal) VALUES (1, "10.000", "92", "40", "16")', ())
        cursor.execute('INSERT OR REPLACE INTO empresa (id, nombre, datos, logo) VALUES (1, "CARNICERÍA LA ESPERANZA", "Av. San Martín 1234 - Tel: 351-1234567", "")', ())
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM cortes')
    cortes = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT * FROM parametros WHERE id = 1')
    params_row = cursor.fetchone()
    params = dict(params_row) if params_row else {}
    
    cursor.execute('SELECT * FROM empresa WHERE id = 1')
    emp_row = cursor.fetchone()
    empresa = dict(emp_row) if emp_row else {}
    
    conn.close()
    return jsonify({'cortes': cortes, 'params': params, 'empresa': empresa})

@app.route('/api/save', methods=['POST'])
def save_data():
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if 'params' in data:
        p = data['params']
        cursor.execute('INSERT OR REPLACE INTO parametros (id, precio_media_res, kilos_media_res, margen_deseado, cant_semanal) VALUES (1, ?, ?, ?, ?)',
                       (p.get('precioMediaRes'), p.get('kilosMediaRes'), p.get('margenDeseadoGen'), p.get('cantSemanal')))
    
    if 'empresa' in data:
        e = data['empresa']
        cursor.execute('UPDATE empresa SET nombre = ?, datos = ?, logo = ? WHERE id = 1',
                       (e.get('nombre'), e.get('datos'), e.get('logo')))
                       
    if 'cortes' in data and len(data['cortes']) > 0:
        cursor.execute('DELETE FROM cortes')
        for c in data['cortes']:
            cursor.execute('INSERT INTO cortes (nombre, kilos, precio_hist, precio_mod, oferta) VALUES (?, ?, ?, ?, ?)',
                           (c.get('nombre'), c.get('kilos'), c.get('precio_hist'), c.get('precio_mod'), 1 if c.get('oferta') else 0))
                           
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/upload-logo', methods=['POST'])
def upload_logo():
    if 'logo' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        db_path = f'/static/uploads/{filename}'
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE empresa SET logo = ? WHERE id = 1', (db_path,))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'logo': db_path})
    return jsonify({'error': 'Invalid file'}), 400

import os

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)