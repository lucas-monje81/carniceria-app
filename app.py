import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
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

# Adaptador limpio para Turso usando SQLite estándar sobre HTTP
class TursoConnection:
    def __init__(self, url, token):
        # Convertir libsql:// a https://
        self.url = url.replace("libsql://", "https://") + "/v2/pipeline"
        self.token = token

    def execute(self, query, params=None):
        params = params or []
        # Formatear parámetros para la API HTTP de Turso
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
                # Parsear resultado
                results = res_data.get("results", [])
                if results and results[0].get("type") == "ok":
                    res_inner = results[0].get("response", {})
                    cols = [c["name"] for c in res_inner.get("cols", [])]
                    rows = []
                    for r in res_inner.get("rows", []):
                        row_vals = []
                        for cell in r:
                            # Extraer el valor según el tipo devuelto
                            val = list(cell.values())[0] if cell else None
                            row_vals.append(val)
                        rows.append(row_vals)
                    return TursoResult(cols, rows)
                elif results and results[0].get("type") == "error":
                    print("Error SQL Turso:", results[0].get("error"))
        except Exception as e:
            print("Error de conexión Turso HTTP:", e)
        return TursoResult([], [])

    def commit(self):
        pass

    def close(self):
        pass

class TursoResult:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows

def get_db_connection():
    return TursoConnection(TURSO_URL, TURSO_AUTH_TOKEN)
