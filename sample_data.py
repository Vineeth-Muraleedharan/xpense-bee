"""Synthetic demo data. Nothing here is real financial data."""
from __future__ import annotations

import random
from datetime import date, timedelta

import tracker_core as core

# (category, merchant, low, high, mode, tags, weekly frequency)
EXPENSE_PATTERNS = [
    ("Food", "Supermarket", 40, 180, "Debit card", [], 1.5),
    ("Food", "Cafe", 12, 28, "Cash", ["coffee"], 3.0),
    ("Food", "Restaurant", 35, 140, "Credit card", [], 1.2),
    ("Transport", "Ride share", 15, 60, "Debit card", [], 1.5),
    ("Shopping", "Online store", 40, 900, "Credit card", ["impulse"], 0.5),
    ("Health", "Pharmacy", 20, 120, "Debit card", [], 0.3),
]
MONTHLY_FIXED = [  # category, merchant, amount, mode, day of month
    ("Rent", "Landlord", 3200, "Bank transfer", 2), ("Bills", "Electricity and water", 260, "Debit card", 5),
    ("Subscription", "Streaming", 45, "Credit card", 8), ("Gym", "Fitness club", 150, "Debit card", 3),
    ("EMI", "Car loan", 1450, "Bank transfer", 10), ("Education", "Online course", 220, "Credit card", 12),
]


def seed(conn, months: int = 4, seed_value: int = 7) -> int:
    """Fill an empty database with `months` months of fake data and two reminders. Returns rows added."""
    rng = random.Random(seed_value)
    today = date.today()
    start = (today.replace(day=1) - timedelta(days=30 * (months - 1))).replace(day=1)
    core.save_profile(conn, "Alex Demo", 31, "Other", "Product designer")
    core.save_settings(conn, core.to_minor("15000"), start.isoformat(), True)
    added, day = 0, start
    while day <= today:
        iso = day.isoformat()
        if day.day == 1:
            core.add_txn(conn, type="income", amount="9500", category="Salary", on=iso, merchant="Employer", at="09:00")
            added += 1
        if day.day == 15 and rng.random() < 0.7:
            core.add_txn(conn, type="income", amount=str(rng.randint(300, 1800)), category="Freelance", on=iso, merchant="Client work", at=f"{rng.randint(10, 17):02d}:{rng.randint(0, 59):02d}")
            added += 1
        for cat, merchant, amount, mode, dom in MONTHLY_FIXED:
            if day.day == dom:
                core.add_txn(conn, type="expense", amount=str(amount), category=cat, mode=mode, on=iso, merchant=merchant, at=f"{rng.randint(7, 22):02d}:{rng.randint(0, 59):02d}")
                added += 1
        for cat, merchant, low, high, mode, tags, weekly in EXPENSE_PATTERNS:
            if rng.random() < weekly / 7:
                core.add_txn(conn, type="expense", amount=f"{rng.uniform(low, high):.2f}", category=cat, mode=mode,
                             tags=",".join(tags), on=iso, merchant=merchant, at=f"{rng.randint(7, 22):02d}:{rng.randint(0, 59):02d}")
                added += 1
        day += timedelta(days=1)
    nxt = lambda dom: (today.replace(day=1) + timedelta(days=32)).replace(day=dom).isoformat()
    core.add_reminder(conn, title="Car loan EMI", type="EMI", amount="1450", on=nxt(10), time="09:00", lead_min=1440)
    core.add_reminder(conn, title="Rent", type="Rent", amount="3200", on=nxt(2), time="08:00", lead_min=1440)
    return added