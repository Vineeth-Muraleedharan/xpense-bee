import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pdf_export  # noqa: E402
import sample_data  # noqa: E402
import tracker_core as core  # noqa: E402


@pytest.fixture
def conn():
    with core.connect(":memory:") as c:
        core.save_profile(c, "Test User", 30, "Other", "Tester")
        core.save_settings(c, core.to_minor("1000"), "2026-10-01", True)
        yield c


def txns(c):
    return core.list_txns(c)


def test_to_minor_and_rejects_bad_input():
    assert core.to_minor("12.5") == 1250 and core.to_minor("12,50") == 1250 and core.to_minor("1,200.50") == 120050
    assert core.to_minor("abc") is None and core.to_minor("-3") is None and core.to_minor("nan") is None


def test_balance_is_opening_plus_income_minus_expense(conn):
    core.add_txn(conn, type="income", amount="500", category="Salary", on="2026-10-02")
    core.add_txn(conn, type="expense", amount="120.25", category="Food", mode="Cash", on="2026-10-03")
    assert core.balance_now(txns(conn), core.get_settings(conn)) == 100000 + 50000 - 12025


def test_entries_before_opening_date_are_ignored(conn):
    core.add_txn(conn, type="expense", amount="999", category="Food", on="2026-09-30")
    assert core.balance_now(txns(conn), core.get_settings(conn)) == 100000


def test_credit_card_toggle(conn):
    core.add_txn(conn, type="expense", amount="100", category="Shopping", mode="Credit card", on="2026-10-02")
    s = core.get_settings(conn)
    assert core.balance_now(txns(conn), s) == 90000
    core.save_settings(conn, s["opening_minor"], s["opening_date"], False)
    s = core.get_settings(conn)
    led = core.build_ledger(txns(conn), s)
    assert led["closing"] == 100000 and led["rows"][0]["memo"] is True


def test_foreign_currency_default_and_manual_rate(conn):
    a = core.add_txn(conn, type="expense", amount="10", currency="USD", category="Food", on="2026-10-02")
    b = core.add_txn(conn, type="expense", amount="10", currency="USD", fx_rate="3.8", category="Food", on="2026-10-02")
    by = {t["id"]: t for t in txns(conn)}
    assert by[a]["base_minor"] == 3750 and by[b]["base_minor"] == 3800


def test_validation_errors(conn):
    for kw in ({"amount": "0"}, {"amount": "x"}, {"amount": "5", "on": "2026-02-30"}, {"amount": "5", "currency": "USD", "fx_rate": "-1"}):
        with pytest.raises(ValueError):
            core.add_txn(conn, **{"type": "expense", "category": "Food", **kw})


def test_buckets_use_whole_units():
    assert core.bucket_of(2099) == "0 - 20" and core.bucket_of(2100) == "21 - 50" and core.bucket_of(1000100) == "10000+"
    assert core.bucket_of(1000000) == "2501 - 10000"


def test_filter_and_sort(conn):
    for amt, cat in (("10", "Food"), ("300", "Rent"), ("45", "Food")):
        core.add_txn(conn, type="expense", amount=amt, category=cat, on="2026-10-05")
    t = txns(conn)
    assert [x["base_minor"] for x in core.filter_sort(t, sort="high")] == [30000, 4500, 1000]
    assert [x["base_minor"] for x in core.filter_sort(t, category="Food", sort="low")] == [1000, 4500]
    assert len(core.filter_sort(t, bucket="21 - 50")) == 1


def test_statement_brought_forward_and_filter(conn):
    core.add_txn(conn, type="income", amount="200", category="Salary", on="2026-10-02")
    core.add_txn(conn, type="expense", amount="50", category="Food", on="2026-10-10")
    st = core.statement(txns(conn), core.get_settings(conn), "2026-10-05", "2026-10-31")
    assert st["brought"] == 120000 and st["closing"] == 115000 and st["debits"] == 5000 and st["credits"] == 0
    only_income = core.statement(txns(conn), core.get_settings(conn), "2026-10-01", "2026-10-31", "income")
    assert len(only_income["rows"]) == 1 and only_income["opening_row"] == "2026-10-01"


def test_reminder_monthly_clamps_and_marks_paid(conn):
    rid = core.add_reminder(conn, title="EMI", type="EMI", amount="100", on="2026-01-31", time="09:00")
    core.mark_paid(conn, rid)
    assert core.list_reminders(conn)[0]["date"] == "2026-02-28"
    core.mark_paid(conn, rid)
    assert core.list_reminders(conn)[0]["date"] == "2026-03-31"
    once = core.add_reminder(conn, title="One off", type="Other", amount="", on="2026-11-01", time="10:00", repeat="none")
    core.mark_paid(conn, once)
    assert all(r["id"] != once for r in core.list_reminders(conn))


def test_reminder_validation(conn):
    with pytest.raises(ValueError):
        core.add_reminder(conn, title="", type="EMI", amount="x", on="2026-13-01", time="25:00")


def test_ics_content(conn):
    core.add_reminder(conn, title="Car, loan; EMI", type="EMI", amount="1800", on="2026-10-28", time="18:30", lead_min=1440)
    ics = core.build_ics(core.list_reminders(conn), now=datetime(2026, 10, 16, 8, 0, 0, tzinfo=timezone.utc))
    assert "DTSTAMP:20261016T080000Z\r\n" in ics and "DTSTART:20261028T183000" in ics
    assert "RRULE:FREQ=MONTHLY;BYMONTHDAY=28" in ics and "TRIGGER:-PT1440M" in ics and r"Car\, loan\; EMI" in ics
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")


def test_demo_data_and_pdfs():
    with core.connect(":memory:") as c:
        assert sample_data.seed(c) > 50
        s, t, p = core.get_settings(c), core.list_txns(c), core.get_profile(c)
        frm, to = core.period_range("Last 3 months", t)
        assert pdf_export.statement_pdf(core.statement(t, s, frm, to), p, s)[:5] == b"%PDF-"
        assert pdf_export.insight_pdf(core.insight(t, s, frm, to), p)[:5] == b"%PDF-"
        ds = core.insight(t, s, frm, to)
        assert sum(h["count"] for h in ds["histogram"]) == sum(1 for x in ds["txns"] if x["type"] == "expense")


def test_local_sign_in_hash(conn):
    core.set_credentials(conn, "Me@Example.com", "correct horse")
    p = core.get_profile(conn)
    assert p["pw_hash"] != "correct horse" and core.has_password(p)
    assert core.verify_login(p, "me@example.com", "correct horse")
    assert not core.verify_login(p, "me@example.com", "wrong password")
    assert not core.verify_login(p, "other@example.com", "correct horse")
    core.save_profile(conn, "Renamed", 31, "", "Job")          # editing the profile keeps the password
    assert core.verify_login(core.get_profile(conn), "me@example.com", "correct horse")
    with pytest.raises(ValueError):
        core.set_credentials(conn, "bad", "short")


def test_statement_month_groups_and_debit_credit(conn):
    core.add_txn(conn, type="income", amount="100", category="Salary", on="2026-10-02")
    core.add_txn(conn, type="expense", amount="30", category="Food", on="2026-11-02")
    st = core.statement(txns(conn), core.get_settings(conn), "2026-10-01", "2026-11-30")
    assert sorted({r["txn"]["date"][:7] for r in st["rows"]}) == ["2026-10", "2026-11"]
    assert st["credits"] == 10000 and st["debits"] == 3000


def test_create_account_needs_only_name_email_password():
    with core.connect(":memory:") as c:
        core.create_account(c, "Vineeth", "V@Example.com", "a long password")
        p, s = core.get_profile(c), core.get_settings(c)
        assert p["name"] == "Vineeth" and p["email"] == "v@example.com" and core.needs_sign_in(p) and core.verify_login(p, "v@example.com", "a long password")
        assert s["opening_minor"] == 0 and s["opening_date"] == f"{date.today().year}-01-01"
        assert core.profile_incomplete(p)
        core.save_profile(c, "Vineeth", 29, "Male", "Analyst", core.to_minor("6500"))
        core.save_profile(c, "Vineeth", 29, "Male", "Analyst")          # salary kept when not passed
        p = core.get_profile(c)
        assert p["salary_minor"] == 650000 and not core.profile_incomplete(p) and core.verify_login(p, "v@example.com", "a long password")
        with pytest.raises(ValueError):
            core.create_account(c, "", "x@y.com", "a long password")


def test_google_account_has_no_password_but_still_needs_sign_in():
    with core.connect(":memory:") as c:
        core.create_account(c, "Gina", "Gina@Gmail.com", provider="google")
        p = core.get_profile(c)
        assert p["email"] == "gina@gmail.com" and not core.has_password(p) and core.needs_sign_in(p)
    with core.connect(":memory:") as c:
        sample_data.seed(c)
        assert not core.needs_sign_in(core.get_profile(c))             # the demo profile opens without signing in


def test_compare_months(conn):
    for on, cat, amt in (("2026-08-05", "Food", "100"), ("2026-08-09", "Rent", "300"), ("2026-09-02", "Food", "150"), ("2026-10-04", "Food", "50"), ("2026-10-06", "Gym", "40")):
        core.add_txn(conn, type="expense", amount=amt, category=cat, on=on)
    core.add_txn(conn, type="income", amount="999", category="Salary", on="2026-10-07")
    t = txns(conn)
    assert core.months_with_expenses(t) == ["2026-10", "2026-09", "2026-08"]
    c = core.compare_months(t, ["2026-10", "2026-08"])
    assert c["months"] == ["2026-08", "2026-10"] and c["totals"] == {"2026-08": 40000, "2026-10": 9000}
    assert c["change"]["diff"] == -31000 and round(c["change"]["pct"]) == -78
    food = next(r for r in c["categories"] if r["category"] == "Food")
    assert food["by_month"] == {"2026-08": 10000, "2026-10": 5000} and c["categories"][0]["category"] == "Rent"
    assert core.compare_months(t, ["2026-10"])["change"] is None


def test_transaction_time_is_stored_shown_and_orders_the_ledger(conn):
    a = core.add_txn(conn, type="expense", amount="10", category="Food", on="2026-10-05", at="18:40")
    b = core.add_txn(conn, type="income", amount="50", category="Salary", on="2026-10-05", at="09:05")
    c = core.add_txn(conn, type="expense", amount="5", category="Food", on="2026-10-05")          # no time given: stamped with now
    by = {t["id"]: t for t in txns(conn)}
    assert by[a]["time"] == "18:40" and by[b]["time"] == "09:05" and core.is_valid_time(by[c]["time"])
    assert core.when(by[a]) == "05 Oct 18:40" and core.when(by[a], True) == "05 Oct 2026 18:40"
    rows = core.build_ledger(txns(conn), core.get_settings(conn))["rows"]
    assert min(rows, key=lambda r: r["txn"]["time"])["txn"]["id"] == rows[0]["txn"]["id"]               # earliest time comes first within the day
    assert rows[0]["txn"]["time"] <= rows[-1]["txn"]["time"]
    assert rows[-1]["balance"] == 100000 + 5000 - 1000 - 500
    core.add_txn(conn, type="expense", amount="10", category="Food", on="2026-10-05", at="18:55", txn_id=a)   # editing keeps one row and updates the time
    assert next(t for t in txns(conn) if t["id"] == a)["time"] == "18:55" and len(txns(conn)) == 3
    with pytest.raises(ValueError):
        core.add_txn(conn, type="expense", amount="1", category="Food", at="25:61")
    old = {"date": "2026-10-05", "time": ""}
    assert core.when(old) == "05 Oct"                                                          # legacy entries show the date only


def test_older_database_gets_the_time_column(tmp_path):
    import sqlite3
    db = tmp_path / "old.db"
    raw = sqlite3.connect(db)
    raw.executescript(core.SCHEMA.replace(", time TEXT NOT NULL DEFAULT ''", ""))
    raw.execute("INSERT INTO transactions VALUES ('x','expense',100,'SAR','1',100,'Food','Cash','[]','2026-10-01','','','2026-10-01T00:00:00')")
    raw.commit(); raw.close()
    with core.connect(str(db)) as c:
        assert core.list_txns(c)[0]["time"] == ""