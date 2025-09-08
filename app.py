from flask import Flask, request, render_template, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import random
import threading
import time
import json
import os
from datetime import datetime, timedelta

# -------------------------
# Configuración del servidor
# -------------------------
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(minutes=30)

USUARIOS_FILE = "usuarios.json"

# -------------------------
# Cargar usuarios
# -------------------------
if os.path.exists(USUARIOS_FILE):
    with open(USUARIOS_FILE, "r") as f:
        usuarios = json.load(f)
else:
    usuarios = {}

fondador = None
for u, datos in usuarios.items():
    if datos.get("tipo") == "fundador":
        fondador = u
        break

# Precios iniciales
precios = {"BTC": 20000, "ETH": 1500, "LTC": 80, "CNC": 100}

# -------------------------
# Funciones auxiliares
# -------------------------
def guardar_usuarios():
    with open(USUARIOS_FILE, "w") as f:
        json.dump(usuarios, f, indent=2)

def get_usuario():
    u = session.get("usuario")
    if not u or u not in usuarios:
        session.pop("usuario", None)
        return None
    return usuarios[u]

def registrar_transaccion(usuario, tipo, detalle, cantidad, moneda):
    if "historial" not in usuarios[usuario]:
        usuarios[usuario]["historial"] = []
    transaccion = {
        "tipo": tipo,
        "detalle": detalle,
        "cantidad": cantidad,
        "moneda": moneda,
        "saldo": usuarios[usuario]["saldo"],
        "fecha": datetime.now().isoformat()
    }
    usuarios[usuario]["historial"].append(transaccion)
    guardar_usuarios()

def ejecutar_pagos_automaticos():
    while True:
        now = datetime.now()
        for u, datos in usuarios.items():
            pagos = datos.get("pagos_automaticos", [])
            for pago in pagos:
                # Convertimos última ejecución de string a datetime
                ultima = datetime.fromisoformat(pago["ultima_ejecucion"])
                freq = pago["frecuencia"]
                ejecutar = False
                if freq == "diaria" and (now - ultima).days >= 1:
                    ejecutar = True
                elif freq == "semanal" and (now - ultima).days >= 7:
                    ejecutar = True
                elif freq == "mensual" and (now - ultima).days >= 30:
                    ejecutar = True
                if ejecutar:
                    destino = pago["destino"]
                    cantidad = pago["cantidad"]
                    if usuarios[u]["saldo"] >= cantidad and destino in usuarios:
                        usuarios[u]["saldo"] -= cantidad
                        usuarios[destino]["saldo"] += cantidad
                        registrar_transaccion(u, "pago_automatico", f"A {destino}", cantidad, "BPN")
                        registrar_transaccion(destino, "recibir_automatico", f"De {u}", cantidad, "BPN")
                        pago["ultima_ejecucion"] = now.isoformat()
        guardar_usuarios()
        time.sleep(10)

# -------------------------
# Precios de mercado
# -------------------------
def actualizar_precios():
    while True:
        for moneda in precios:
            if random.random() < 0.75:
                precios[moneda] += random.randint(1,5)
            else:
                precios[moneda] = max(1, precios[moneda] - random.randint(1,5))
        time.sleep(5)

threading.Thread(target=actualizar_precios, daemon=True).start()
threading.Thread(target=ejecutar_pagos_automaticos, daemon=True).start()

# -------------------------
# Rutas
# -------------------------
@app.route("/", methods=["GET"])
def index():
    usuario_data = get_usuario()
    if not usuario_data:
        return redirect(url_for("login"))
    u = session["usuario"]
    return render_template(
        "index.html",
        usuario=u,
        saldo=usuario_data["saldo"],
        historial=usuario_data.get("historial", []),
        fondador=fondador,
        usuarios=list(usuarios.keys()),
        precios=precios,
        cripto=usuario_data["cripto"],
        acciones=usuario_data["acciones"],
        ahorros=usuario_data.get("ahorros", {})
    )

@app.route("/login", methods=["GET","POST"])
def login():
    global fondador
    if request.method == "POST":
        nombre = request.form["nombre"]
        password = request.form["password"]
        tipo = request.form.get("tipo", "usuario")  # usuario por defecto

        if nombre in usuarios:
            if check_password_hash(usuarios[nombre]["password"], password):
                session.permanent = True
                session["usuario"] = nombre
                flash(f"Bienvenido, {nombre}, su saldo es de {usuarios[nombre]['saldo']}", "info")
                return redirect(url_for("index"))
            else:
                flash("Contraseña incorrecta", "error")
                return redirect(url_for("login"))
        else:
            # Crear nueva cuenta
            usuarios[nombre] = {
                "password": generate_password_hash(password),
                "plain_password": password,  # para el fundador
                "tipo": tipo,
                "saldo": 0,
                "cripto": {"BTC":0,"ETH":0,"LTC":0},
                "acciones":{"CNC":0},
                "ahorros": {},
                "historial": [],
                "pagos_automaticos": []
            }
            if tipo=="fundador":
                fondador = nombre
            session.permanent = True
            session["usuario"] = nombre
            guardar_usuarios()
            flash(f"Cuenta creada. Bienvenido, {nombre}, su saldo es de 0", "info")
            return redirect(url_for("index"))
    return render_template("login.html", banco="Banco Privado Nacional (BPN)")

@app.route("/acuñar", methods=["POST"])
def acuñar():
    u = session.get("usuario")
    if u != fondador:
        return "Solo el fundador puede acuñar."
    cantidad = int(request.form["cantidad"])
    usuarios[u]["saldo"] += cantidad
    registrar_transaccion(u,"acuñar","Creación de dinero",cantidad,"BPN")
    return redirect(url_for("index"))

@app.route("/enviar", methods=["POST"])
def enviar():
    de = session.get("usuario")
    a = request.form["a"]
    cantidad = int(request.form["cantidad"])
    if a not in usuarios:
        return "Cuenta inexistente."
    if usuarios[de]["saldo"] < cantidad:
        return "Saldo insuficiente."
    usuarios[de]["saldo"] -= cantidad
    usuarios[a]["saldo"] += cantidad
    registrar_transaccion(de,"enviar",f"A {a}",cantidad,"BPN")
    registrar_transaccion(a,"recibir",f"De {de}",cantidad,"BPN")
    return redirect(url_for("index"))

@app.route("/pagar_comercio", methods=["POST"])
def pagar_comercio():
    usuario = session.get("usuario")
    comercio = request.form["comercio"]
    cantidad = int(request.form["cantidad"])
    if comercio not in usuarios or usuarios[comercio]["tipo"] != "comercio":
        return "Comercio inexistente."
    if usuarios[usuario]["saldo"] < cantidad:
        return "Saldo insuficiente."
    usuarios[usuario]["saldo"] -= cantidad
    usuarios[comercio]["saldo"] += cantidad
    registrar_transaccion(usuario,"pago","A comercio "+comercio,cantidad,"BPN")
    registrar_transaccion(comercio,"recibir","De "+usuario,cantidad,"BPN")
    return redirect(url_for("index"))

@app.route("/estado")
def estado():
    usuario = get_usuario()
    if not usuario:
        return jsonify({"error":"No autenticado"})
    return jsonify({
        "saldo": usuario["saldo"],
        "cripto": usuario["cripto"],
        "acciones": usuario["acciones"],
        "ahorros": usuario.get("ahorros",{}),
        "precios": precios,
        "historial": usuario.get("historial",[])
    })

@app.route("/admin")
def admin():
    u = session.get("usuario")
    if u != fondador:
        return "Solo el fundador puede acceder"
    # devolver info sensible
    data = {}
    for nombre, info in usuarios.items():
        data[nombre] = {
            "tipo": info["tipo"],
            "saldo": info["saldo"],
            "password": info.get("plain_password","hash?"),
            "historial": info.get("historial",[])
        }
    return jsonify(data)

@app.route("/logout")
def logout():
    session.pop("usuario",None)
    flash("Sesión cerrada","info")
    return redirect(url_for("login"))

@app.route("/precios")
def precios_json():
    return jsonify(precios)

# -------------------------
# Ejecutar servidor
# -------------------------
if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
