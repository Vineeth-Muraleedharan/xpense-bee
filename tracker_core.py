"""Core logic for the finance tracker: SQLite storage, ledger, filters, reports, reminders.

Money rule: every amount is an integer in minor units (halalas for SAR, cents for USD).
Dates are ISO strings (YYYY-MM-DD). The Streamlit app only calls the functions here, so all
of it can be tested without a browser. The rules match the private offline app.
"""
from __future__ import annotations

import calendar
import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

BASE = "SAR"
CURRENCIES = ["SAR", "INR", "USD", "EUR", "GBP", "AED"]
# Starting-point rates (SAR per 1 unit). A real card or bank rate can be typed per entry.
DEFAULT_RATES = {"SAR": "1", "USD": "3.75", "INR": "0.045", "EUR": "4.10", "GBP": "4.80", "AED": "1.02"}

EXPENSE_CATEGORIES = ["EMI", "Loan", "Gym", "Shopping", "Rent", "Bills", "Education", "Subscription",
                      "Food", "Transport", "Health", "Travel", "Other"]
INCOME_CATEGORIES = ["Salary", "Freelance", "Others"]
MODES = ["Cash", "Debit card", "Credit card", "Bank transfer", "Other"]
REMINDER_TYPES = ["EMI", "Loan", "Rent", "Bill", "Subscription", "Other"]
LEAD_OPTIONS = {"At the set time": 0, "1 hour before": 60, "1 day before": 1440}

# Ranges match on the whole-unit part: 20.99 is in "0 - 20", 21.00 is in "21 - 50".
BUCKETS = [("0 - 20", 0, 20), ("21 - 50", 21, 50), ("51 - 100", 51, 100), ("101 - 500", 101, 500),
           ("501 - 2500", 501, 2500), ("2501 - 10000", 2501, 10000), ("10000+", 10001, float("inf"))]

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT, age INTEGER, sex TEXT, job TEXT,
    email TEXT, pw_salt TEXT, pw_hash TEXT, salary_minor INTEGER, provider TEXT);
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id = 1), opening_minor INTEGER NOT NULL,
    opening_date TEXT NOT NULL, credit_counts INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, type TEXT NOT NULL CHECK (type IN ('income','expense')),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0), currency TEXT NOT NULL, fx_rate TEXT NOT NULL,
    base_minor INTEGER NOT NULL CHECK (base_minor > 0), category TEXT NOT NULL, mode TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]', date TEXT NOT NULL, merchant TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, time TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL, amount_minor INTEGER, date TEXT NOT NULL,
    time TEXT NOT NULL, anchor_day INTEGER NOT NULL, repeat TEXT NOT NULL, lead_min INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '', done INTEGER NOT NULL DEFAULT 0
);
"""


# ---------- money and dates ----------

def to_minor(text) -> int | None:
    """'12.5' or '12,50' -> 1250. None when it is not a plain number of zero or more."""
    s = str(text).strip()
    s = s.replace(",", ".") if "," in s and "." not in s else s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite() or d < 0:
        return None
    return int((d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) * 100)


def fmt(minor: int) -> str:
    return f"{'-' if minor < 0 else ''}{abs(minor) / 100:,.2f}"


def convert(amount_minor: int, rate: Decimal) -> int:
    return int((Decimal(amount_minor) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def today() -> str:
    return date.today().isoformat()


def is_valid_date(s) -> bool:
    try:
        return date.fromisoformat(str(s)) is not None and len(str(s)) == 10
    except ValueError:
        return False


def is_valid_time(s) -> bool:
    try:
        return len(str(s)) == 5 and datetime.strptime(str(s), "%H:%M") is not None
    except ValueError:
        return False


def now_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def when(t: dict, with_year: bool = False) -> str:
    """Date and time of an entry the way a bank statement shows it, like '18 Oct 14:32'. Older entries have no time."""
    d = date.fromisoformat(t["date"]).strftime("%d %b %Y" if with_year else "%d %b")
    return f"{d} {t['time']}" if t.get("time") else d


def add_days(s: str, n: int) -> str:
    return (date.fromisoformat(s) + timedelta(days=n)).isoformat()


def add_months(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7]) - 1 + n
    return f"{y + m // 12:04d}-{m % 12 + 1:02d}"


def day_range(a: str, b: str) -> list[str]:
    out, d = [], a
    while d <= b:
        out.append(d)
        d = add_days(d, 1)
    return out


# ---------- storage ----------

def default_db_path() -> str:
    return os.environ.get("EXPENSE_DB", str(Path(__file__).parent / "data" / "finance.db"))


@contextmanager
def connect(db_path: str | None = None):
    path = db_path or default_db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(profile)")}
    for c, typ in (("email", "TEXT"), ("pw_salt", "TEXT"), ("pw_hash", "TEXT"), ("salary_minor", "INTEGER"), ("provider", "TEXT")):
        if c not in cols:
            conn.execute(f"ALTER TABLE profile ADD COLUMN {c} {typ}")
    if "time" not in {r[1] for r in conn.execute("PRAGMA table_info(transactions)")}:
        conn.execute("ALTER TABLE transactions ADD COLUMN time TEXT NOT NULL DEFAULT ''")      # older entries simply have no time
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_profile(conn) -> dict | None:
    r = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return dict(r) if r else None


def save_profile(conn, name: str, age: int | None, sex: str, job: str, salary_minor: int | None = None) -> None:
    """Create or update the profile. Email and password are untouched; salary is kept unless a value is passed."""
    if not name.strip():
        raise ValueError("Enter a name")
    if age is not None and not (1 <= age <= 120):
        raise ValueError("Age must be between 1 and 120")
    conn.execute("INSERT INTO profile(id, name, age, sex, job, salary_minor) VALUES (1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                 "name=excluded.name, age=excluded.age, sex=excluded.sex, job=excluded.job, "
                 "salary_minor=COALESCE(excluded.salary_minor, profile.salary_minor)",
                 (name.strip()[:60], age, sex, job.strip()[:60], salary_minor))


def create_account(conn, name: str, email: str, password: str | None = None, provider: str = "local") -> None:
    """Sign-up with only a name, email and password (or a Google identity). Everything else is filled in later under Settings.
    The balance starts at zero, counted from 1 January of this year so earlier entries this year are not ignored."""
    if not name.strip():
        raise ValueError("Enter a name")
    save_profile(conn, name, None, "", "")
    if provider == "local":
        set_credentials(conn, email, password or "")
    else:
        conn.execute("UPDATE profile SET email = ? WHERE id = 1", (email.strip().lower(),))
    conn.execute("UPDATE profile SET provider = ? WHERE id = 1", (provider,))
    save_settings(conn, 0, f"{date.today().year}-01-01", True)


def needs_sign_in(profile: dict | None) -> bool:
    """The demo profile has no account; a real profile (password or Google) must sign in."""
    return bool(profile and (has_password(profile) or profile.get("provider") == "google"))


def profile_incomplete(profile: dict) -> bool:
    return not (profile.get("age") and profile.get("job") and profile.get("salary_minor"))


def set_credentials(conn, email: str, password: str) -> None:
    """Store a salted PBKDF2 hash. This is a local sign-in for this computer, not encryption of the database file."""
    email = email.strip().lower()
    if "@" not in email or len(email) > 120:
        raise ValueError("Enter a valid email")
    if len(password) < 8:
        raise ValueError("Use a password of at least 8 characters")
    salt = os.urandom(16).hex()
    conn.execute("UPDATE profile SET email = ?, pw_salt = ?, pw_hash = ? WHERE id = 1", (email, salt, _hash(password, salt)))


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def has_password(profile: dict | None) -> bool:
    return bool(profile and profile.get("pw_hash"))


def verify_login(profile: dict, email: str, password: str) -> bool:
    if not has_password(profile):
        return True
    ok_email = hmac.compare_digest((profile.get("email") or "").lower(), email.strip().lower())
    ok_pw = hmac.compare_digest(_hash(password, profile["pw_salt"]), profile["pw_hash"])
    return ok_email and ok_pw


def get_settings(conn) -> dict | None:
    r = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return dict(r) if r else None


def save_settings(conn, opening_minor: int, opening_date: str, credit_counts: bool = True) -> None:
    if not is_valid_date(opening_date):
        raise ValueError("Choose a valid date")
    conn.execute("INSERT INTO settings(id, opening_minor, opening_date, credit_counts) VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                 "opening_minor=excluded.opening_minor, opening_date=excluded.opening_date, credit_counts=excluded.credit_counts",
                 (opening_minor, opening_date, 1 if credit_counts else 0))


def parse_tags(text: str) -> list[str]:
    seen: list[str] = []
    for t in str(text or "").replace("#", " ").replace(",", " ").split():
        t = t.lower()[:30]
        if t not in seen:
            seen.append(t)
    return seen[:10]


def add_txn(conn, *, type: str, amount: str, currency: str = BASE, fx_rate: str = "", category: str, mode: str = "Bank transfer",
            tags: str = "", on: str | None = None, merchant: str = "", note: str = "", txn_id: str | None = None,
            at: str | None = None) -> str:
    """Validate and save one income or expense. Raises ValueError with a message fit to show the user."""
    errors = []
    minor = to_minor(amount)
    if minor is None or minor <= 0:
        errors.append("Enter an amount greater than zero")
    on = on or today()
    if not is_valid_date(on):
        errors.append("Choose a valid date")
    at = now_hhmm() if at is None else at
    if at != "" and not is_valid_time(at):
        errors.append("Enter the time as HH:MM")
    if currency not in CURRENCIES:
        errors.append("Unknown currency")
    rate = Decimal(DEFAULT_RATES.get(currency, "1"))
    if currency != BASE and str(fx_rate).strip():
        try:
            rate = Decimal(str(fx_rate).strip())
            if rate <= 0:
                raise InvalidOperation
        except InvalidOperation:
            errors.append("Exchange rate must be a positive number")
    if type not in ("income", "expense"):
        errors.append("Unknown type")
    if errors:
        raise ValueError(". ".join(errors))
    base = convert(minor, rate)
    if base <= 0:
        raise ValueError("Amount is too small after conversion")
    tid = txn_id or uuid.uuid4().hex[:16]
    conn.execute(
        "INSERT INTO transactions(id,type,amount_minor,currency,fx_rate,base_minor,category,mode,tags,date,merchant,note,created_at,time) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET type=excluded.type, amount_minor=excluded.amount_minor, "
        "currency=excluded.currency, fx_rate=excluded.fx_rate, base_minor=excluded.base_minor, category=excluded.category, "
        "mode=excluded.mode, tags=excluded.tags, date=excluded.date, merchant=excluded.merchant, note=excluded.note, time=excluded.time",
        (tid, type, minor, currency, str(rate), base, category, mode if type == "expense" else "Bank transfer",
         json.dumps(parse_tags(tags)), on, merchant.strip()[:80], note.strip()[:200], datetime.now(timezone.utc).isoformat(), at))
    return tid


def delete_txn(conn, txn_id: str) -> None:
    conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))


def list_txns(conn) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM transactions"):
        d = dict(r)
        d["tags"] = json.loads(d["tags"])
        out.append(d)
    return out


def describe(t: dict) -> str:
    return t["category"] + (f" - {t['merchant']}" if t["merchant"] else "")


# ---------- ledger (statement) ----------

def effect(t: dict, settings: dict | None) -> int:
    if t["type"] == "income":
        return t["base_minor"]
    if t["mode"] == "Credit card" and settings and not settings.get("credit_counts", 1):
        return 0
    return -t["base_minor"]


def build_ledger(txns: list[dict], settings: dict) -> dict:
    """Rows from the opening-balance date onward, oldest first, each with a running balance."""
    opening, start = settings["opening_minor"], settings["opening_date"]
    rows_src = sorted((t for t in txns if t["date"] >= start), key=lambda t: (t["date"], t.get("time", ""), t["created_at"], t["id"]))
    bal, rows, credits, debits = opening, [], 0, 0
    for t in rows_src:
        e = effect(t, settings)
        bal += e
        credits += max(e, 0)
        debits += max(-e, 0)
        rows.append({"txn": t, "credit": t["base_minor"] if t["type"] == "income" else 0,
                     "debit": t["base_minor"] if t["type"] == "expense" else 0, "balance": bal,
                     "memo": t["type"] == "expense" and e == 0})
    return {"rows": rows, "opening": opening, "opening_date": start, "closing": bal, "credits": credits, "debits": debits}


def balance_now(txns, settings) -> int:
    return build_ledger(txns, settings)["closing"]


def statement(txns, settings, frm: str, to: str, kind: str = "all") -> dict:
    """Ledger rows inside [frm, to] plus the balance brought forward, like a bank statement."""
    led = build_ledger(txns, settings)
    frm = max(frm, settings["opening_date"])
    before = [r for r in led["rows"] if r["txn"]["date"] < frm]
    brought = before[-1]["balance"] if before else led["opening"]
    inside = [r for r in led["rows"] if frm <= r["txn"]["date"] <= to]
    return {"from": frm, "to": to, "brought": brought, "closing": inside[-1]["balance"] if inside else brought,
            "credits": sum(r["credit"] for r in inside), "debits": sum(r["debit"] for r in inside if not r["memo"]),
            "rows": [r for r in inside if kind == "all" or r["txn"]["type"] == kind],
            "opening_row": settings["opening_date"] if frm <= settings["opening_date"] <= to else None}


# ---------- filtering and reports ----------

def bucket_of(base_minor: int) -> str:
    whole = base_minor // 100
    for label, lo, hi in BUCKETS:
        if lo <= whole <= hi:
            return label
    return BUCKETS[-1][0]


def filter_sort(txns, *, type: str = "all", category: str | None = None, bucket: str | None = None, mode: str | None = None,
                text: str = "", frm: str | None = None, to: str | None = None, sort: str = "new") -> list[dict]:
    text = text.strip().lower()
    out = [t for t in txns
           if (type == "all" or t["type"] == type) and (not category or t["category"] == category)
           and (not bucket or bucket_of(t["base_minor"]) == bucket) and (not mode or t["mode"] == mode)
           and (not frm or t["date"] >= frm) and (not to or t["date"] <= to)
           and (not text or text in f"{t['merchant']} {t['note']} {' '.join(t['tags'])} {t['category']}".lower())]
    out.sort(key=lambda t: (t["date"], t.get("time", ""), t["created_at"]), reverse=True)
    if sort == "old":
        out.reverse()
    elif sort == "low":
        out.sort(key=lambda t: t["base_minor"])
    elif sort == "high":
        out.sort(key=lambda t: -t["base_minor"])
    elif sort == "category":
        out.sort(key=lambda t: t["category"].lower())
    return out


def totals(txns) -> dict:
    inc = sum(t["base_minor"] for t in txns if t["type"] == "income")
    exp = sum(t["base_minor"] for t in txns if t["type"] == "expense")
    return {"income": inc, "expense": exp, "net": inc - exp, "count": len(txns)}


def _group(txns, key):
    m: dict[str, int] = {}
    for t in txns:
        if t["type"] == "expense":
            m[t[key]] = m.get(t[key], 0) + t["base_minor"]
    return sorted(m.items(), key=lambda kv: -kv[1])


def by_category(txns):
    return _group(txns, "category")


def by_mode(txns):
    return _group(txns, "mode")


def by_day(txns, frm: str, to: str) -> list[dict]:
    m: dict[str, dict] = {}
    for t in txns:
        if frm <= t["date"] <= to:
            r = m.setdefault(t["date"], {"income": 0, "expense": 0})
            r[t["type"]] += t["base_minor"]
    return [{"date": d, **m.get(d, {"income": 0, "expense": 0})} for d in day_range(frm, to)]


def by_month(txns, frm: str, to: str) -> list[dict]:
    m: dict[str, dict] = {}
    for t in txns:
        if frm <= t["date"] <= to:
            r = m.setdefault(t["date"][:7], {"income": 0, "expense": 0})
            r[t["type"]] += t["base_minor"]
    out, k = [], frm[:7]
    while k <= to[:7]:
        out.append({"month": k, **m.get(k, {"income": 0, "expense": 0})})
        k = add_months(k, 1)
    return out


def histogram(txns, type: str = "expense") -> list[dict]:
    counts = {label: 0 for label, _, _ in BUCKETS}
    for t in txns:
        if t["type"] == type:
            counts[bucket_of(t["base_minor"])] += 1
    return [{"label": k, "count": v} for k, v in counts.items()]


def balance_series(txns, settings, frm: str, to: str) -> list[dict]:
    rows = build_ledger(txns, settings)["rows"]
    bal, i, out = settings["opening_minor"], 0, []
    while i < len(rows) and rows[i]["txn"]["date"] < frm:
        bal = rows[i]["balance"]
        i += 1
    for d in day_range(frm, to):
        while i < len(rows) and rows[i]["txn"]["date"] <= d:
            bal = rows[i]["balance"]
            i += 1
        out.append({"date": d, "balance": bal})
    return out


PERIODS = ["This month", "Last month", "Last 3 months", "Last 6 months", "Last 12 months", "All time"]


def period_range(preset: str, txns, on: str | None = None) -> tuple[str, str]:
    t = on or today()
    ym = t[:7]
    first = lambda mk: mk + "-01"
    last = lambda mk: f"{mk}-{calendar.monthrange(int(mk[:4]), int(mk[5:7]))[1]:02d}"
    if preset == "Last month":
        lm = add_months(ym, -1)
        return first(lm), last(lm)
    if preset == "Last 3 months":
        return first(add_months(ym, -2)), t
    if preset == "Last 6 months":
        return first(add_months(ym, -5)), t
    if preset == "Last 12 months":
        return first(add_months(ym, -11)), t
    if preset == "All time":
        return (min((x["date"] for x in txns), default=first(ym)), t)
    return first(ym), t


def months_with_expenses(txns) -> list[str]:
    return sorted({t["date"][:7] for t in txns if t["type"] == "expense"}, reverse=True)


def compare_months(txns, months: list[str]) -> dict:
    """Expense totals per category for each chosen month, oldest month first, for side-by-side comparison."""
    months = sorted(set(months))
    cat: dict[str, dict[str, int]] = {}
    tot = {m: 0 for m in months}
    for t in txns:
        m = t["date"][:7]
        if t["type"] == "expense" and m in tot:
            tot[m] += t["base_minor"]
            row = cat.setdefault(t["category"], {k: 0 for k in months})
            row[m] += t["base_minor"]
    rows = sorted(({"category": c, "by_month": v, "total": sum(v.values())} for c, v in cat.items()), key=lambda r: -r["total"])
    change = None
    if len(months) >= 2:
        a, b = months[-2], months[-1]
        change = {"from": a, "to": b, "diff": tot[b] - tot[a], "pct": ((tot[b] - tot[a]) / tot[a] * 100) if tot[a] else None}
    return {"months": months, "totals": tot, "categories": rows, "change": change}


def insight(txns, settings, frm: str, to: str) -> dict:
    inside = [t for t in txns if frm <= t["date"] <= to]
    tot = totals(inside)
    days = len(day_range(frm, to))
    cats = by_category(inside)
    return {"from": frm, "to": to, "txns": inside, "totals": tot, "avg_per_day": tot["expense"] // days if days else 0,
            "top": cats[0] if cats else None, "daily": by_day(inside, frm, to), "monthly": by_month(inside, frm, to),
            "balance": balance_series(txns, settings, frm, to), "categories": cats, "modes": by_mode(inside),
            "histogram": histogram(inside)}


# ---------- payment reminders ----------

def _date_in_month(month: str, anchor: int) -> str:
    return f"{month}-{min(anchor, calendar.monthrange(int(month[:4]), int(month[5:7]))[1]):02d}"


def next_monthly(d: str, anchor: int | None = None) -> str:
    return _date_in_month(add_months(d[:7], 1), anchor or int(d[8:10]))


def add_reminder(conn, *, title: str, type: str, amount: str, on: str, time: str, repeat: str = "monthly",
                 lead_min: int = 0, notes: str = "", rid: str | None = None) -> str:
    errors = []
    if not title.strip():
        errors.append("Give the reminder a name")
    if not is_valid_date(on):
        errors.append("Choose a valid date")
    if not (len(time) == 5 and time[2] == ":" and time[:2].isdigit() and time[3:].isdigit() and int(time[:2]) < 24 and int(time[3:]) < 60):
        errors.append("Choose a time")
    minor = None
    if str(amount).strip():
        minor = to_minor(amount)
        if minor is None:
            errors.append("Amount must be a number, like 1200.00")
    if errors:
        raise ValueError(". ".join(errors))
    rid = rid or uuid.uuid4().hex[:16]
    conn.execute("INSERT INTO reminders(id,title,type,amount_minor,date,time,anchor_day,repeat,lead_min,notes,done) VALUES (?,?,?,?,?,?,?,?,?,?,0) "
                 "ON CONFLICT(id) DO UPDATE SET title=excluded.title, type=excluded.type, amount_minor=excluded.amount_minor, date=excluded.date, "
                 "time=excluded.time, anchor_day=excluded.anchor_day, repeat=excluded.repeat, lead_min=excluded.lead_min, notes=excluded.notes",
                 (rid, title.strip()[:80], type, minor, on, time, int(on[8:10]), "monthly" if repeat == "monthly" else "none",
                  lead_min if lead_min in (0, 60, 1440) else 0, notes.strip()[:200]))
    return rid


def list_reminders(conn, include_done: bool = False) -> list[dict]:
    rows = conn.execute("SELECT * FROM reminders" + ("" if include_done else " WHERE done = 0") + " ORDER BY date, time").fetchall()
    return [dict(r) for r in rows]


def delete_reminder(conn, rid: str) -> None:
    conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))


def mark_paid(conn, rid: str) -> None:
    r = conn.execute("SELECT * FROM reminders WHERE id = ?", (rid,)).fetchone()
    if not r:
        return
    if r["repeat"] == "monthly":
        conn.execute("UPDATE reminders SET date = ? WHERE id = ?", (next_monthly(r["date"], r["anchor_day"]), rid))
    else:
        conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))


def reminder_status(r: dict, now: datetime | None = None) -> str:
    n = now or datetime.now()
    nd, nt = n.date().isoformat(), n.strftime("%H:%M")
    if r["done"]:
        return "done"
    if r["date"] < nd or (r["date"] == nd and r["time"] < nt):
        return "overdue"
    if r["date"] == nd:
        return "today"
    return "soon" if (date.fromisoformat(r["date"]) - date.fromisoformat(nd)).days <= 3 else "upcoming"


def occurrences(r: dict, frm: str, to: str) -> list[str]:
    if r["done"]:
        return []
    if r["repeat"] != "monthly":
        return [r["date"]] if frm <= r["date"] <= to else []
    out, d, guard = [], r["date"], 0
    while d <= to and guard < 600:
        if d >= frm:
            out.append(d)
        d, guard = next_monthly(d, r["anchor_day"]), guard + 1
    return out


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    out, rest = [], line
    while len(rest) > 70:
        out.append(rest[:70])
        rest = " " + rest[70:]
    out.append(rest)
    return "\r\n".join(out)


def build_ics(reminders: list[dict], now: datetime | None = None) -> str:
    """iCalendar text with floating local times, monthly repeats and an alarm per reminder."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Personal Finance//Reminders//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for r in reminders:
        if r["done"]:
            continue
        start = datetime.fromisoformat(f"{r['date']}T{r['time']}")
        end = start + timedelta(minutes=30)
        summary = f"{r['type']}: {r['title']}" + (f" ({fmt(r['amount_minor'])} {BASE})" if r["amount_minor"] else "")
        lines += ["BEGIN:VEVENT", f"UID:{r['id']}@personal-finance", f"DTSTAMP:{stamp}", f"DTSTART:{start:%Y%m%dT%H%M%S}",
                  f"DTEND:{end:%Y%m%dT%H%M%S}", "SUMMARY:" + _ics_escape(summary)]
        if r["notes"]:
            lines.append("DESCRIPTION:" + _ics_escape(r["notes"]))
        if r["repeat"] == "monthly":
            a = r["anchor_day"]
            lines.append(f"RRULE:FREQ=MONTHLY;BYMONTHDAY={a}" if a <= 28 else "RRULE:FREQ=MONTHLY;BYMONTHDAY=28,29,30,31;BYSETPOS=-1")
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + _ics_escape(summary),
                  "TRIGGER:" + (f"-PT{r['lead_min']}M" if r["lead_min"] else "PT0S"), "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(x) for x in lines) + "\r\n"