"""Xpense Bee, a personal finance tracker (Streamlit). Run with: streamlit run app.py

Same ideas as the private phone app: a card on Home, quick expense icons, statement with running balance,
insight charts, calendar with payment reminders, PDF and .ics downloads. Demo data only; nothing leaves your machine.
"""
from __future__ import annotations

import base64
import calendar
from pathlib import Path
from datetime import date, datetime, time as dtime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import pdf_export
import sample_data
import tracker_core as core

st.set_page_config(page_title="Xpense Bee", page_icon=str(Path(__file__).parent / "assets" / "logo.png"), layout="centered")

ICONS = {"EMI": "🗓️", "Loan": "🏦", "Gym": "🏋️", "Shopping": "🛍️", "Rent": "🏠", "Bills": "🧾", "Education": "🎓", "Subscription": "🔁",
         "Food": "🍽️", "Transport": "🚗", "Health": "💊", "Travel": "✈️", "Other": "•", "Salary": "💼", "Freelance": "💻", "Others": "•"}
PALETTE = ["#d8b76a", "#5fd3a8", "#f28b7b", "#6fb1e0", "#b79cf0", "#e6a15c", "#7fd0d6", "#d98fb8"]
SORTS = {"Newest first": "new", "Oldest first": "old", "Amount: low to high": "low", "Amount: high to low": "high", "By category": "category"}
PAGES = ["Home", "Expense", "Insight", "Statement", "Settings"]
NAV_ICONS = {"Home": "home", "Expense": "account_balance_wallet", "Insight": "insights", "Statement": "receipt_long", "Settings": "tune"}

ASSETS = Path(__file__).parent / "assets"


def _b64(name: str) -> str:
    return base64.b64encode((ASSETS / name).read_bytes()).decode()


CSS = """
<style>
.stApp {background: #000 !important;}
.stApp::before {content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none; background: url("data:image/svg+xml;base64,__HIVEBG__") center top / 42px 72.746px;
  -webkit-mask-image: linear-gradient(180deg,#000 0%,rgba(0,0,0,.35) 60%,transparent 100%); mask-image: linear-gradient(180deg,#000 0%,rgba(0,0,0,.35) 60%,transparent 100%);}
[data-testid=stHeader] {background: transparent !important;}
.stApp::after {content: ""; position: fixed; inset: 0; z-index: 100000; pointer-events: none; border: 3px solid #f4ff2e; border-radius: 10px;
  box-shadow: inset 0 0 12px rgba(244,255,46,.55), 0 0 12px rgba(244,255,46,.55);}
.st-key-authcard {position: relative; isolation: isolate; overflow: hidden; padding: 18px 20px 12px; border-radius: 22px; background: linear-gradient(135deg,#0b3f35 0%,#061a17 55%,#020605 100%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.10), 0 22px 40px -20px rgba(0,0,0,.9), 0 0 0 1px rgba(216,183,106,.28);}
.st-key-authcard::before {content: ""; position: absolute; top: 0; right: 0; bottom: 0; width: 82%; z-index: -1; pointer-events: none; opacity: .55;
  background: url("data:image/svg+xml;base64,__HIVECARD__") right center / auto 118% no-repeat;
  -webkit-mask-image: linear-gradient(to left,#000 8%,transparent 92%); mask-image: linear-gradient(to left,#000 8%,transparent 92%);}
.st-key-authcard .chipbar {display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; font: 600 1rem 'Iowan Old Style',Georgia,serif; letter-spacing: .06em; color: #f6f1e2;}
.st-key-authcard .chip {width: 44px; height: 33px; border-radius: 7px; border: 1px solid rgba(60,40,5,.45);
  background: linear-gradient(90deg,transparent 31%,rgba(60,40,5,.35) 31% 33%,transparent 33% 66%,rgba(60,40,5,.35) 66% 68%,transparent 68%), linear-gradient(135deg,#f1dc9b,#c9a24f 55%,#e6cb83);}
.stApp button[kind=primary], .stApp button[kind=primaryFormSubmit] {color: #1b1405 !important;} .stApp button[kind=primary] p, .stApp button[kind=primaryFormSubmit] p {color: #1b1405 !important;}
.stApp .st-key-bottomnav button[kind=primary], .stApp .st-key-bottomnav button[kind=primary] p {color: #d8b76a !important;}
.st-key-cmp [data-testid=stHorizontalBlock] {flex-direction: row !important; flex-wrap: nowrap; gap: .5rem;} .st-key-cmp [data-testid=stColumn] {min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;}
.or {display: flex; align-items: center; gap: 10px; color: #9aa19d; font-size: .8rem; margin: .5rem 0;}
.or::before, .or::after {content: ""; flex: 1; height: 1px; background: #3a3a3a;}
.st-key-upcoming {padding: 12px 16px 6px; margin: 0 0 1rem; border-radius: 16px; background: linear-gradient(135deg, rgba(244,255,46,.10), rgba(212,175,90,.07)); border: 1px solid rgba(244,255,46,.55); border-left: 5px solid #f4ff2e; box-shadow: 0 0 18px -6px rgba(244,255,46,.45);}
.st-key-upcoming h3 {margin-top: 0; padding-top: 0; font-size: 1.3rem;}
.st-key-upcoming .line:last-child {border-bottom: 0;}
.st-key-account, .st-key-nudge {padding: 10px 14px; margin: 0 0 .8rem; border-radius: 14px; background: #0e0e0e; border: 1px solid #262626;}
.st-key-account [data-testid=stHorizontalBlock], .st-key-nudge [data-testid=stHorizontalBlock] {flex-direction: row !important; flex-wrap: nowrap; align-items: center;}
.st-key-account [data-testid=stColumn]:first-child, .st-key-nudge [data-testid=stColumn]:first-child {flex: 1 1 0 !important; width: auto !important; min-width: 0 !important;}
.st-key-account [data-testid=stColumn]:last-child, .st-key-nudge [data-testid=stColumn]:last-child {flex: 0 0 auto !important; width: auto !important; min-width: 0 !important;}
.block-container {position: relative; z-index: 1;}
.block-container {max-width: 560px; padding-top: 3.6rem; padding-bottom: 7rem;}
.st-key-bottomnav {position: fixed; bottom: 0; left: 50%; right: auto; transform: translateX(-50%); width: min(560px, 100%); z-index: 999; padding: .5rem .6rem .8rem;
  background: rgba(0,0,0,.96); border-top: 1px solid #3a3320; border-radius: 20px 20px 0 0; box-shadow: 0 -12px 30px -12px rgba(0,0,0,.9); backdrop-filter: blur(10px);}
.st-key-bottomnav [data-testid=stHorizontalBlock] {flex-direction: row !important; flex-wrap: nowrap !important; gap: 4px !important;}
.st-key-bottomnav [data-testid=stColumn] {min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;}
.st-key-bottomnav button {width: 100% !important; min-height: 3rem; border-radius: 14px !important; border: 0 !important; background: transparent !important; color: #cfd6d2 !important; padding: .4rem .2rem !important;}
.st-key-bottomnav [data-testid=stColumn]:has(button[kind=primary]) {flex: 2.1 1 0 !important;}
.st-key-bottomnav button[kind=primary] {background: rgba(216,183,106,.18) !important; color: #d8b76a !important;}
.st-key-bottomnav button p {font-size: .74rem; white-space: nowrap;}
.st-key-bottomnav button span[data-testid=stIconMaterial] {font-size: 1.5rem !important;}
.st-key-quick [data-testid=stHorizontalBlock] {flex-direction: row !important; flex-wrap: nowrap; gap: .4rem;}
.st-key-quick [data-testid=stColumn] {min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;}
.st-key-quick button {padding: .4rem .1rem; min-height: 4.2rem;}
.st-key-quick button p {font-size: .74rem; white-space: nowrap;}
.mhead {display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; padding: 8px 10px; margin-top: 14px; background: #0e0e0e; border-top: 1px solid #d8b76a; border-bottom: 1px solid #262626;}
.mhead .m {font: 600 1rem Georgia,serif; color: #d8b76a;} .mhead .s {font: 600 .84rem Georgia,serif;}
h1, h2, h3 {font-family: 'Iowan Old Style','Palatino Linotype',Georgia,serif; letter-spacing: .005em;}
.atm {position: relative; isolation: isolate; min-height: 250px; padding: 18px 20px; border-radius: 22px; color: #f6f1e2; overflow: hidden;
  background: linear-gradient(135deg,#0d0d0d 0%,#050505 55%,#000 100%); border: 1px solid rgba(255,255,255,.85);
  box-shadow: 0 22px 40px -20px rgba(0,0,0,.9);
  display: flex; flex-direction: column; justify-content: space-between; gap: 12px;}
.atm::before {content: ""; position: absolute; top: 0; right: 0; bottom: 0; width: 82%; z-index: -1; pointer-events: none;
  background: url("data:image/svg+xml;base64,__HIVECARD__") right center / auto 118% no-repeat;
  -webkit-mask-image: linear-gradient(to left,#000 8%,transparent 92%); mask-image: linear-gradient(to left,#000 8%,transparent 92%);}
.atm::after {content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none; background: radial-gradient(70% 90% at 100% 0%, rgba(242,193,78,.10), transparent 60%);}
.atm .top {display: flex; align-items: center; justify-content: space-between;}
.atm .brand {display: flex; align-items: center; gap: 8px; font: 600 1.02rem 'Iowan Old Style','Palatino Linotype',Georgia,serif; letter-spacing: .05em; color: #f6f1e2;}
.atm .bee {width: 40px; height: 40px; display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,.5));}
.atm .stats {display: grid; grid-template-columns: 1fr 1fr; gap: 10px;}
.atm .stat {display: flex; align-items: center; gap: 9px; min-width: 0;}
.atm .stat .dot {flex: none; width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: .95rem; line-height: 1;}
.atm .stat.inc .dot {background: rgba(95,211,168,.2); color: #5fd3a8;} .atm .stat.exp .dot {background: rgba(242,139,123,.2); color: #f28b7b;}
.atm .stat .lab {font-size: .72rem; color: rgba(246,241,226,.7);}
.atm .stat .val {font: 600 .98rem/1.2 'Iowan Old Style','Palatino Linotype',Georgia,serif; font-variant-numeric: lining-nums tabular-nums;}
.atm .chip {width: 44px; height: 33px; border-radius: 7px; border: 1px solid rgba(60,40,5,.45);
  background: linear-gradient(90deg,transparent 31%,rgba(60,40,5,.35) 31% 33%,transparent 33% 66%,rgba(60,40,5,.35) 66% 68%,transparent 68%),
  linear-gradient(135deg,#f1dc9b,#c9a24f 55%,#e6cb83);}
.atm .label {font-size: .84rem; color: rgba(246,241,226,.78);}
.atm .bal {font: 600 2.1rem/1.15 'Iowan Old Style','Palatino Linotype',Georgia,serif; font-variant-numeric: lining-nums tabular-nums; letter-spacing: .02em;}
.atm .cur {font-size: .95rem; font-weight: 500; opacity: .8;}
.atm .name {font: 600 1.08rem/1.25 'Iowan Old Style','Palatino Linotype',Georgia,serif; letter-spacing: .03em;}
.atm .sub {font-size: .84rem; color: rgba(246,241,226,.78);}
.st-key-cardbar {margin-top: .6rem;}
.st-key-cardbar [data-testid=stHorizontalBlock], .st-key-calnav [data-testid=stHorizontalBlock], .st-key-pagehead [data-testid=stHorizontalBlock] {flex-direction: row !important; flex-wrap: nowrap;}
.st-key-cardbar [data-testid=stColumn], .st-key-calnav [data-testid=stColumn], .st-key-pagehead [data-testid=stColumn] {min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;}
.st-key-pagehead [data-testid=stColumn]:last-child {flex: 0 0 auto !important;}
.st-key-calnav [data-testid=stColumn]:nth-child(2) {flex: 3 1 0 !important;}
.st-key-cardbar button {border-radius: 999px;}
.figure {font: 600 1.35rem/1.3 Georgia,serif; font-variant-numeric: lining-nums tabular-nums;}
.pos {color: #5fd3a8;} .neg {color: #f28b7b;} .muted {color: #8aa7a2; font-size: .86rem;}
.line {display: flex; justify-content: space-between; gap: 12px; padding: 9px 2px; border-bottom: 1px solid #262626;}
.line .t {display: block;} .line .s {display: block; color: #8aa7a2; font-size: .82rem;}
.line .a {font: 600 1rem Georgia,serif; white-space: nowrap;}
.calgrid {display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; text-align: center;}
.calgrid .dow {color: #8aa7a2; font-size: .78rem; padding: 4px 0;}
.calgrid .d {padding: 8px 0 4px; border-radius: 10px; font-variant-numeric: tabular-nums;}
.calgrid .d.out {opacity: .3;} .calgrid .d.today {box-shadow: inset 0 0 0 1px #d8b76a;} .calgrid .d.sel {background: #181818;}
.dot {display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin: 0 1px;}
.dot.r {background: #d8b76a;} .dot.e {background: #f28b7b;} .dot.i {background: #5fd3a8;}
</style>
"""
st.markdown(CSS.replace("__HIVEBG__", _b64("hive-bg.svg")).replace("__HIVECARD__", _b64("hive-card.svg")), unsafe_allow_html=True)


# ---------- helpers ----------

def money(minor: int, sign: bool = False) -> str:
    return ("+" if sign and minor > 0 else "") + core.fmt(minor)


def mask(text: str) -> str:
    return "•••••" if st.session_state.get("hide", True) else text


def line(title: str, sub: str, amount: str, cls: str = "") -> str:
    return f'<div class="line"><span><span class="t">{title}</span><span class="s">{sub}</span></span><span class="a {cls}">{amount}</span></div>'


def rel_day(iso: str) -> str:
    d = (date.fromisoformat(iso) - date.today()).days
    return {0: "Today", 1: "Tomorrow", -1: "Yesterday"}.get(d, date.fromisoformat(iso).strftime("%d %b %Y"))


def due_text(r: dict) -> str:
    s = core.reminder_status(r)
    return f"Overdue since {r['date']}" if s == "overdue" else f"{rel_day(r['date'])}, {r['time']}"


def txn_form(key: str, kind: str, txn: dict | None = None, default_category: str | None = None):
    """Shared income/expense form. Returns True after a successful save."""
    cats = core.INCOME_CATEGORIES if kind == "income" else core.EXPENSE_CATEGORIES
    cat0 = (txn or {}).get("category") or default_category or cats[0]
    with st.form(key, clear_on_submit=txn is None, border=False):
        c1, c2 = st.columns([3, 1])
        amount = c1.text_input("Amount", value=core.fmt((txn or {}).get("amount_minor", 0)).replace(",", "") if txn else "", placeholder="0.00")
        currency = c2.selectbox("Currency", core.CURRENCIES, index=core.CURRENCIES.index((txn or {}).get("currency", core.BASE)))
        fx = st.text_input("Exchange rate (SAR per 1 unit, optional)", value="", help="Leave empty to use the default rate for the currency.")
        category = st.selectbox("Category" if kind == "expense" else "Source", cats, index=cats.index(cat0) if cat0 in cats else 0, key=f"{key}_cat")
        mode = None
        if kind == "expense":
            mode = st.radio("Paid with", core.MODES, index=core.MODES.index((txn or {}).get("mode", "Debit card")), horizontal=True)
        d1, d2 = st.columns(2)
        on = d1.date_input("Date", value=date.fromisoformat(txn["date"]) if txn else date.today())
        if txn and txn.get("time"):
            t0 = dtime.fromisoformat(txn["time"])
        else:
            t0 = dtime(0, 0) if txn else datetime.now().time().replace(second=0, microsecond=0)
        at = d2.time_input("Time", value=t0, step=60)
        tags = st.text_input("Tags", value=", ".join((txn or {}).get("tags", [])), placeholder="coffee, work") if kind == "expense" else ""
        merchant = st.text_input("Shop or source (optional)", value=(txn or {}).get("merchant", ""))
        note = st.text_input("Note (optional)", value=(txn or {}).get("note", "")) if (kind == "expense" or category == "Others") else ""
        ok = st.form_submit_button("Save changes" if txn else ("Add income" if kind == "income" else "Add expense"), type="primary", width="stretch")
    if ok:
        try:
            with core.connect() as conn:
                core.add_txn(conn, type=kind, amount=amount, currency=currency, fx_rate=fx, category=category, mode=mode or "Bank transfer",
                             tags=tags, on=on.isoformat(), merchant=merchant, note=note, txn_id=(txn or {}).get("id"), at=at.strftime("%H:%M"))
                start = (core.get_settings(conn) or {}).get("opening_date", "")
            if start and on.isoformat() < start:
                st.toast(f"Saved, but it is dated before your balance date ({start}), so it does not change the balance. "
                         "Change that date in Settings if needed.", icon="⚠️")
            return True
        except ValueError as e:
            st.error(str(e))
    return False


@st.dialog("Add income")
def income_dialog():
    if txn_form("income_form", "income"):
        st.toast("Income added")
        st.rerun()


@st.dialog("Add expense")
def expense_dialog(category: str):
    if txn_form(f"quick_{category}", "expense", default_category=category):
        st.toast("Expense added")
        st.rerun()


@st.dialog("Edit entry")
def edit_dialog(txn: dict):
    if txn_form(f"edit_{txn['id']}", txn["type"], txn):
        st.toast("Entry updated")
        st.rerun()
    if st.button("Delete this entry", width="stretch"):
        with core.connect() as conn:
            core.delete_txn(conn, txn["id"])
        st.toast("Entry deleted")
        st.rerun()


def entry_picker(rows: list[dict], key: str):
    """Pick one entry from a list to edit or delete (Streamlit tables cannot hold buttons per row)."""
    if not rows:
        return
    opts = {f"{core.when(t, True)}  {core.describe(t)}  {'+' if t['type'] == 'income' else '-'}{core.fmt(t['base_minor'])}": t for t in rows[:200]}
    with st.expander("Edit or delete an entry"):
        pick = st.selectbox("Entry", list(opts), key=key, label_visibility="collapsed")
        if st.button("Open", key=key + "_open"):
            edit_dialog(opts[pick])


# ---------- setup ----------

def brand_header(tagline: str = "Busy bees save more."):
    logo = base64.b64encode((Path(__file__).parent / "assets" / "logo.png").read_bytes()).decode()
    st.markdown('<div style="text-align:center;margin:1rem 0 .6rem"><img src="data:image/png;base64,' + logo + '" width="84" height="84" '
                'style="border-radius:22px;box-shadow:0 0 0 1px rgba(216,183,106,.35);margin-bottom:10px">'
                '<h1 style="margin:0">Xpense Bee</h1><div class="muted">' + tagline + '</div></div>', unsafe_allow_html=True)


def google_configured() -> bool:
    """Google sign-in works only after the owner adds their own Google client in .streamlit/secrets.toml (see README)."""
    try:
        return "google" in st.secrets["auth"]
    except Exception:
        return False


def google_signed_in() -> bool:
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return False


def google_button(key: str):
    if google_configured():
        if st.button("Continue with Google", icon=":material/login:", key=key, width="stretch"):
            st.login("google")
    else:
        st.button("Continue with Google", icon=":material/login:", key=key, width="stretch", disabled=True,
                  help="Needs a Google client ID in .streamlit/secrets.toml. The README explains the five-minute setup.")


def sign_out():
    st.session_state["signed_in"] = False
    if google_signed_in():
        st.logout()
    else:
        st.rerun()


def sign_up_form():
    with st.form("signup", border=False):
        name = st.text_input("Name")
        email = st.text_input("Email")
        pw = st.text_input("Password (8 or more characters)", type="password")
        go_ = st.form_submit_button("Create account", type="primary", width="stretch")
    if go_:
        try:
            with core.connect() as conn:
                core.create_account(conn, name, email, pw)
            st.session_state["signed_in"] = True
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    st.markdown('<div class="or">or</div>', unsafe_allow_html=True)
    google_button("g_signup")
    st.caption("You add your age, job, salary and starting balance later, under Settings.")


def auth_screen(profile: dict | None):
    """First run: create an account (or try the demo). Later runs: sign in. The account is local to this computer."""
    brand_header()
    if st.session_state.get("google_mismatch"):
        st.error(f"This computer's profile belongs to {st.session_state['google_mismatch']}. Sign in with that Google account.")
    with st.container(key="authcard"):
        st.markdown('<div class="chipbar"><div class="chip"></div><span>Xpense Bee</span></div>', unsafe_allow_html=True)
        if profile is None:
            tab_up, tab_demo = st.tabs(["Sign up", "Try the demo"])
            with tab_up:
                sign_up_form()
            with tab_demo:
                st.write("Fills the app with synthetic entries so you can look around. No password is needed.")
                if st.button("Open the demo", type="primary", width="stretch"):
                    with core.connect() as conn:
                        sample_data.seed(conn)
                    st.session_state["signed_in"] = True
                    st.rerun()
            return
        st.markdown(f"Welcome back, **{profile['name']}**")
        if core.has_password(profile):
            with st.form("signin", border=False):
                email = st.text_input("Email", value=profile.get("email") or "")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Sign in", type="primary", width="stretch"):
                    if core.verify_login(profile, email, pw):
                        st.session_state["signed_in"] = True
                        st.rerun()
                    else:
                        st.error("That email and password do not match.")
            st.markdown('<div class="or">or</div>', unsafe_allow_html=True)
        google_button("g_signin")
    st.caption("This sign-in keeps casual visitors out of the app on this computer. It does not encrypt the database file.")


def google_session(conn, profile) -> None:
    """If the visitor signed in with Google, create the profile (first time) or check it is the same account."""
    if not google_signed_in() or st.session_state.get("signed_in"):
        return
    email = (st.user.get("email") or "").lower()
    name = st.user.get("name") or email.split("@")[0]
    if profile is None:
        core.create_account(conn, name, email, provider="google")
        conn.commit()
        st.session_state["signed_in"] = True
        st.rerun()
    elif (profile.get("email") or "").lower() == email:
        st.session_state["signed_in"] = True
        st.session_state.pop("google_mismatch", None)
        st.rerun()
    else:
        st.session_state["google_mismatch"] = profile.get("email") or profile["name"]
        st.logout()


# ---------- pages ----------

def greeting() -> str:
    hr = datetime.now().hour
    return "Good morning" if 5 <= hr < 12 else "Good afternoon" if 12 <= hr < 17 else "Good evening"


def page_home(conn, profile, settings, txns):
    st.markdown(f"<h2 style='margin:0 0 .6rem'>{greeting()}, {profile['name'].split()[0]}</h2>", unsafe_allow_html=True)
    hide = st.session_state.get("hide", True)
    led_bal = core.balance_now(txns, settings)
    who = f'<div class="name">{profile["name"]}</div>'
    if profile["job"]:
        who += f'<div class="sub">{profile["job"]}</div>'
    demo = ", ".join(x for x in [f"{profile['age']} years" if profile["age"] else "", profile["sex"]] if x)
    if demo:
        who += f'<div class="sub">{demo}</div>'
    bal_html = "••••• ••" if hide else f'{core.fmt(led_bal)} <span class="cur">{core.BASE}</span>'
    ym = date.today().isoformat()[:7]
    mt = core.totals([x for x in txns if x["date"][:7] == ym])
    mon = date.today().strftime("%b")
    bee = _b64("bee.svg")
    st.markdown(f"""<div class="atm"><div class="top"><div class="chip"></div><div class="brand"><span>Xpense Bee</span><img class="bee" src="data:image/svg+xml;base64,{bee}" alt=""></div></div>
      <div><div class="label">Available balance</div><div class="bal">{bal_html}</div></div>
      <div class="stats">
        <div class="stat inc"><span class="dot">&#8595;</span><span><div class="lab">Income, {mon}</div><div class="val">{mask("+" + core.fmt(mt["income"]))}</div></span></div>
        <div class="stat exp"><span class="dot">&#8593;</span><span><div class="lab">Expenses, {mon}</div><div class="val">{mask("-" + core.fmt(mt["expense"]))}</div></span></div>
      </div>
      <div>{who}</div></div>""", unsafe_allow_html=True)
    with st.container(key="cardbar"):
        c1, c2 = st.columns([1, 1])
        if c1.button("Show balance" if hide else "Hide balance", icon=":material/visibility:" if hide else ":material/visibility_off:", key="eye"):
            st.session_state["hide"] = not hide
            st.rerun()
        if c2.button("Add income", icon=":material/add:", type="primary", key="addinc"):
            income_dialog()
    if core.profile_incomplete(profile):
        with st.container(key="nudge"):
            n1, n2 = st.columns([3, 1])
            n1.markdown("Add your age, job and salary to finish your profile.")
            if n2.button("Open", key="nudge_go"):
                st.session_state["nav"] = "Settings"
                st.rerun()
    with st.container(key="upcoming"):
        st.subheader(":material/notifications_active: Upcoming payments")
        rem = core.list_reminders(conn)[:3]
        if rem:
            st.markdown("".join(line(r["title"], due_text(r), mask("-" + core.fmt(r["amount_minor"])) if r["amount_minor"] else "", "neg") for r in rem), unsafe_allow_html=True)
        else:
            st.caption("No payments scheduled. Add an EMI or loan reminder in Insight.")
    recent = core.filter_sort(txns, sort="new")[:5]
    with st.expander(f":material/receipt_long: Recent activity ({len(recent)})" if recent else ":material/receipt_long: Recent activity", expanded=False):
        if recent:
            st.markdown("".join(line(core.describe(t), rel_day(t["date"]) + (", " + t["time"] if t.get("time") else "") + (", " + t["mode"] if t["type"] == "expense" else ""),
                                     mask(("+" if t["type"] == "income" else "-") + core.fmt(t["base_minor"])), "pos" if t["type"] == "income" else "neg") for t in recent),
                        unsafe_allow_html=True)
        else:
            st.caption("Nothing yet. Use Add income on your card or log an expense.")


def page_expense(conn, profile, settings, txns):
    st.title("Expenses")
    st.subheader("Quick add")
    with st.container(key="quick"):
        for row in range(0, len(core.EXPENSE_CATEGORIES), 4):
            cols = st.columns(4)
            for col, cat in zip(cols, core.EXPENSE_CATEGORIES[row:row + 4]):
                if col.button(f"{ICONS[cat]}\n\n{cat}", key=f"q_{cat}", width="stretch"):
                    expense_dialog(cat)
    expenses = [t for t in txns if t["type"] == "expense"]
    st.subheader("Recent expenses")
    recent = core.filter_sort(expenses)[:5]
    st.markdown("".join(line(core.describe(t), f"{rel_day(t['date'])}{', ' + t['time'] if t.get('time') else ''}, {t['mode']}", "-" + core.fmt(t["base_minor"]), "neg") for t in recent) or
                '<div class="muted">Your latest expenses will show here.</div>', unsafe_allow_html=True)
    st.subheader("All expenses")
    c1, c2 = st.columns(2)
    sort = c1.selectbox("Sort", list(SORTS))
    cat = c2.selectbox("Category", ["All categories"] + core.EXPENSE_CATEGORIES)
    c3, c4 = st.columns(2)
    bucket = c3.selectbox("Amount range", ["Any amount"] + [b[0] for b in core.BUCKETS])
    mode = c4.selectbox("Payment mode", ["Any payment mode"] + core.MODES)
    text = st.text_input("Search", placeholder="Shop, note or tag")
    rows = core.filter_sort(expenses, category=None if cat.startswith("All") else cat, bucket=None if bucket.startswith("Any") else bucket,
                            mode=None if mode.startswith("Any") else mode, text=text, sort=SORTS[sort])
    st.caption(f"{len(rows)} expenses, {core.fmt(sum(t['base_minor'] for t in rows))} {core.BASE} in total")
    if rows:
        st.dataframe(pd.DataFrame([{"Date and time": core.when(t, True), "Category": t["category"], "Shop": t["merchant"], "Paid with": t["mode"],
                                    "Tags": " ".join("#" + g for g in t["tags"]), "Amount": t["base_minor"] / 100} for t in rows[:300]]),
                     hide_index=True, width="stretch", column_config={"Amount": st.column_config.NumberColumn(format="%.2f")})
        entry_picker(rows, "exp_pick")
    else:
        st.info("No expenses match these filters.")


def dark_layout(fig, height=260):
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e8f1ee"), showlegend=False, xaxis=dict(gridcolor="rgba(138,167,162,.15)"), yaxis=dict(gridcolor="rgba(138,167,162,.15)"))
    return fig


MODES = ["Month", "Day", "3 months", "6 months", "12 months", "All time"]


def _set_mode(mode: str):
    st.session_state["ins_mode"] = mode


def _shift_month(n: int):
    m = core.add_months(st.session_state["cal_month"], n)
    st.session_state["cal_month"] = m
    st.session_state["cal_day"] = date.fromisoformat(m + "-01") if m != date.today().isoformat()[:7] else date.today()
    st.session_state["ins_mode"] = "Month"


def _day_picked():
    d = st.session_state["cal_day"]
    st.session_state["cal_month"] = d.isoformat()[:7]
    st.session_state["ins_mode"] = "Day"
    st.session_state["cal_picks"] = st.session_state.get("cal_picks", 0) + 1     # collapses the calendar dropdown


def _whole_month():
    st.session_state["ins_mode"] = "Month"
    st.session_state["cal_picks"] = st.session_state.get("cal_picks", 0) + 1


def calendar_block(txns, reminders):
    month = st.session_state.setdefault("cal_month", date.today().isoformat()[:7])
    st.session_state.setdefault("cal_day", date.today())
    with st.container(key="calnav"):
        n1, n2, n3 = st.columns([1, 3, 1])
        n1.button("", icon=":material/chevron_left:", key="prev", on_click=_shift_month, args=(-1,))
        n2.markdown(f"<h3 style='text-align:center;margin:0'>{date(int(month[:4]), int(month[5:7]), 1):%B %Y}</h3>", unsafe_allow_html=True)
        n3.button("", icon=":material/chevron_right:", key="next", on_click=_shift_month, args=(1,))
    y, m = int(month[:4]), int(month[5:7])
    first = date(y, m, 1)
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    cells = [start + timedelta(days=i) for i in range(42)]
    sel = st.session_state["cal_day"] if st.session_state.get("ins_mode") == "Day" else None
    mark: dict[str, set] = {}
    for t in txns:
        mark.setdefault(t["date"], set()).add("i" if t["type"] == "income" else "e")
    for r in reminders:
        for d in core.occurrences(r, cells[0].isoformat(), cells[-1].isoformat()):
            mark.setdefault(d, set()).add("r")
    html = '<div class="calgrid">' + "".join(f'<div class="dow">{d}</div>' for d in "SMTWTFS")
    for c in cells:
        cls = ("" if c.month == m else " out") + (" today" if c == date.today() else "") + (" sel" if c == sel else "")
        dots = "".join(f'<i class="dot {k}"></i>' for k in "rei" if k in mark.get(c.isoformat(), ()))
        html += f'<div class="d{cls}">{c.day}<br/>{dots or "&nbsp;"}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)
    st.caption("🟡 payment due   🔴 spent   🟢 income")
    c1, c2 = st.columns([3, 2])
    c1.date_input("Pick a day", key="cal_day", on_change=_day_picked, help="Choosing a day shows the insight for that day only.")
    c2.write("")
    c2.button("Whole month", on_click=_whole_month, width="stretch")


def reminders_block(conn, reminders, default_day: date):
    st.subheader("Payment reminders")
    with st.expander("Add a reminder", expanded=not reminders):
        with st.form("rem_form", clear_on_submit=True, border=False):
            title = st.text_input("Name", placeholder="Car loan EMI")
            c1, c2 = st.columns(2)
            rtype = c1.selectbox("Type", core.REMINDER_TYPES)
            amount = c2.text_input("Amount (optional)")
            c3, c4 = st.columns(2)
            on = c3.date_input("Due date", value=default_day)
            at = c4.time_input("Time", value=dtime(9, 0))
            repeat = st.radio("Repeat", ["Every month", "Just once"], horizontal=True)
            lead = st.selectbox("Remind me (calendar file)", list(core.LEAD_OPTIONS))
            notes = st.text_input("Note (optional)")
            if st.form_submit_button("Save reminder", type="primary", width="stretch"):
                try:
                    core.add_reminder(conn, title=title, type=rtype, amount=amount, on=on.isoformat(), time=at.strftime("%H:%M"),
                                      repeat="monthly" if repeat == "Every month" else "none", lead_min=core.LEAD_OPTIONS[lead], notes=notes)
                    conn.commit()
                    st.toast("Reminder added")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    for r in reminders:
        a, b, d = st.columns([5, 2, 1])
        a.markdown(line(r["title"], due_text(r) + (", monthly" if r["repeat"] == "monthly" else ""), "-" + core.fmt(r["amount_minor"]) if r["amount_minor"] else "", "neg"), unsafe_allow_html=True)
        if b.button("Mark paid", key=f"paid_{r['id']}"):
            core.mark_paid(conn, r["id"])
            conn.commit()
            st.rerun()
        if d.button("", icon=":material/delete:", key=f"del_{r['id']}"):
            core.delete_reminder(conn, r["id"])
            conn.commit()
            st.rerun()
    if reminders:
        st.download_button("Download all as calendar file (.ics)", core.build_ics(reminders), file_name="payment_reminders.ics", mime="text/calendar", width="stretch")
    else:
        st.caption("No reminders yet. Add your EMI, loan or rent with the date and time you want.")


def insight_range(txns) -> tuple[str, str, str]:
    mode = st.session_state.get("ins_mode", "Month")
    month = st.session_state.get("cal_month", date.today().isoformat()[:7])
    if mode == "Day":
        d = st.session_state.get("cal_day", date.today()).isoformat()
        return d, d, date.fromisoformat(d).strftime("%A, %d %B %Y")
    if mode == "Month":
        last = f"{month}-{calendar.monthrange(int(month[:4]), int(month[5:7]))[1]:02d}"
        return month + "-01", min(last, core.today()) if month == core.today()[:7] else last, date.fromisoformat(month + "-01").strftime("%B %Y")
    frm, to = core.period_range({"3 months": "Last 3 months", "6 months": "Last 6 months", "12 months": "Last 12 months", "All time": "All time"}[mode], txns)
    return frm, to, mode


def page_insight(conn, profile, settings, txns):
    with st.container(key="pagehead"):
        head, dl = st.columns([4, 1])
    head.title("Insight")
    reminders = core.list_reminders(conn)
    # The calendar is a dropdown: open until a day or "Whole month" is picked, then it shrinks. The invisible suffix gives the
    # dropdown a new identity after each pick, so it collapses again even if you had opened it by hand.
    picks = st.session_state.get("cal_picks", 0)
    frm, to, label = insight_range(txns)
    with st.expander(":material/calendar_month: Calendar" + "\u200b" * (picks % 50), expanded=picks == 0):
        calendar_block(txns, reminders)
    st.segmented_control("Show insight for", MODES, key="ins_mode", default="Month")
    frm, to, label = insight_range(txns)
    ds = core.insight(txns, settings, frm, to)
    t = ds["totals"]
    st.markdown(f"**Showing {label}**")
    if st.session_state.get("ins_mode") == "Day":
        day_items = [line(r["title"], r["time"], "-" + core.fmt(r["amount_minor"]) if r["amount_minor"] else "", "neg") for r in reminders if core.occurrences(r, frm, frm)]
        day_items += [line(core.describe(x), (x["time"] + ", " if x.get("time") else "") + (x["mode"] if x["type"] == "expense" else "Income"), ("+" if x["type"] == "income" else "-") + core.fmt(x["base_minor"]),
                           "pos" if x["type"] == "income" else "neg") for x in txns if x["date"] == frm]
        st.markdown("".join(day_items) or '<div class="muted">Nothing on this day.</div>', unsafe_allow_html=True)
    if ds["txns"]:
        dl.download_button("PDF", pdf_export.insight_pdf(ds, profile), file_name=f"insight_{frm}_to_{to}.pdf", mime="application/pdf", icon=":material/download:")
        a, b, c = st.columns(3)
        a.metric("Income", core.fmt(t["income"]))
        b.metric("Spent", core.fmt(t["expense"]))
        c.metric("Net", core.fmt(t["net"]))
        one_day = frm == to
        if not one_day:
            st.caption(f"About {core.fmt(ds['avg_per_day'])} {core.BASE} a day" + (f", most of it on {ds['top'][0]} ({core.fmt(ds['top'][1])})." if ds["top"] else "."))
        if t["expense"] > 0 and not one_day:
            st.subheader("Daily spending")
            fig = go.Figure(go.Scatter(x=[d["date"] for d in ds["daily"]], y=[d["expense"] / 100 for d in ds["daily"]], fill="tozeroy",
                                       line=dict(color="#f28b7b", width=2), fillcolor="rgba(242,139,123,.22)", hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
            st.plotly_chart(dark_layout(fig), width="stretch")
        if t["expense"] > 0:
            st.subheader("Where the money went")
            cats = ds["categories"]
            fig = go.Figure(go.Pie(labels=[c for c, _ in cats], values=[v / 100 for _, v in cats], hole=0.6, marker=dict(colors=PALETTE, line=dict(color="#000000", width=2)),
                                   sort=False, textinfo="percent"))
            st.plotly_chart(dark_layout(fig, 300).update_layout(showlegend=True), width="stretch")
        if not one_day:
            st.subheader("Balance over time")
            fig = go.Figure(go.Scatter(x=[d["date"] for d in ds["balance"]], y=[d["balance"] / 100 for d in ds["balance"]], line=dict(color="#d8b76a", width=2.5, shape="hv"),
                                       hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
            st.plotly_chart(dark_layout(fig), width="stretch")
        if len(ds["monthly"]) > 1:
            st.subheader("Income and spending by month")
            fig = go.Figure([go.Bar(name="Income", x=[m["month"] for m in ds["monthly"]], y=[m["income"] / 100 for m in ds["monthly"]], marker_color="#5fd3a8"),
                             go.Bar(name="Spent", x=[m["month"] for m in ds["monthly"]], y=[m["expense"] / 100 for m in ds["monthly"]], marker_color="#f28b7b")])
            st.plotly_chart(dark_layout(fig).update_layout(barmode="group", showlegend=True, legend=dict(orientation="h", y=1.15)), width="stretch")
        if t["expense"] > 0 and not one_day:
            st.subheader("Size of expenses")
            st.caption("How many expenses fall in each amount range.")
            fig = go.Figure(go.Bar(x=[h["label"] for h in ds["histogram"]], y=[h["count"] for h in ds["histogram"]], marker_color="#d8b76a"))
            st.plotly_chart(dark_layout(fig).update_layout(bargap=0.04), width="stretch")
        if t["expense"] > 0:
            st.subheader("Payment methods")
            fig = go.Figure(go.Bar(y=[m for m, _ in ds["modes"]][::-1], x=[v / 100 for _, v in ds["modes"]][::-1], orientation="h", marker_color="#d8b76a"))
            st.plotly_chart(dark_layout(fig, 200), width="stretch")
    else:
        st.info("Nothing in this period yet.")
    compare_block(txns)
    reminders_block(conn, reminders, st.session_state.get("cal_day", date.today()))


def compare_block(txns):
    st.subheader("Compare months")
    avail = core.months_with_expenses(txns)
    if len(avail) < 2:
        st.caption("Spend in at least two different months to compare them.")
        return
    pick = st.multiselect("Months to compare", avail, default=avail[:2], max_selections=6,
                          format_func=lambda m: date.fromisoformat(m + "-01").strftime("%B %Y"), key="cmp_months")
    if len(pick) < 2:
        st.caption("Choose two or more months.")
        return
    cmp_ = core.compare_months(txns, pick)
    ms = cmp_["months"]
    name = lambda m: date.fromisoformat(m + "-01").strftime("%b %Y")
    with st.container(key="cmp"):
        prev = None
        for col, m in zip(st.columns(len(ms)), ms):
            delta = None if prev is None else f"{(cmp_['totals'][m] - cmp_['totals'][prev]) / 100:+,.2f}"
            col.metric(name(m), core.fmt(cmp_["totals"][m]), delta=delta, delta_color="inverse")
            prev = m
    ch = cmp_["change"]
    if ch and ch["pct"] is not None:
        word = "more" if ch["diff"] > 0 else "less"
        st.caption(f"{name(ch['to'])} is {abs(ch['pct']):.0f}% {word} than {name(ch['from'])} ({core.fmt(abs(ch['diff']))} {core.BASE}).")
    if cmp_["categories"]:
        fig = go.Figure([go.Bar(name=name(m), x=[r["category"] for r in cmp_["categories"]], y=[r["by_month"][m] / 100 for r in cmp_["categories"]],
                                marker_color=PALETTE[i % len(PALETTE)]) for i, m in enumerate(ms)])
        st.plotly_chart(dark_layout(fig, 300).update_layout(barmode="group", showlegend=True, legend=dict(orientation="h", y=1.15)), width="stretch")
        df = pd.DataFrame([{"Category": r["category"], **{name(m): r["by_month"][m] / 100 for m in ms}} for r in cmp_["categories"]])
        df["Change"] = df[name(ms[-1])] - df[name(ms[-2])]
        fmt = {c: "{:,.2f}" for c in df.columns if c != "Category"}
        fmt["Change"] = "{:+,.2f}"
        styled = df.style.format(fmt).map(lambda v: "color:#f28b7b" if v > 0 else "color:#5fd3a8" if v < 0 else "", subset=["Change"])
        st.dataframe(styled, hide_index=True, width="stretch")


def page_statement(conn, profile, settings, txns):
    with st.container(key="pagehead"):
        head, dl = st.columns([4, 1])
    head.title("Statement")
    kind_label = st.segmented_control("Show", ["All", "Income", "Expenses"], default="All", label_visibility="collapsed") or "All"
    kind = {"All": "all", "Income": "income", "Expenses": "expense"}[kind_label]
    period = st.selectbox("Period", core.PERIODS[:-1] + ["Since opening"], label_visibility="collapsed")
    frm, to = core.period_range("All time" if period == "Since opening" else period, txns)
    stm = core.statement(txns, settings, frm, to, kind)
    dl.download_button("PDF", pdf_export.statement_pdf(stm, profile, settings, kind), file_name=f"statement_{stm['from']}_to_{to}.pdf",
                       mime="application/pdf", icon=":material/download:")
    a, b = st.columns(2)
    a.metric("Balance brought forward", core.fmt(stm["brought"]))
    b.metric("Closing balance", core.fmt(stm["closing"]))
    c, d = st.columns(2)
    c.metric("Total credit", "+" + core.fmt(stm["credits"]))
    d.metric("Total debit", "-" + core.fmt(stm["debits"]))
    st.caption(f"{stm['from']} to {to}, amounts in {core.BASE}. Credit is money in (green), debit is money out (red).")
    if not stm["rows"]:
        st.info("No entries in this period.")
        return
    months: dict[str, list[dict]] = {}
    for r in reversed(stm["rows"]):                      # newest first, grouped by month
        months.setdefault(r["txn"]["date"][:7], []).append(r)
    for mk, rows in months.items():
        cr = sum(r["credit"] for r in rows)
        db = sum(r["debit"] for r in rows if not r["memo"])
        st.markdown(f'<div class="mhead"><span class="m">{date.fromisoformat(mk + "-01"):%B %Y}</span>'
                    f'<span class="s"><span class="pos">Credit +{core.fmt(cr)}</span> &nbsp; <span class="neg">Debit -{core.fmt(db)}</span></span></div>', unsafe_allow_html=True)
        money_cell = lambda v: f"{v / 100:,.2f}" if v else ""
        df = pd.DataFrame([{"Date and time": core.when(r["txn"]), "Details": core.describe(r["txn"]) + (" (card, not deducted)" if r["memo"] else ""),
                            "Debit": money_cell(r["debit"]), "Credit": money_cell(r["credit"]), "Balance": f"{r['balance'] / 100:,.2f}"} for r in rows])
        styled = df.style.map(lambda v: "color: #f28b7b", subset=["Debit"]).map(lambda v: "color: #5fd3a8", subset=["Credit"]).set_properties(subset=["Debit", "Credit", "Balance"], **{"text-align": "right"})
        st.dataframe(styled, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 420),
                     column_config={"Date and time": st.column_config.Column(width=112), "Details": st.column_config.Column(width=125),
                                    "Debit": st.column_config.Column(width=76), "Credit": st.column_config.Column(width=76), "Balance": st.column_config.Column(width=88)})
    if stm["opening_row"] and kind == "all":
        st.caption(f"{stm['opening_row']}  Opening balance  {core.fmt(settings['opening_minor'])}")
    entry_picker([r["txn"] for r in reversed(stm["rows"])], "stm_pick")


def page_settings(conn, profile, settings, txns):
    st.title("Settings")
    if core.needs_sign_in(profile):
        with st.container(key="account"):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{profile['name']}**<br><span class='muted'>{profile.get('email') or ''}</span>", unsafe_allow_html=True)
            if c2.button("Sign out", icon=":material/logout:", key="signout"):
                sign_out()
    st.subheader("Your profile")
    with st.form("profile", border=False):
        name = st.text_input("Name", value=profile["name"])
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", 0, 120, value=profile["age"] or 0, help="0 leaves it empty")
        sexes = ["", "Female", "Male", "Other"]
        sex = c2.selectbox("Sex", sexes, index=sexes.index(profile["sex"]) if profile["sex"] in sexes else 0, format_func=lambda x: x or "Prefer not to say")
        job = st.text_input("Job", value=profile["job"] or "")
        salary = st.text_input("Monthly salary (SAR)", value=f"{profile['salary_minor'] / 100:.2f}" if profile.get("salary_minor") else "", placeholder="Optional")
        if st.form_submit_button("Save profile", type="primary"):
            sal = core.to_minor(salary) if salary.strip() else None
            if salary.strip() and sal is None:
                st.error("Enter the salary as a number, like 6500.")
            else:
                try:
                    core.save_profile(conn, name, int(age) or None, sex, job, sal)
                    conn.commit()
                    st.toast("Profile saved")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    st.subheader("Balance")
    st.caption("Your balance is the starting amount plus all income, minus all expenses dated on or after the date.")
    with st.form("balance", border=False):
        bal = st.text_input("Starting balance (SAR)", value=f"{settings['opening_minor'] / 100:.2f}")
        asof = st.date_input("Balance as of", value=date.fromisoformat(settings["opening_date"]))
        credit = st.toggle("Credit card spending reduces balance", value=bool(settings["credit_counts"]),
                           help="Turn off if you pay the card bill later and record that payment as an expense.")
        if st.form_submit_button("Update balance", type="primary"):
            minor = core.to_minor(bal)
            if minor is None:
                st.error("Enter the balance as a number, like 5200.50.")
            else:
                core.save_settings(conn, minor, asof.isoformat(), credit)
                conn.commit()
                st.toast("Balance updated")
                st.rerun()
    st.subheader("Your data")
    if txns:
        df = pd.DataFrame([{**{k: t[k] for k in ("date", "time", "type", "category", "mode", "merchant", "note")}, "tags": " ".join(t["tags"]),
                            "amount": t["amount_minor"] / 100, "currency": t["currency"], "amount_sar": t["base_minor"] / 100} for t in core.filter_sort(txns, sort="old")])
        st.download_button("Download all entries (CSV)", df.to_csv(index=False), file_name=f"entries_{date.today()}.csv", mime="text/csv")
    if st.button("Load demo data (adds synthetic entries)"):
        sample_data.seed(conn)
        conn.commit()
        st.rerun()
    with st.expander("Erase everything"):
        if st.button("Erase all data", type="primary"):
            for tbl in ("transactions", "reminders", "settings", "profile"):
                conn.execute(f"DELETE FROM {tbl}")
            conn.commit()
            st.rerun()


# ---------- main ----------

def main():
    with core.connect() as conn:
        profile, settings = core.get_profile(conn), core.get_settings(conn)
        google_session(conn, profile if profile and settings else None)
        if not profile or not settings or (core.needs_sign_in(profile) and not st.session_state.get("signed_in")):
            auth_screen(profile if profile and settings else None)
            return
        txns = core.list_txns(conn)
        page = st.session_state.get("nav") or "Home"
        {"Home": page_home, "Expense": page_expense, "Insight": page_insight, "Statement": page_statement,
         "Settings": page_settings}[page](conn, profile, settings, txns)
        with st.container(key="bottomnav"):                 # fixed to the bottom of the window by the CSS above
            for col, name in zip(st.columns(len(PAGES)), PAGES):
                if col.button(name if name == page else "\u200b", icon=f":material/{NAV_ICONS[name]}:", key=f"nav_{name}", help=name,
                              type="primary" if name == page else "secondary"):
                    st.session_state["nav"] = name
                    st.rerun()


main()