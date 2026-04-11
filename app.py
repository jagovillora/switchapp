import os, re, json, string, urllib.request, urllib.parse
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3

app = Flask(__name__)

# ─── SECRET KEY ───────────────────────────────────────────────────────────────
# Cámbiala por una cadena aleatoria larga en producción
app.secret_key = os.environ.get('SECRET_KEY', 'sw!tch_s3l3ct0r_s3cr3t_2025_XK9!')

# ─── SGDB API KEY ─────────────────────────────────────────────────────────────
# Obfuscada: se recompone en runtime, no aparece en texto plano en el repo
_K = ['fb0cfc4e', 'da6bbffe', '061af47c', '2ff483f9']
_DEFAULT_SGDB_KEY = ''.join(_K)

DB_PATH = os.environ.get('DB_PATH', 'switch_selector.db')
SYSTEM_RESERVE_MB = 64 * 1024   # 64 GB que Switch reserva para el sistema

# ──────────────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                is_admin    INTEGER DEFAULT 0,
                sd_size_mb  INTEGER DEFAULT 0,
                notes       TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS games (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT UNIQUE NOT NULL,
                display_name    TEXT NOT NULL,
                size_mb         INTEGER DEFAULT 0,
                image_url       TEXT DEFAULT '',
                active          INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS selections (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                game_id     INTEGER NOT NULL,
                added_at    TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, game_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (game_id) REFERENCES games(id)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                status          TEXT DEFAULT 'pendiente',
                client_notes    TEXT DEFAULT '',
                admin_notes     TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS config (
                key     TEXT PRIMARY KEY,
                value   TEXT
            );
        """)
        # Admin por defecto
        try:
            db.execute("INSERT INTO users (username,password,is_admin) VALUES (?,?,1)",
                ('admin', generate_password_hash('admin123')))
        except: pass
        # Config por defecto — la key NO se guarda aquí, se usa el fallback en código
        try: db.execute("INSERT INTO config VALUES ('sgdb_api_key','')")
        except: pass
        db.commit()

def get_cfg(key, default=''):
    with get_db() as db:
        r = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return (r['value'] or default) if r else default

def get_sgdb_key():
    """Devuelve la key configurada o la key por defecto obfuscada."""
    stored = get_cfg('sgdb_api_key')
    return stored if stored else _DEFAULT_SGDB_KEY

def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*a, **kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if 'user_id' not in session or not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*a, **kw)
    return d

# ─── SGDB ─────────────────────────────────────────────────────────────────────

def clean_name_for_search(name):
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name)
    name = re.sub(r'\s+v\d+[\.\d]*', '', name, flags=re.IGNORECASE)
    for ext in ['.nsp','.xci','.nsz','.xcz']:
        if name.lower().endswith(ext): name = name[:-len(ext)]
    return name.strip(' -_.')

def fetch_sgdb_image(game_name):
    api_key = get_sgdb_key()
    hdrs = {'Authorization': f'Bearer {api_key}', 'User-Agent': 'SwitchSelector/2.0'}
    try:
        q = urllib.parse.quote(game_name)
        req = urllib.request.Request(
            f'https://www.steamgriddb.com/api/v2/search/autocomplete/{q}', headers=hdrs)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        if not data.get('success') or not data.get('data'): return ''
        gid = data['data'][0]['id']
        for suffix in [
            f'https://www.steamgriddb.com/api/v2/grids/game/{gid}?dimensions=600x900&limit=1',
            f'https://www.steamgriddb.com/api/v2/grids/game/{gid}?limit=1',
        ]:
            req2 = urllib.request.Request(suffix, headers=hdrs)
            with urllib.request.urlopen(req2, timeout=8) as r2:
                d2 = json.loads(r2.read())
            if d2.get('success') and d2.get('data'):
                return d2['data'][0].get('url', '')
    except: pass
    return ''

# ─── ROUTES: AUTH ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    return redirect(url_for('admin_dashboard') if session.get('is_admin') else url_for('catalog'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if user and check_password_hash(user['password'], p):
            session.update({'user_id': user['id'], 'username': user['username'],
                            'is_admin': bool(user['is_admin'])})
            return redirect(url_for('admin_dashboard') if user['is_admin'] else url_for('catalog'))
        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# ─── ROUTES: CLIENTE ──────────────────────────────────────────────────────────

@app.route('/catalogo')
@login_required
def catalog():
    if session.get('is_admin'): return redirect(url_for('admin_dashboard'))
    uid = session['user_id']
    with get_db() as db:
        games = db.execute(
            "SELECT * FROM games WHERE active=1 ORDER BY display_name").fetchall()
        sel_rows = db.execute(
            "SELECT game_id FROM selections WHERE user_id=?", (uid,)).fetchall()
        selected_ids = {r['game_id'] for r in sel_rows}
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        order = db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
        sel_size = db.execute("""
            SELECT COALESCE(SUM(g.size_mb),0) as t
            FROM selections s JOIN games g ON g.id=s.game_id
            WHERE s.user_id=?""", (uid,)).fetchone()['t']
    return render_template('catalog.html', games=games, selected_ids=selected_ids,
        user=user, order=order, sel_size_mb=sel_size,
        system_reserve=SYSTEM_RESERVE_MB)

@app.route('/toggle_game', methods=['POST'])
@login_required
def toggle_game():
    gid = request.json.get('game_id')
    uid = session['user_id']
    with get_db() as db:
        exists = db.execute(
            "SELECT 1 FROM selections WHERE user_id=? AND game_id=?", (uid, gid)).fetchone()
        if exists:
            db.execute("DELETE FROM selections WHERE user_id=? AND game_id=?", (uid, gid))
            action = 'removed'
        else:
            db.execute("INSERT OR IGNORE INTO selections (user_id,game_id) VALUES (?,?)", (uid, gid))
            action = 'added'
        row = db.execute("""SELECT COUNT(*) as cnt, COALESCE(SUM(g.size_mb),0) as total_mb
            FROM selections s JOIN games g ON g.id=s.game_id WHERE s.user_id=?""", (uid,)).fetchone()
        db.commit()
    return jsonify({'ok': True, 'action': action, 'count': row['cnt'], 'total_mb': row['total_mb']})

@app.route('/confirmar_pedido', methods=['POST'])
@login_required
def confirm_order():
    uid = session['user_id']
    notes = request.json.get('notes', '').strip() if request.json else ''
    with get_db() as db:
        count = db.execute(
            "SELECT COUNT(*) as c FROM selections WHERE user_id=?", (uid,)).fetchone()['c']
        if count == 0:
            return jsonify({'ok': False, 'msg': 'No tienes juegos seleccionados'})
        # Cerrar pedidos abiertos anteriores
        db.execute("""UPDATE orders SET status='cancelado', updated_at=datetime('now')
            WHERE user_id=? AND status='pendiente'""", (uid,))
        db.execute("""INSERT INTO orders (user_id, status, client_notes)
            VALUES (?, 'pendiente', ?)""", (uid, notes))
        db.commit()
    return jsonify({'ok': True})

# ─── ROUTES: ADMIN ────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    with get_db() as db:
        users = db.execute("""
            SELECT u.*, COUNT(DISTINCT s.id) as game_count,
                COALESCE(SUM(g.size_mb),0) as total_mb,
                (SELECT status FROM orders WHERE user_id=u.id ORDER BY id DESC LIMIT 1) as last_status,
                (SELECT client_notes FROM orders WHERE user_id=u.id ORDER BY id DESC LIMIT 1) as last_notes
            FROM users u
            LEFT JOIN selections s ON s.user_id=u.id
            LEFT JOIN games g ON g.id=s.game_id
            WHERE u.is_admin=0 GROUP BY u.id ORDER BY u.created_at DESC""").fetchall()
        pending_orders = db.execute(
            "SELECT COUNT(*) as c FROM orders WHERE status='pendiente'").fetchone()['c']
        total_games = db.execute(
            "SELECT COUNT(*) as c FROM games WHERE active=1").fetchone()['c']
        sgdb_key_set = bool(get_cfg('sgdb_api_key'))
    return render_template('admin_dashboard.html',
        users=users, pending_orders=pending_orders,
        total_games=total_games, sgdb_key_set=sgdb_key_set,
        using_default_key=not sgdb_key_set)

@app.route('/admin/usuario/<int:uid>')
@admin_required
def admin_user(uid):
    with get_db() as db:
        user   = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        sels   = db.execute("""SELECT g.* FROM selections s JOIN games g ON g.id=s.game_id
                             WHERE s.user_id=? ORDER BY g.display_name""", (uid,)).fetchall()
        orders = db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
        total_mb = db.execute("""SELECT COALESCE(SUM(g.size_mb),0) as t
            FROM selections s JOIN games g ON g.id=s.game_id
            WHERE s.user_id=?""", (uid,)).fetchone()['t']
    return render_template('admin_user.html', user=user, selections=sels,
                           orders=orders, total_mb=total_mb)

@app.route('/admin/crear_usuario', methods=['POST'])
@admin_required
def admin_create_user():
    u  = request.form.get('username','').strip()
    p  = request.form.get('password','').strip()
    n  = request.form.get('notes','').strip()
    sd = request.form.get('sd_size_mb','0').strip()
    if not u or not p: flash('Faltan datos', 'error'); return redirect(url_for('admin_dashboard'))
    try:
        with get_db() as db:
            db.execute("INSERT INTO users (username,password,notes,sd_size_mb) VALUES (?,?,?,?)",
                (u, generate_password_hash(p), n, int(sd) if sd.isdigit() else 0))
            db.commit()
        flash(f'Cliente "{u}" creado correctamente', 'success')
    except: flash(f'El usuario "{u}" ya existe', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/borrar_usuario/<int:uid>', methods=['POST'])
@admin_required
def admin_delete_user(uid):
    with get_db() as db:
        u = db.execute("SELECT username FROM users WHERE id=? AND is_admin=0", (uid,)).fetchone()
        if u:
            db.execute("DELETE FROM selections WHERE user_id=?", (uid,))
            db.execute("DELETE FROM orders WHERE user_id=?", (uid,))
            db.execute("DELETE FROM users WHERE id=?", (uid,))
            db.commit()
            flash('Cliente eliminado', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resetear/<int:uid>', methods=['POST'])
@admin_required
def admin_reset(uid):
    with get_db() as db:
        db.execute("DELETE FROM selections WHERE user_id=?", (uid,))
        db.execute("""UPDATE orders SET status='cancelado', updated_at=datetime('now')
            WHERE user_id=? AND status='pendiente'""", (uid,))
        db.commit()
    flash('Selección reiniciada', 'success')
    return redirect(url_for('admin_user', uid=uid))

@app.route('/admin/order_status/<int:oid>', methods=['POST'])
@admin_required
def admin_order_status(oid):
    status = request.form.get('status')
    notes  = request.form.get('admin_notes','').strip()
    valid  = ['pendiente','en_proceso','completado','cancelado']
    if status not in valid: flash('Estado inválido', 'error'); return redirect(url_for('admin_dashboard'))
    with get_db() as db:
        order = db.execute("SELECT user_id FROM orders WHERE id=?", (oid,)).fetchone()
        db.execute("""UPDATE orders SET status=?, admin_notes=?, updated_at=datetime('now')
            WHERE id=?""", (status, notes, oid))
        db.commit()
    flash('Pedido actualizado', 'success')
    return redirect(url_for('admin_user', uid=order['user_id']))

@app.route('/admin/cambiar_password/<int:uid>', methods=['POST'])
@admin_required
def admin_change_password(uid):
    p = request.form.get('new_password','').strip()
    if p:
        with get_db() as db:
            db.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(p), uid))
            db.commit()
        flash('Contraseña actualizada', 'success')
    return redirect(url_for('admin_user', uid=uid))

@app.route('/admin/update_sd/<int:uid>', methods=['POST'])
@admin_required
def admin_update_sd(uid):
    sd = request.form.get('sd_size_mb','0').strip()
    with get_db() as db:
        db.execute("UPDATE users SET sd_size_mb=? WHERE id=?",
            (int(sd) if sd.isdigit() else 0, uid))
        db.commit()
    flash('MicroSD actualizada', 'success')
    return redirect(url_for('admin_user', uid=uid))

@app.route('/admin/config', methods=['POST'])
@admin_required
def admin_config():
    key = request.form.get('sgdb_api_key','').strip()
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO config VALUES ('sgdb_api_key',?)", (key,))
        db.commit()
    flash('Configuración guardada', 'success')
    return redirect(url_for('admin_dashboard'))

# ─── ROUTES: ADMIN GAMES ──────────────────────────────────────────────────────

@app.route('/admin/juegos')
@admin_required
def admin_games():
    with get_db() as db:
        games = db.execute(
            "SELECT * FROM games ORDER BY display_name").fetchall()
    return render_template('admin_games.html', games=games)

@app.route('/admin/juegos/add', methods=['POST'])
@admin_required
def admin_add_game():
    name     = request.form.get('name','').strip()
    size_str = request.form.get('size_mb','0').strip()
    img      = request.form.get('image_url','').strip()
    if not name: flash('Nombre requerido', 'error'); return redirect(url_for('admin_games'))
    display  = clean_name_for_search(name) or name
    size_mb  = int(size_str) if size_str.isdigit() else 0
    if not img:
        img = fetch_sgdb_image(display)
    try:
        with get_db() as db:
            db.execute("""INSERT INTO games (name, display_name, size_mb, image_url)
                VALUES (?,?,?,?)""", (name, display, size_mb, img))
            db.commit()
        flash(f'"{display}" añadido correctamente', 'success')
    except: flash(f'"{name}" ya existe en el catálogo', 'error')
    return redirect(url_for('admin_games'))

@app.route('/admin/juegos/bulk', methods=['POST'])
@admin_required
def admin_bulk_add():
    raw   = request.form.get('bulk_names','')
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    added = skipped = 0
    for line in lines:
        display = clean_name_for_search(line) or line
        img = fetch_sgdb_image(display)
        try:
            with get_db() as db:
                db.execute("""INSERT INTO games (name, display_name, size_mb, image_url)
                    VALUES (?,?,0,?)""", (line, display, img))
                db.commit()
            added += 1
        except: skipped += 1
    flash(f'{added} juegos añadidos, {skipped} ya existían', 'success')
    return redirect(url_for('admin_games'))

@app.route('/admin/juegos/toggle/<int:gid>', methods=['POST'])
@admin_required
def admin_toggle_game(gid):
    with get_db() as db:
        g = db.execute("SELECT active FROM games WHERE id=?", (gid,)).fetchone()
        db.execute("UPDATE games SET active=? WHERE id=?", (0 if g['active'] else 1, gid))
        db.commit()
    return redirect(url_for('admin_games'))

@app.route('/admin/juegos/delete/<int:gid>', methods=['POST'])
@admin_required
def admin_delete_game(gid):
    with get_db() as db:
        db.execute("DELETE FROM selections WHERE game_id=?", (gid,))
        db.execute("DELETE FROM games WHERE id=?", (gid,))
        db.commit()
    flash('Juego eliminado', 'success')
    return redirect(url_for('admin_games'))

@app.route('/admin/juegos/edit/<int:gid>', methods=['POST'])
@admin_required
def admin_edit_game(gid):
    display  = request.form.get('display_name','').strip()
    size_str = request.form.get('size_mb','0').strip()
    img      = request.form.get('image_url','').strip()
    with get_db() as db:
        db.execute("""UPDATE games SET display_name=?, size_mb=?, image_url=? WHERE id=?""",
            (display, int(size_str) if size_str.isdigit() else 0, img, gid))
        db.commit()
    return jsonify({'ok': True})

@app.route('/admin/juegos/fetch_image/<int:gid>', methods=['POST'])
@admin_required
def admin_fetch_image(gid):
    with get_db() as db:
        g = db.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    if not g: return jsonify({'ok': False, 'msg': 'No encontrado'})
    url = fetch_sgdb_image(g['display_name'])
    if url:
        with get_db() as db:
            db.execute("UPDATE games SET image_url=? WHERE id=?", (url, gid))
            db.commit()
        return jsonify({'ok': True, 'url': url})
    return jsonify({'ok': False, 'msg': 'Sin imagen en SteamGridDB'})

@app.route('/admin/juegos/refetch_all', methods=['POST'])
@admin_required
def admin_refetch_all():
    with get_db() as db:
        pending = db.execute(
            "SELECT id, display_name FROM games WHERE image_url='' OR image_url IS NULL").fetchall()
    updated = 0
    for g in pending:
        url = fetch_sgdb_image(g['display_name'])
        with get_db() as db:
            db.execute("UPDATE games SET image_url=? WHERE id=?", (url, g['id']))
            db.commit()
        if url: updated += 1
    return jsonify({'ok': True, 'total': len(pending), 'updated': updated})

# ─── ROUTES: ADMIN PREVIEW ────────────────────────────────────────────────────

@app.route('/admin/preview')
@admin_required
def admin_preview():
    with get_db() as db:
        games = db.execute(
            "SELECT * FROM games WHERE active=1 ORDER BY display_name").fetchall()
    return render_template('admin_preview.html', games=games)

@app.route('/admin/update_game_image', methods=['POST'])
@admin_required
def admin_update_game_image():
    gid = request.json.get('game_id')
    url = request.json.get('url','').strip()
    with get_db() as db:
        db.execute("UPDATE games SET image_url=? WHERE id=?", (url, gid))
        db.commit()
    return jsonify({'ok': True})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
