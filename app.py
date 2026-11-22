"""NotesFinder - Flask backend."""
import os
import difflib
import re
import shutil
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, g, jsonify, render_template, request, send_file, abort
from PIL import Image
from werkzeug.utils import secure_filename

from processing import ocr
from processing.pdf_processing import process_pdf
from processing.tagging import generate_tags

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE)  # where uploads + database live (set to a persistent disk in production)
UPLOADS = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "database", "notes.db")
IMG_EXT = {"jpg", "jpeg", "png"}
ALLOWED = IMG_EXT | {"pdf"}
DEFAULT_SUBJECTS = ["Data Structures", "Mathematics", "Operating Systems", "Computer Networks",
            "DBMS", "Computer Organization and Architecture", "Other"]

app = Flask(__name__)


def get_subjects():
    """Default subjects plus any custom ones users have created."""
    extra = [r[0] for r in db().execute("SELECT DISTINCT subject FROM notes ORDER BY subject")]
    return DEFAULT_SUBJECTS + [x for x in extra if x not in DEFAULT_SUBJECTS]


def clean_subject(raw):
    s = re.sub(r"\s+", " ", (raw or "")).strip()[:60]
    if not s:
        return "Other"
    for known in get_subjects():
        if known.lower() == s.lower():
            return known
    return s

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes(
  note_id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT NOT NULL, file_path TEXT NOT NULL,
  subject TEXT NOT NULL, file_type TEXT NOT NULL, upload_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pages(
  page_id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL, extracted_text TEXT NOT NULL DEFAULT '', preview_path TEXT);
CREATE TABLE IF NOT EXISTS tags(tag_id INTEGER PRIMARY KEY AUTOINCREMENT, tag_name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS page_tags(
  page_id INTEGER NOT NULL REFERENCES pages(page_id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE, PRIMARY KEY(page_id, tag_id));
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    for sub in ("images", "pdfs", "pages"):
        os.makedirs(os.path.join(UPLOADS, sub), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript(SCHEMA)
    c.commit()
    c.close()


def page_tags(page_id):
    rows = db().execute("SELECT t.tag_name FROM tags t JOIN page_tags pt ON pt.tag_id=t.tag_id WHERE pt.page_id=?", (page_id,))
    return [r[0] for r in rows]


def save_page(note_id, num, text, preview):
    d = db()
    cur = d.execute("INSERT INTO pages(note_id,page_number,extracted_text,preview_path) VALUES(?,?,?,?)",
                    (note_id, num, text, preview))
    pid = cur.lastrowid
    for t in generate_tags(text):
        d.execute("INSERT OR IGNORE INTO tags(tag_name) VALUES(?)", (t,))
        tid = d.execute("SELECT tag_id FROM tags WHERE tag_name=?", (t,)).fetchone()[0]
        d.execute("INSERT OR IGNORE INTO page_tags VALUES(?,?)", (pid, tid))


# ---------- pages ----------
@app.route("/")
def index():
    return render_template("index.html", subjects=get_subjects())


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", subjects=get_subjects())


@app.route("/results")
def results():
    return render_template("results.html", subjects=get_subjects(), q=request.args.get("q", ""),
                           subject=request.args.get("subject", ""))


# ---------- API ----------
@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    subject = request.form.get("subject", "Other")
    if not f or not f.filename:
        return jsonify(error="No file selected."), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED:
        return jsonify(error="Unsupported file type. Use JPG, JPEG, PNG or PDF."), 400
    subject = clean_subject(subject)
    original = secure_filename(f.filename) or f"note.{ext}"
    stored = f"{uuid.uuid4().hex[:10]}_{original}"
    folder = "pdfs" if ext == "pdf" else "images"
    path = os.path.join(UPLOADS, folder, stored)
    f.save(path)
    d = db()
    cur = d.execute("INSERT INTO notes(file_name,file_path,subject,file_type,upload_date) VALUES(?,?,?,?,?)",
                    (original, os.path.relpath(path, BASE), subject, ext, datetime.now().strftime("%Y-%m-%d %H:%M")))
    nid = cur.lastrowid
    try:
        pages = used_ocr = 0
        if ext == "pdf":
            pdir = os.path.join(UPLOADS, "pages", str(nid))
            for num, text, prev, ocr_used in process_pdf(path, pdir):
                save_page(nid, num, text, os.path.relpath(prev, BASE))
                pages += 1
                used_ocr += ocr_used
        else:
            with Image.open(path) as im:
                im.load()
                text = ocr.extract_text(im).strip()
            save_page(nid, 1, text, os.path.relpath(path, BASE))
            pages, used_ocr = 1, 1
        d.commit()
    except Exception as e:
        d.rollback()
        if os.path.exists(path):
            os.remove(path)
        shutil.rmtree(os.path.join(UPLOADS, "pages", str(nid)), ignore_errors=True)
        return jsonify(error=f"Could not process file: {e}"), 422
    engine = ocr.engine_name()
    warn = None
    if used_ocr and engine == "none":
        warn = "No OCR engine installed (EasyOCR/Tesseract) - images and scanned pages have no searchable text yet."
    return jsonify(note_id=nid, file_name=original, subject=subject, pages=pages, ocr_engine=engine, warning=warn), 201


NOTE_Q = "SELECT n.*, (SELECT COUNT(*) FROM pages p WHERE p.note_id=n.note_id) AS pages FROM notes n"


def note_dict(r):
    return dict(note_id=r["note_id"], file_name=r["file_name"], subject=r["subject"],
                file_type=r["file_type"], upload_date=r["upload_date"], pages=r["pages"])


@app.get("/api/notes")
def notes():
    rows = db().execute(NOTE_Q + " ORDER BY n.note_id DESC").fetchall()
    return jsonify([note_dict(r) for r in rows])


@app.get("/api/notes/<int:nid>")
def note(nid):
    r = db().execute(NOTE_Q + " WHERE n.note_id=?", (nid,)).fetchone()
    if not r:
        return jsonify(error="Note not found"), 404
    out = note_dict(r)
    out["page_list"] = [dict(page_id=p["page_id"], page_number=p["page_number"], tags=page_tags(p["page_id"]),
                             text=p["extracted_text"]) for p in
                        db().execute("SELECT * FROM pages WHERE note_id=? ORDER BY page_number", (nid,))]
    return jsonify(out)


@app.delete("/api/notes/<int:nid>")
def delete_note(nid):
    d = db()
    r = d.execute("SELECT * FROM notes WHERE note_id=?", (nid,)).fetchone()
    if not r:
        return jsonify(error="Note not found"), 404
    d.execute("DELETE FROM notes WHERE note_id=?", (nid,))
    d.execute("DELETE FROM tags WHERE tag_id NOT IN (SELECT tag_id FROM page_tags)")
    d.commit()
    fp = os.path.join(BASE, r["file_path"])
    if os.path.exists(fp):
        os.remove(fp)
    shutil.rmtree(os.path.join(UPLOADS, "pages", str(nid)), ignore_errors=True)
    return jsonify(deleted=nid)


@app.get("/api/subjects")
def subjects():
    counts = {r[0]: r[1] for r in db().execute("SELECT subject, COUNT(*) FROM notes GROUP BY subject")}
    return jsonify([dict(name=s, count=counts.get(s, 0)) for s in get_subjects()])


@app.get("/api/stats")
def stats():
    d = db()
    return jsonify(notes=d.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
                   pages=d.execute("SELECT COUNT(*) FROM pages").fetchone()[0],
                   tags=d.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
                   subjects=d.execute("SELECT COUNT(DISTINCT subject) FROM notes").fetchone()[0],
                   top_tags=[r[0] for r in d.execute(
                       "SELECT t.tag_name FROM tags t JOIN page_tags pt ON pt.tag_id=t.tag_id "
                       "GROUP BY t.tag_id ORDER BY COUNT(*) DESC LIMIT 12")],
                   ocr_engine=ocr.engine_name())


def snippet(text, terms, width=240):
    flat = re.sub(r"\s+", " ", text)
    low = flat.lower()
    pos = [low.find(t) for t in terms if low.find(t) >= 0]
    start = max(0, (min(pos) if pos else 0) - 80)
    s = flat[start:start + width]
    return ("…" if start else "") + s + ("…" if start + width < len(flat) else "")


def like(t):
    return "%" + t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def fuzzy_word(term, words):
    """Return a word from `words` that approximately matches `term`, else None.
    Tolerates OCR slips: wrong/missing letters and words cut off at the end."""
    if len(term) < 4:
        return None
    best, best_r = None, 0.0
    for w in words:
        if abs(len(w) - len(term)) > 3 or w[0] != term[0]:
            continue
        if len(w) >= 4 and (term.startswith(w) or w.startswith(term)):  # truncated word
            return w
        r = difflib.SequenceMatcher(None, term, w).ratio()
        if r > best_r:
            best, best_r = w, r
    return best if best_r >= 0.8 else None


SEARCH_SQL = ("SELECT p.page_id,p.page_number,p.extracted_text,n.note_id,n.file_name,n.subject,n.file_type,"
              "IFNULL(tg.tags,'') AS tags FROM pages p JOIN notes n ON n.note_id=p.note_id "
              "LEFT JOIN (SELECT pt.page_id, GROUP_CONCAT(t.tag_name,'|') AS tags FROM page_tags pt "
              "JOIN tags t ON t.tag_id=pt.tag_id GROUP BY pt.page_id) tg ON tg.page_id=p.page_id WHERE 1=1")


@app.get("/api/search")
def search():
    q = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    note_id = request.args.get("note_id", type=int)
    terms = [t for t in re.findall(r"\w+", q.lower()) if t]
    if not terms:
        return jsonify(query=q, terms=[], count=0, results=[])
    sql, params = SEARCH_SQL, []
    if subject:
        sql += " AND n.subject=?"
        params.append(subject)
    if note_id:
        sql += " AND n.note_id=?"
        params.append(note_id)
    phrase = q.lower()
    exact, similar = [], []
    for r in db().execute(sql, params):
        text = r["extracted_text"]
        low = text.lower()
        hay = low + " " + r["tags"].lower()
        words = None
        matched, fuzzy_hits = [], []
        for t in terms:
            if t in hay:
                matched.append(t)
                continue
            if words is None:
                words = set(re.findall(r"\w+", hay))
            w = fuzzy_word(t, words)
            if not w:
                break
            matched.append(w)
            fuzzy_hits.append(w)
        else:
            is_fuzzy = bool(fuzzy_hits)
            score = low.count(phrase) * 5 + sum(low.count(t) for t in matched)
            item = dict(page_id=r["page_id"], note_id=r["note_id"], subject=r["subject"], file_name=r["file_name"],
                        file_type=r["file_type"], page_number=r["page_number"],
                        tags=[t for t in r["tags"].split("|") if t],
                        snippet=snippet(text, matched), score=score, fuzzy=is_fuzzy, hl=fuzzy_hits)
            (similar if is_fuzzy else exact).append(item)
    exact.sort(key=lambda x: -x["score"])
    similar.sort(key=lambda x: -x["score"])
    out = exact + similar
    return jsonify(query=q, terms=terms, count=len(out), exact=len(exact), results=out)


@app.get("/api/pages/<int:pid>")
def get_page(pid):
    p = db().execute("SELECT p.*, n.file_name, n.subject FROM pages p JOIN notes n USING(note_id) WHERE page_id=?", (pid,)).fetchone()
    if not p:
        return jsonify(error="Page not found"), 404
    sib = db().execute("SELECT page_id, page_number FROM pages WHERE note_id=? ORDER BY page_number", (p["note_id"],)).fetchall()
    ids = [r["page_id"] for r in sib]
    i = ids.index(pid)
    return jsonify(page_id=pid, note_id=p["note_id"], file_name=p["file_name"], subject=p["subject"],
                   page_number=p["page_number"], total_pages=len(ids), text=p["extracted_text"], tags=page_tags(pid),
                   prev_id=ids[i - 1] if i > 0 else None, next_id=ids[i + 1] if i < len(ids) - 1 else None)


@app.get("/api/pages/<int:pid>/image")
def page_image(pid):
    p = db().execute("SELECT preview_path FROM pages WHERE page_id=?", (pid,)).fetchone()
    if not p or not p[0] or not os.path.exists(os.path.join(BASE, p[0])):
        abort(404)
    return send_file(os.path.join(BASE, p[0]))


@app.get("/api/notes/<int:nid>/file")
def note_file(nid):
    r = db().execute("SELECT file_path FROM notes WHERE note_id=?", (nid,)).fetchone()
    if not r or not os.path.exists(os.path.join(BASE, r[0])):
        abort(404)
    return send_file(os.path.join(BASE, r[0]))


@app.errorhandler(413)
def too_big(_):
    return jsonify(error="File too large (max 50 MB)."), 413


init_db()


def _warm_ocr():
    """Load the OCR model in the background so the first upload isn't slow."""
    try:
        ocr._detect()
    except Exception:
        pass


if os.environ.get("WARM_OCR") or __name__ == "__main__":
    import threading
    threading.Thread(target=_warm_ocr, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
