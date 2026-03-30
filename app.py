"""
MarquiBot Web — Marmoles Marquitec
Flask + SQLite  |  pip install flask
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import sqlite3, os, re
from datetime import datetime
from werkzeug.utils import secure_filename

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))

# Busca templates/ si existe, si no usa la raiz
_tmpl = os.path.join(BASE_DIR, "templates")
if not os.path.isdir(_tmpl):
    _tmpl = BASE_DIR

app = Flask(__name__, template_folder=_tmpl)
app.secret_key = "marquitec_2024_secret"

DB_PATH   = os.path.join(BASE_DIR, "marquibot_data.db")
DOCS_DIR  = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(DOCS_DIR, exist_ok=True)

ALLOWED = {"pdf","png","jpg","jpeg","xlsx","xls"}

# ══════════════════════════════════════════════════════════════
#  DB
# ══════════════════════════════════════════════════════════════
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with get_db() as con:
        cur = con.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS proyectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE, creado TEXT, usuario TEXT);

            CREATE TABLE IF NOT EXISTS proyecto_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proyecto_id INTEGER NOT NULL, tipo TEXT NOT NULL,
                fecha TEXT, nombre_arch TEXT, ruta_local TEXT,
                subido TEXT, usuario TEXT);

            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT, material TEXT, grosor TEXT,
                cantidad TEXT, usuario TEXT);

            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material TEXT NOT NULL, grosor TEXT,
                cantidad INTEGER NOT NULL DEFAULT 0,
                unidad TEXT DEFAULT 'uds', actualizado TEXT);

            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                emoji TEXT DEFAULT '👤', activo INTEGER DEFAULT 1);

            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT, usuario TEXT, modulo TEXT, accion TEXT);
        """)
        for nom, em in [("Nataly","🌸"),("Emilie","😊"),("Rafael","👋"),("Liliana","💚")]:
            cur.execute("INSERT OR IGNORE INTO usuarios (nombre,emoji,activo) VALUES (?,?,1)",(nom,em))
        # Migraciones
        for tabla, col, tipo in [
            ("pedidos","grosor","TEXT"), ("inventario","grosor","TEXT"),
            ("inventario","unidad","TEXT"), ("historial","modulo","TEXT"),
            ("historial","accion","TEXT"),
        ]:
            try: cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
            except: pass
        con.commit()

init_db()

def db_q(sql, p=()):
    with get_db() as c: return c.execute(sql,p).fetchall()

def db_one(sql, p=()):
    with get_db() as c: return c.execute(sql,p).fetchone()

def db_exec(sql, p=()):
    with get_db() as c: c.execute(sql,p); c.commit()

def log(usuario, modulo, accion):
    db_exec("INSERT INTO historial (fecha,usuario,modulo,accion) VALUES (?,?,?,?)",
            (datetime.now().strftime("%d/%m/%Y %H:%M"), usuario, modulo, accion))

def ahora(): return datetime.now().strftime("%d/%m/%Y %H:%M")

def usuario_actual():
    return session.get("usuario", None)

# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        nombre = request.form.get("usuario","").strip()
        if nombre:
            session["usuario"] = nombre
            log(nombre,"AUTH","Login")
            return redirect(url_for("dashboard"))
    usuarios = db_q("SELECT nombre,emoji FROM usuarios WHERE activo=1 ORDER BY id")
    return render_template("login.html", usuarios=usuarios)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def require_login():
    if not usuario_actual():
        return redirect(url_for("login"))
    return None

# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
@app.route("/dashboard")
def dashboard():
    r = require_login()
    if r: return r
    n_proyectos  = db_one("SELECT COUNT(*) as c FROM proyectos")["c"]
    n_pedidos    = db_one("SELECT COUNT(*) as c FROM pedidos")["c"]
    n_inventario = db_one("SELECT COUNT(*) as c FROM inventario")["c"]
    historial    = db_q("SELECT fecha,usuario,modulo,accion FROM historial ORDER BY id DESC LIMIT 8")
    return render_template("dashboard.html",
        usuario=usuario_actual(),
        n_proyectos=n_proyectos, n_pedidos=n_pedidos, n_inventario=n_inventario,
        historial=historial)

# ══════════════════════════════════════════════════════════════
#  PROYECTOS
# ══════════════════════════════════════════════════════════════
@app.route("/proyectos")
def proyectos():
    r = require_login()
    if r: return r
    rows = db_q("SELECT id,nombre,creado,usuario FROM proyectos ORDER BY id DESC")
    data = []
    for p in rows:
        ndocs = db_one("SELECT COUNT(*) as c FROM proyecto_docs WHERE proyecto_id=? AND ruta_local IS NOT NULL",(p["id"],))["c"]
        data.append({"id":p["id"],"nombre":p["nombre"],"creado":p["creado"],"usuario":p["usuario"],"ndocs":ndocs})
    return render_template("proyectos.html", usuario=usuario_actual(), proyectos=data)

@app.route("/proyectos/nuevo", methods=["GET","POST"])
def nuevo_proyecto():
    r = require_login()
    if r: return r
    error = None
    if request.method == "POST":
        nombre = request.form.get("nombre","").strip()
        if not nombre:
            error = "El nombre es obligatorio."
        else:
            try:
                db_exec("INSERT INTO proyectos (nombre,creado,usuario) VALUES (?,?,?)",
                        (nombre, ahora(), usuario_actual()))
                pid = db_one("SELECT id FROM proyectos WHERE nombre=?",(nombre,))["id"]
                # Guardar docs
                for tipo in ["cotizacion","render","plano_corte"]:
                    fecha = request.form.get("fecha_"+tipo,"").strip()
                    f = request.files.get("archivo_"+tipo)
                    nom_a = dest = None
                    if f and f.filename:
                        nom_a = secure_filename(f.filename)
                        dest  = os.path.join(DOCS_DIR, str(pid)+"_"+tipo+"_"+nom_a)
                        f.save(dest)
                        dest  = str(pid)+"_"+tipo+"_"+nom_a  # ruta relativa
                    db_exec("INSERT INTO proyecto_docs (proyecto_id,tipo,fecha,nombre_arch,ruta_local,subido,usuario) VALUES (?,?,?,?,?,?,?)",
                            (pid,tipo,fecha,nom_a,dest,ahora(),usuario_actual()))
                log(usuario_actual(),"PROYECTO","Nuevo: "+nombre)
                return redirect(url_for("ver_proyecto", pid=pid))
            except Exception as ex:
                error = "Ya existe un proyecto con ese nombre." if "UNIQUE" in str(ex) else str(ex)
    return render_template("nuevo_proyecto.html", usuario=usuario_actual(), error=error)

@app.route("/proyectos/<int:pid>")
def ver_proyecto(pid):
    r = require_login()
    if r: return r
    proy = db_one("SELECT * FROM proyectos WHERE id=?", (pid,))
    if not proy: return redirect(url_for("proyectos"))
    docs = db_q("SELECT * FROM proyecto_docs WHERE proyecto_id=?", (pid,))
    docs_dict = {d["tipo"]: d for d in docs}
    return render_template("ver_proyecto.html", usuario=usuario_actual(),
                           proy=proy, docs=docs_dict)

@app.route("/proyectos/<int:pid>/adjuntar/<tipo>", methods=["POST"])
def adjuntar_doc(pid, tipo):
    r = require_login()
    if r: return r
    f = request.files.get("archivo")
    fecha = request.form.get("fecha", datetime.now().strftime("%d/%m/%Y"))
    if f and f.filename:
        nom_a = secure_filename(f.filename)
        dest_rel = str(pid)+"_"+tipo+"_"+nom_a
        dest = os.path.join(DOCS_DIR, dest_rel)
        f.save(dest)
        existe = db_one("SELECT id FROM proyecto_docs WHERE proyecto_id=? AND tipo=?",(pid,tipo))
        if existe:
            db_exec("UPDATE proyecto_docs SET fecha=?,nombre_arch=?,ruta_local=?,subido=?,usuario=? WHERE proyecto_id=? AND tipo=?",
                    (fecha,nom_a,dest_rel,ahora(),usuario_actual(),pid,tipo))
        else:
            db_exec("INSERT INTO proyecto_docs (proyecto_id,tipo,fecha,nombre_arch,ruta_local,subido,usuario) VALUES (?,?,?,?,?,?,?)",
                    (pid,tipo,fecha,nom_a,dest_rel,ahora(),usuario_actual()))
        log(usuario_actual(),"PROYECTO","Adjunto "+tipo)
    return redirect(url_for("ver_proyecto", pid=pid))

@app.route("/proyectos/<int:pid>/eliminar", methods=["POST"])
def eliminar_proyecto(pid):
    r = require_login()
    if r: return r
    proy = db_one("SELECT nombre FROM proyectos WHERE id=?",(pid,))
    if proy:
        db_exec("DELETE FROM proyecto_docs WHERE proyecto_id=?",(pid,))
        db_exec("DELETE FROM proyectos WHERE id=?",(pid,))
        log(usuario_actual(),"PROYECTO","Eliminado: "+proy["nombre"])
    return redirect(url_for("proyectos"))

@app.route("/archivos/<filename>")
def archivo(filename):
    return send_from_directory(DOCS_DIR, filename)

# ══════════════════════════════════════════════════════════════
#  PEDIDOS
# ══════════════════════════════════════════════════════════════
@app.route("/pedidos")
def pedidos():
    r = require_login()
    if r: return r
    rows = db_q("SELECT * FROM pedidos ORDER BY id DESC")
    return render_template("pedidos.html", usuario=usuario_actual(), pedidos=rows)

@app.route("/pedidos/nuevo", methods=["POST"])
def nuevo_pedido():
    r = require_login()
    if r: return r
    material = request.form.get("material","").strip()
    grosor   = request.form.get("grosor","").strip()
    cantidad = request.form.get("cantidad","").strip()
    fecha    = request.form.get("fecha", datetime.now().strftime("%d/%m/%Y"))
    if material and cantidad:
        db_exec("INSERT INTO pedidos (fecha,material,grosor,cantidad,usuario) VALUES (?,?,?,?,?)",
                (fecha,material,grosor,cantidad,usuario_actual()))
        log(usuario_actual(),"PEDIDO","Nuevo: "+material+" x"+cantidad)
    return redirect(url_for("pedidos"))

@app.route("/pedidos/<int:pid>/eliminar", methods=["POST"])
def eliminar_pedido(pid):
    r = require_login()
    if r: return r
    p = db_one("SELECT material FROM pedidos WHERE id=?",(pid,))
    if p:
        db_exec("DELETE FROM pedidos WHERE id=?",(pid,))
        log(usuario_actual(),"PEDIDO","Eliminado: "+p["material"])
    return redirect(url_for("pedidos"))

# ══════════════════════════════════════════════════════════════
#  INVENTARIO
# ══════════════════════════════════════════════════════════════
@app.route("/inventario")
def inventario():
    r = require_login()
    if r: return r
    rows = db_q("SELECT * FROM inventario ORDER BY material")
    return render_template("inventario.html", usuario=usuario_actual(), items=rows)

@app.route("/inventario/agregar", methods=["POST"])
def agregar_inventario():
    r = require_login()
    if r: return r
    material = request.form.get("material","").strip()
    grosor   = request.form.get("grosor","").strip()
    cantidad = request.form.get("cantidad","0").strip()
    unidad   = request.form.get("unidad","uds").strip() or "uds"
    if material:
        try:
            cant = int(cantidad)
            existe = db_one("SELECT id,cantidad FROM inventario WHERE LOWER(material)=LOWER(?) AND LOWER(COALESCE(grosor,''))=LOWER(?)",(material,grosor))
            if existe:
                db_exec("UPDATE inventario SET cantidad=?,unidad=?,actualizado=? WHERE id=?",
                        (existe["cantidad"]+cant, unidad, ahora(), existe["id"]))
            else:
                db_exec("INSERT INTO inventario (material,grosor,cantidad,unidad,actualizado) VALUES (?,?,?,?,?)",
                        (material,grosor,cant,unidad,ahora()))
            log(usuario_actual(),"INVENTARIO","+ "+material+" "+grosor+" "+str(cant))
        except: pass
    return redirect(url_for("inventario"))

@app.route("/inventario/<int:iid>/quitar", methods=["POST"])
def quitar_inventario(iid):
    r = require_login()
    if r: return r
    cantidad = request.form.get("cantidad","0").strip()
    item = db_one("SELECT * FROM inventario WHERE id=?",(iid,))
    if item:
        try:
            q = int(cantidad)
            nueva = max(0, item["cantidad"] - q)
            db_exec("UPDATE inventario SET cantidad=?,actualizado=? WHERE id=?",(nueva,ahora(),iid))
            log(usuario_actual(),"INVENTARIO","- "+item["material"]+" -"+str(q))
        except: pass
    return redirect(url_for("inventario"))

@app.route("/inventario/<int:iid>/eliminar", methods=["POST"])
def eliminar_inventario(iid):
    r = require_login()
    if r: return r
    item = db_one("SELECT material FROM inventario WHERE id=?",(iid,))
    if item:
        db_exec("DELETE FROM inventario WHERE id=?",(iid,))
        log(usuario_actual(),"INVENTARIO","Eliminado: "+item["material"])
    return redirect(url_for("inventario"))

# ══════════════════════════════════════════════════════════════
#  FILTROS
# ══════════════════════════════════════════════════════════════
@app.route("/filtros")
def filtros():
    r = require_login()
    if r: return r
    tipo = request.args.get("tipo","Todos")
    mat  = request.args.get("material","").strip().lower()
    gro  = request.args.get("grosor","").strip().lower()
    fi   = request.args.get("fecha_ini","").strip()
    ff   = request.args.get("fecha_fin","").strip()

    resultados = []

    def fecha_ok(f_str):
        if not fi and not ff: return True
        def p(s):
            for fmt in ("%d/%m/%Y","%Y-%m-%d"):
                try: return datetime.strptime(s[:10],fmt)
                except: pass
            return None
        fd=p(str(f_str or ""))
        if fd is None: return True
        if fi and fd < p(fi): return False
        if ff and fd > p(ff): return False
        return True

    if tipo in ("Todos","Pedidos"):
        sql="SELECT id,fecha,material,grosor,cantidad FROM pedidos WHERE 1=1"; vals=[]
        if mat: sql+=" AND LOWER(COALESCE(material,'')) LIKE ?"; vals.append("%"+mat+"%")
        if gro: sql+=" AND LOWER(COALESCE(grosor,'')) LIKE ?";   vals.append("%"+gro+"%")
        for row in db_q(sql,vals):
            if fecha_ok(row["fecha"]):
                resultados.append({"tipo":"Pedido","fecha":row["fecha"],"nombre":row["material"],
                                   "grosor":row["grosor"],"cantidad":row["cantidad"],"id":row["id"],"tabla":"pedidos"})

    if tipo in ("Todos","Inventario"):
        sql="SELECT id,material,grosor,cantidad,unidad FROM inventario WHERE 1=1"; vals=[]
        if mat: sql+=" AND LOWER(COALESCE(material,'')) LIKE ?"; vals.append("%"+mat+"%")
        if gro: sql+=" AND LOWER(COALESCE(grosor,'')) LIKE ?";   vals.append("%"+gro+"%")
        for row in db_q(sql,vals):
            resultados.append({"tipo":"Inventario","fecha":"—","nombre":row["material"],
                               "grosor":row["grosor"],"cantidad":str(row["cantidad"])+" "+(row["unidad"] or "uds"),
                               "id":row["id"],"tabla":"inventario"})

    if tipo in ("Todos","Proyectos"):
        sql="SELECT id,nombre,creado FROM proyectos WHERE 1=1"; vals=[]
        if mat: sql+=" AND LOWER(nombre) LIKE ?"; vals.append("%"+mat+"%")
        for row in db_q(sql,vals):
            if fecha_ok(row["creado"]):
                ndocs=db_one("SELECT COUNT(*) as c FROM proyecto_docs WHERE proyecto_id=? AND ruta_local IS NOT NULL",(row["id"],))["c"]
                resultados.append({"tipo":"Proyecto","fecha":row["creado"],"nombre":row["nombre"],
                                   "grosor":"—","cantidad":str(ndocs)+"/3 docs","id":row["id"],"tabla":"proyectos"})

    return render_template("filtros.html", usuario=usuario_actual(),
                           resultados=resultados, tipo=tipo,
                           mat=mat, gro=gro, fi=fi, ff=ff)

@app.route("/filtros/eliminar", methods=["POST"])
def filtros_eliminar():
    r = require_login()
    if r: return r
    tabla = request.form.get("tabla")
    rid   = request.form.get("id")
    if tabla == "pedidos":
        p = db_one("SELECT material FROM pedidos WHERE id=?",(rid,))
        if p: db_exec("DELETE FROM pedidos WHERE id=?",(rid,)); log(usuario_actual(),"PEDIDO","Eliminado: "+p["material"])
    elif tabla == "inventario":
        p = db_one("SELECT material FROM inventario WHERE id=?",(rid,))
        if p: db_exec("DELETE FROM inventario WHERE id=?",(rid,)); log(usuario_actual(),"INVENTARIO","Eliminado: "+p["material"])
    elif tabla == "proyectos":
        p = db_one("SELECT nombre FROM proyectos WHERE id=?",(rid,))
        if p:
            db_exec("DELETE FROM proyecto_docs WHERE proyecto_id=?",(rid,))
            db_exec("DELETE FROM proyectos WHERE id=?",(rid,))
            log(usuario_actual(),"PROYECTO","Eliminado: "+p["nombre"])
    return redirect(request.referrer or url_for("filtros"))

# ══════════════════════════════════════════════════════════════
#  USUARIOS (admin)
# ══════════════════════════════════════════════════════════════
@app.route("/usuarios")
def usuarios():
    r = require_login()
    if r: return r
    rows = db_q("SELECT * FROM usuarios ORDER BY id")
    return render_template("usuarios.html", usuario=usuario_actual(), usuarios=rows)

@app.route("/usuarios/agregar", methods=["POST"])
def agregar_usuario():
    nombre = request.form.get("nombre","").strip()
    emoji  = request.form.get("emoji","👤").strip() or "👤"
    if nombre:
        try: db_exec("INSERT INTO usuarios (nombre,emoji,activo) VALUES (?,?,1)",(nombre,emoji))
        except: pass
    return redirect(url_for("usuarios"))

@app.route("/usuarios/<int:uid>/toggle", methods=["POST"])
def toggle_usuario(uid):
    row = db_one("SELECT activo FROM usuarios WHERE id=?",(uid,))
    if row: db_exec("UPDATE usuarios SET activo=? WHERE id=?",(0 if row["activo"] else 1,uid))
    return redirect(url_for("usuarios"))

@app.route("/usuarios/<int:uid>/eliminar", methods=["POST"])
def eliminar_usuario(uid):
    db_exec("DELETE FROM usuarios WHERE id=?",(uid,))
    return redirect(url_for("usuarios"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
