"""ShipIQ authentication and role-based access control helpers.
Uses additive SQLite tables in the existing ShipIQ database; never rewrites shipment rows.
"""
import hashlib
import hmac
import os
import sqlite3
import time
from datetime import datetime, timezone

ROLES = ("Admin", "Analyst", "Viewer")
PBKDF2_ROUNDS = 310_000

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _connect(db_path):
    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def init_auth_db(db_path):
    """Create only auth-related tables in the existing database."""
    with _connect(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS shipiq_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Admin','Analyst','Viewer')),
            is_active INTEGER NOT NULL DEFAULT 1,
            is_primary_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_login TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS shipiq_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER, action TEXT NOT NULL, target_user_id INTEGER,
            details TEXT, created_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shipiq_users_email ON shipiq_users(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shipiq_audit_created ON shipiq_audit_logs(created_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS shipiq_login_attempts (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            failures INTEGER NOT NULL DEFAULT 0,
            window_start REAL NOT NULL,
            locked_until REAL NOT NULL DEFAULT 0
        )""")

def _hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return "pbkdf2_sha256$" + str(PBKDF2_ROUNDS) + "$" + salt.hex() + "$" + digest.hex()

def _verify_password(password, encoded):
    try:
        scheme, rounds, salt_hex, digest_hex = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def _audit(conn, actor_user_id, action, target_user_id=None, details=""):
    conn.execute("INSERT INTO shipiq_audit_logs(actor_user_id,action,target_user_id,details,created_at) VALUES(?,?,?,?,?)",
                 (actor_user_id, action, target_user_id, details[:500], _now()))

def _public_user(row):
    if row is None:
        return None
    d = dict(row)
    d.pop("password_hash", None)
    d["is_active"] = bool(d.get("is_active"))
    d["is_primary_admin"] = bool(d.get("is_primary_admin"))
    return d

def user_count(db_path):
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM shipiq_users").fetchone()[0]

def register_user(db_path, full_name, email, password):
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if len(full_name) < 2:
        return False, "Enter your full name.", None
    if len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
        return False, "Enter a valid email address.", None
    if len(password or "") < 10:
        return False, "Password must be at least 10 characters.", None
    init_auth_db(db_path)
    encoded = _hash_password(password)
    try:
        with _connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute("SELECT COUNT(*) FROM shipiq_users").fetchone()[0]
            role = "Admin" if count == 0 else "Viewer"
            primary = 1 if count == 0 else 0
            cur = conn.execute("INSERT INTO shipiq_users(full_name,email,password_hash,role,is_active,is_primary_admin,created_at,updated_at) VALUES(?,?,?,?,1,?,?,?)",
                               (full_name, email, encoded, role, primary, _now(), _now()))
            uid = cur.lastrowid
            _audit(conn, uid, "first_admin_registered" if primary else "self_registered", uid, "role=" + role)
            row = conn.execute("SELECT * FROM shipiq_users WHERE id=?", (uid,)).fetchone()
            return True, "Account created.", _public_user(row)
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists.", None

def authenticate(db_path, email, password):
    init_auth_db(db_path)
    email = (email or "").strip().lower()[:254]
    now_epoch = time.time()
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        attempt = conn.execute("SELECT failures,window_start,locked_until FROM shipiq_login_attempts WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if attempt and attempt["locked_until"] > now_epoch:
            return None, "Too many failed sign-in attempts. Try again in about 15 minutes."
        if attempt and now_epoch - attempt["window_start"] > 900:
            conn.execute("DELETE FROM shipiq_login_attempts WHERE email=? COLLATE NOCASE", (email,))
            attempt = None
        row = conn.execute("SELECT * FROM shipiq_users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        valid = False
        if row is not None:
            valid = bool(row["is_active"]) and _verify_password(password or "", row["password_hash"])
        else:
            # A dummy hash check for unknown addresses reduces obvious timing differences.
            _verify_password(password or "", "pbkdf2_sha256$310000$00000000000000000000000000000000$" + ("0" * 64))
        if not valid:
            failures = int(attempt["failures"]) + 1 if attempt else 1
            window_start = float(attempt["window_start"]) if attempt else now_epoch
            locked_until = now_epoch + 900 if failures >= 5 else 0
            conn.execute("INSERT INTO shipiq_login_attempts(email,failures,window_start,locked_until) VALUES(?,?,?,?) ON CONFLICT(email) DO UPDATE SET failures=excluded.failures,window_start=excluded.window_start,locked_until=excluded.locked_until",
                         (email, failures, window_start, locked_until))
            return None, "Email or password is incorrect."
        conn.execute("DELETE FROM shipiq_login_attempts WHERE email=? COLLATE NOCASE", (email,))
        now = _now()
        conn.execute("UPDATE shipiq_users SET last_login=?, updated_at=? WHERE id=?", (now, now, row["id"]))
        _audit(conn, row["id"], "login", row["id"])
        fresh = conn.execute("SELECT * FROM shipiq_users WHERE id=?", (row["id"],)).fetchone()
        return _public_user(fresh), None

def list_users(db_path):
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT id,full_name,email,role,is_active,is_primary_admin,created_at,updated_at,last_login FROM shipiq_users ORDER BY is_primary_admin DESC, full_name COLLATE NOCASE")]

def list_audit_logs(db_path, limit=100):
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        return [dict(r) for r in conn.execute("""SELECT a.id,a.action,a.target_user_id,a.details,a.created_at,u.email AS actor_email
            FROM shipiq_audit_logs a LEFT JOIN shipiq_users u ON u.id=a.actor_user_id
            ORDER BY a.id DESC LIMIT ?""", (max(1, min(int(limit), 500)),))]

def _actor_is_admin(conn, actor_id):
    row = conn.execute("SELECT role,is_active FROM shipiq_users WHERE id=?", (actor_id,)).fetchone()
    return bool(row and row["is_active"] and row["role"] == "Admin")

def admin_create_user(db_path, actor_id, full_name, email, password, role):
    if role not in ROLES:
        return False, "Choose a valid role."
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if len(full_name) < 2 or "@" not in email or len(password or "") < 10:
        return False, "Check the name, email, and password (minimum 10 characters)."
    init_auth_db(db_path)
    try:
        with _connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not _actor_is_admin(conn, actor_id):
                return False, "Admin permission required."
            cur = conn.execute("INSERT INTO shipiq_users(full_name,email,password_hash,role,is_active,is_primary_admin,created_at,updated_at) VALUES(?,?,?,?,1,0,?,?)",
                               (full_name, email, _hash_password(password), role, _now(), _now()))
            _audit(conn, actor_id, "admin_created_user", cur.lastrowid, "role=" + role)
            return True, "User created."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."

def admin_update_user(db_path, actor_id, target_id, role=None, is_active=None, full_name=None):
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not _actor_is_admin(conn, actor_id):
            return False, "Admin permission required."
        target = conn.execute("SELECT * FROM shipiq_users WHERE id=?", (int(target_id),)).fetchone()
        if not target:
            return False, "User not found."
        new_role = role if role is not None else target["role"]
        new_active = int(bool(is_active)) if is_active is not None else int(target["is_active"])
        new_name = (full_name or target["full_name"]).strip()
        if new_role not in ROLES or len(new_name) < 2:
            return False, "Invalid role or name."
        if target["is_primary_admin"] and (new_role != "Admin" or not new_active):
            return False, "Transfer primary Admin ownership before changing or deactivating this account."
        if target["role"] == "Admin" and target["is_active"] and (new_role != "Admin" or not new_active):
            active_admins = conn.execute("SELECT COUNT(*) FROM shipiq_users WHERE role='Admin' AND is_active=1").fetchone()[0]
            if active_admins <= 1:
                return False, "The last active Admin cannot be demoted or deactivated."
        conn.execute("UPDATE shipiq_users SET role=?,is_active=?,full_name=?,updated_at=? WHERE id=?",
                     (new_role, new_active, new_name, _now(), int(target_id)))
        _audit(conn, actor_id, "admin_updated_user", int(target_id),
               "role=" + new_role + ";active=" + str(new_active) + ";name_changed=" + str(new_name != target["full_name"]))
        return True, "User updated."

def admin_delete_user(db_path, actor_id, target_id):
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not _actor_is_admin(conn, actor_id):
            return False, "Admin permission required."
        target = conn.execute("SELECT * FROM shipiq_users WHERE id=?", (int(target_id),)).fetchone()
        if not target:
            return False, "User not found."
        if target["is_primary_admin"]:
            return False, "Transfer primary Admin ownership before deleting this account."
        if target["role"] == "Admin" and target["is_active"]:
            n = conn.execute("SELECT COUNT(*) FROM shipiq_users WHERE role='Admin' AND is_active=1").fetchone()[0]
            if n <= 1:
                return False, "The last active Admin cannot be deleted."
        _audit(conn, actor_id, "admin_deleted_user", int(target_id), "email=" + target["email"])
        conn.execute("DELETE FROM shipiq_users WHERE id=?", (int(target_id),))
        return True, "User deleted."

def transfer_primary_admin(db_path, actor_id, target_id, actor_password):
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        actor = conn.execute("SELECT * FROM shipiq_users WHERE id=?", (int(actor_id),)).fetchone()
        target = conn.execute("SELECT * FROM shipiq_users WHERE id=?", (int(target_id),)).fetchone()
        if not actor or not actor["is_active"] or actor["role"] != "Admin":
            return False, "Admin permission required."
        if not _verify_password(actor_password or "", actor["password_hash"]):
            return False, "Password confirmation failed."
        if not target or not target["is_active"] or target["role"] != "Admin":
            return False, "Choose another active Admin account."
        if int(actor_id) == int(target_id):
            return False, "Choose a different Admin account."
        conn.execute("UPDATE shipiq_users SET is_primary_admin=0,updated_at=? WHERE is_primary_admin=1", (_now(),))
        conn.execute("UPDATE shipiq_users SET is_primary_admin=1,updated_at=? WHERE id=?", (_now(), int(target_id)))
        _audit(conn, actor_id, "transferred_primary_admin", int(target_id), "ownership transferred with password confirmation")
        return True, "Primary Admin ownership transferred. Your Admin role remains unchanged."

def change_own_password(db_path, user_id, current_password, new_password):
    if len(new_password or "") < 10:
        return False, "New password must be at least 10 characters."
    init_auth_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM shipiq_users WHERE id=? AND is_active=1", (int(user_id),)).fetchone()
        if not row or not _verify_password(current_password or "", row["password_hash"]):
            return False, "Current password is incorrect."
        conn.execute("UPDATE shipiq_users SET password_hash=?,updated_at=? WHERE id=?", (_hash_password(new_password), _now(), int(user_id)))
        _audit(conn, user_id, "changed_own_password", user_id)
        return True, "Password changed."
