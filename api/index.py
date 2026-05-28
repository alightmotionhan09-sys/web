from flask import Flask, request, jsonify, render_template, send_file, abort, Response
from datetime import datetime
import os

# Vercel: templates harus di folder "templates" relatif dari file ini
# Struktur: api/index.py  →  templates/ harus di api/templates/
app = Flask(__name__, template_folder="../templates", static_folder="../static")

# ⚠️ VERCEL: /tmp adalah satu-satunya folder yang bisa ditulis,
# tapi TIDAK PERSISTEN antar request (ephemeral).
# Untuk penyimpanan permanen gunakan database eksternal (Supabase, PlanetScale, dsb).
SAVE_DIR = "/tmp/modules"
os.makedirs(SAVE_DIR, exist_ok=True)


def parse_module_file(filename):
    filepath = os.path.join(SAVE_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    lines      = content.splitlines()
    name       = filename
    path       = ""
    sent       = ""
    code_lines = []
    in_code    = False

    for line in lines:
        if line.startswith("-- Module:"):
            name = line.replace("-- Module:", "").strip()
        elif line.startswith("-- Path  :"):
            path = line.replace("-- Path  :", "").strip()
        elif line.startswith("-- Sent  :"):
            sent = line.replace("-- Sent  :", "").strip()
        elif line.startswith("---"):
            in_code = True
        elif in_code:
            code_lines.append(line)

    return {
        "file": filename,
        "name": name,
        "path": path,
        "sent": sent,
        "code": "\n".join(code_lines).strip(),
    }


@app.route("/")
def index():
    return render_template("web.html")


@app.route("/api/modules", methods=["GET"])
def api_modules():
    files = sorted(
        [f for f in os.listdir(SAVE_DIR) if f.endswith(".lua")],
        reverse=True
    )
    modules = []
    for f in files:
        data = parse_module_file(f)
        if data:
            modules.append(data)
    return jsonify({"count": len(modules), "modules": modules})


@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Body harus JSON"}), 400

    module_name = data.get("name", "unknown")
    module_code = data.get("code", "")
    module_path = data.get("path", "")

    if not module_code:
        return jsonify({"status": "error", "message": "Field 'code' kosong"}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in module_name)
    filename  = f"{timestamp}_{safe_name}.lua"
    filepath  = os.path.join(SAVE_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"-- Module: {module_name}\n")
        f.write(f"-- Path  : {module_path}\n")
        f.write(f"-- Sent  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("-" * 60 + "\n\n")
        f.write(module_code)

    return jsonify({
        "status":  "ok",
        "message": f"Module '{module_name}' berhasil disimpan.",
        "file":    filename,
    })


@app.route("/download/<filename>")
def download_file(filename):
    filename = os.path.basename(filename)
    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype="text/plain"
    )


@app.route("/share/<filename>")
def share_file(filename):
    filename = os.path.basename(filename)
    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    data = parse_module_file(filename)
    if not data:
        abort(404)
    return Response(data["code"], mimetype="text/plain; charset=utf-8")


@app.route("/view/<filename>")
def view_file(filename):
    filename = os.path.basename(filename)
    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    data = parse_module_file(filename)
    if not data:
        abort(404)
    return render_template("share.html", module=data, filename=filename)


@app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.get_json(silent=True)
    if not data or not data.get("file"):
        return jsonify({"status": "error", "message": "File tidak ditemukan"}), 400
    filename = os.path.basename(data["file"])
    filepath = os.path.join(SAVE_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"status": "ok", "message": f"{filename} dihapus."})
    return jsonify({"status": "error", "message": "File tidak ada."}), 404


@app.route("/api/clear", methods=["POST"])
def api_clear():
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".lua")]
    for f in files:
        os.remove(os.path.join(SAVE_DIR, f))
    return jsonify({"status": "ok", "message": f"{len(files)} files dihapus."})


# Vercel butuh variable `app` yang di-export, bukan __main__
# Jangan pakai app.run() di sini
