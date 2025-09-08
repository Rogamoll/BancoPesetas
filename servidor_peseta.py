from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import random
import threading
import time
import json
import os

app = Flask(__name__)
app.secret_key = "una_clave_super_secreta"

USUARIOS_FILE = "usuarios.json"

# Cargar usuarios si existe
if os.path.exists(USUARIOS_FILE):
    with open(USUARIOS_FILE, "r") as f:
        usuarios = json.load(f)
else:
    usuarios = {}

fondador = None
if usuarios:
    fondador = list(usuarios.keys())[0]

# Precios iniciales
precios = {
    "BTC": 20000,
    "ETH": 1500,
    "LTC": 80,
    "CNC": 100
}

# Función para guardar usuarios en archivo
def guardar_usuarios():
    with open(USUARIOS_FILE, "w") as f:
        json.dump(usuarios, f)

# Función para simular cambios de precios
def actualizar_precios():
    while True:
        for moneda in precios:
            cambio = random.randint(-5, 5)
            precios[moneda] = max(1, precios[moneda] + cambio)
        time.sleep(5)

hilo_precios = threading.Thread(target=actualizar_precios, daemon=True)
hilo_precios.start()

@app.route("/", methods=["GET"])
def index():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario_actual = session["usuario"]
    if usuario_actual not in usuarios:
        session.pop("usuario")
        return redirect(url_for("login"))
    saldo = usuarios[usuario_actual]["saldo"]
    return render_template(
        "index.html",
        usuario=usuario_actual,
        saldo=saldo,
        fondador=fondador,
        usuarios=list(usuarios.keys()),
        precios=precios,
        cripto=usuarios[usuario_actual]["cripto"],
        acciones=usuarios[usuario_actual]["acciones"]
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    global fondador
    if request.method == "POST":
        nombre = request.form["nombre"]
        password = request.form["password"]
        if nombre in usuarios:
            if usuarios[nombre]["password"] == password:
                session["usuario"] = nombre
                return redirect(url_for("index"))
            else:
                return "Contraseña incorrecta."
        else:
            # Crear nueva cuenta
            usuarios[nombre] = {
                "password": password,
                "saldo": 0,
                "cripto": {"BTC":0,"ETH":0,"LTC":0},
                "acciones": {"CNC":0}
            }
            if not fondador:
                fondador = nombre
            session["usuario"] = nombre
            guardar_usuarios()
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/acuñar", methods=["POST"])
def acuñar():
    usuario_actual = session.get("usuario")
    if usuario_actual != fondador:
        return "Solo el fundador puede acuñar."
    cantidad = int(request.form["cantidad"])
    usuarios[usuario_actual]["saldo"] += cantidad
    guardar_usuarios()
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
    guardar_usuarios()
    return redirect(url_for("index"))

@app.route("/invertir", methods=["POST"])
def invertir():
    usuario = session.get("usuario")
    moneda = request.form["moneda"]
    cantidad = int(request.form["cantidad"])
    if moneda in ["BTC","ETH","LTC","CNC"]:
        costo = precios[moneda] * cantidad
        if usuarios[usuario]["saldo"] < costo:
            return "Saldo insuficiente"
        usuarios[usuario]["saldo"] -= costo
        if moneda == "CNC":
            usuarios[usuario]["acciones"]["CNC"] += cantidad
        else:
            usuarios[usuario]["cripto"][moneda] += cantidad
            precios[moneda] += random.randint(-10,10)
    guardar_usuarios()
    return redirect(url_for("index"))

@app.route("/vender", methods=["POST"])
def vender():
    usuario = session.get("usuario")
    moneda = request.form["moneda"]
    cantidad = int(request.form["cantidad"])
    if moneda in ["BTC","ETH","LTC","CNC"]:
        if moneda == "CNC":
            if usuarios[usuario]["acciones"]["CNC"] < cantidad:
                return "No tienes suficientes acciones"
            usuarios[usuario]["acciones"]["CNC"] -= cantidad
            usuarios[usuario]["saldo"] += precios[moneda] * cantidad
        else:
            if usuarios[usuario]["cripto"][moneda] < cantidad:
                return "No tienes suficientes monedas"
            usuarios[usuario]["cripto"][moneda] -= cantidad
            usuarios[usuario]["saldo"] += precios[moneda] * cantidad
            precios[moneda] += random.randint(-10,10)
    guardar_usuarios()
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

@app.route("/precios")
def precios_json():
    return jsonify(precios)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
