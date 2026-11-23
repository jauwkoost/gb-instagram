"""
Gemeentebelangen Urk – Instagram-generator
Start lokaal met:  python app.py   (daarna http://localhost:8080)
"""
import io
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from functools import wraps

from flask import (Flask, Response, abort, redirect, render_template, request,
                   send_from_directory, url_for)
from PIL import Image, ImageOps

from renderer import load_config, render_all

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.environ.get("GB_OUTPUT", os.path.join(BASE, "output"))
WACHTWOORD = os.environ.get("GB_WACHTWOORD", "")
BEWAAR_DAGEN = int(os.environ.get("GB_BEWAAR_DAGEN", "30"))

os.makedirs(OUTPUT, exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # max 25 MB per upload

ID_RE = re.compile(r"^[a-f0-9]{32}$")
VELDEN = ["soort", "label", "titel", "ondertitel", "kop", "tekst", "lijst_kop", "lijst",
          "slot", "uitslag", "foto_stijl", "story_oproep", "focus_x", "focus_y"]


# ---------------------------------------------------------------- wachtwoord
def beveiligd(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if WACHTWOORD:
            auth = request.authorization
            if not auth or auth.password != WACHTWOORD:
                return Response("Inloggen vereist", 401,
                                {"WWW-Authenticate": 'Basic realm="Gemeentebelangen"'})
        return f(*args, **kwargs)
    return wrapper


def opruimen():
    grens = time.time() - BEWAAR_DAGEN * 86400
    for naam in os.listdir(OUTPUT):
        pad = os.path.join(OUTPUT, naam)
        if ID_RE.match(naam) and os.path.isdir(pad) and os.path.getmtime(pad) < grens:
            shutil.rmtree(pad, ignore_errors=True)


def map_voor(job_id):
    if not ID_RE.match(job_id or ""):
        abort(404)
    pad = os.path.join(OUTPUT, job_id)
    if not os.path.isdir(pad):
        abort(404)
    return pad


def bestandsnaam(titel):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", titel.lower()).strip("-")
    return (s[:50] or "post")


# ---------------------------------------------------------------- pagina's
@app.route("/")
@beveiligd
def formulier():
    cfg = load_config()
    vorige = {}
    van = request.args.get("van", "")
    if ID_RE.match(van):
        pad = os.path.join(OUTPUT, van, "invoer.json")
        if os.path.exists(pad):
            with open(pad, encoding="utf-8") as f:
                vorige = json.load(f)
            vorige["_id"] = van
            vorige["_heeft_foto"] = os.path.exists(os.path.join(OUTPUT, van, "foto.png"))
    return render_template("index.html", cfg=cfg, vorige=vorige)


@app.route("/maak", methods=["POST"])
@beveiligd
def maak():
    opruimen()
    cfg = load_config()
    data = {k: (request.form.get(k) or "").strip() for k in VELDEN}
    if data["soort"] not in cfg["soorten"]:
        abort(400)
    if not data["titel"]:
        return "Vul een titel in.", 400

    # stemming
    voor, tegen = [], []
    namen = request.form.getlist("partij_naam")
    zetels = request.form.getlist("partij_zetels")
    stemmen = request.form.getlist("partij_stem")
    for naam, z, s in zip(namen, zetels, stemmen):
        naam = naam.strip()
        if not naam or s not in ("voor", "tegen"):
            continue
        try:
            z = int(z)
        except ValueError:
            z = 0
        (voor if s == "voor" else tegen).append({"naam": naam, "zetels": z})
    data["stemming"] = {"voor": voor, "tegen": tegen}

    job_id = uuid.uuid4().hex
    pad = os.path.join(OUTPUT, job_id)
    os.makedirs(pad)

    # afbeelding: nieuw geüpload, of die van de vorige versie
    foto = None
    upload = request.files.get("afbeelding")
    if upload and upload.filename:
        try:
            foto = Image.open(upload.stream)
            foto.load()
        except Exception:
            shutil.rmtree(pad, ignore_errors=True)
            return "Deze afbeelding kan niet worden geopend. Gebruik JPG of PNG.", 400
    elif request.form.get("foto_behouden") == "1":
        vorige = request.form.get("vorige_id", "")
        oud = os.path.join(OUTPUT, vorige, "foto.png")
        if ID_RE.match(vorige) and os.path.exists(oud):
            foto = Image.open(oud)
            foto.load()
    if foto is not None:
        foto = ImageOps.exif_transpose(foto).convert("RGB")  # telefoonfoto's rechtop zetten
        foto.thumbnail((2400, 2400))
        foto.save(os.path.join(pad, "foto.png"))

    with open(os.path.join(pad, "invoer.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    slides, story = render_all(dict(data), foto)
    basis = bestandsnaam(data["titel"])
    namen_uit = []
    for i, s in enumerate(slides, 1):
        n = f"{basis}_post_{i:02d}.png"
        s.save(os.path.join(pad, n), optimize=True)
        namen_uit.append(n)
    sn = f"{basis}_story.png"
    story.save(os.path.join(pad, sn), optimize=True)
    namen_uit.append(sn)

    with zipfile.ZipFile(os.path.join(pad, f"{basis}.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for n in namen_uit:
            z.write(os.path.join(pad, n), n)

    with open(os.path.join(pad, "bestanden.json"), "w") as f:
        json.dump({"post": namen_uit[:-1], "story": sn, "zip": f"{basis}.zip"}, f)
    return redirect(url_for("resultaat", job_id=job_id))


@app.route("/resultaat/<job_id>")
@beveiligd
def resultaat(job_id):
    pad = map_voor(job_id)
    with open(os.path.join(pad, "bestanden.json")) as f:
        bestanden = json.load(f)
    with open(os.path.join(pad, "invoer.json"), encoding="utf-8") as f:
        invoer = json.load(f)
    return render_template("resultaat.html", job_id=job_id, b=bestanden, invoer=invoer)


@app.route("/bestand/<job_id>/<naam>")
@beveiligd
def bestand(job_id, naam):
    pad = map_voor(job_id)
    download = request.args.get("download") == "1"
    return send_from_directory(pad, naam, as_attachment=download)


@app.route("/gezond")
def gezond():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
