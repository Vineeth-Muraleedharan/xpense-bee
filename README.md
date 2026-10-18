# Xpense Bee 
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://xpense-bee-by-vineeth.streamlit.app/)

**Live demo: https://xpense-bee-by-vineeth.streamlit.app/** - try it with the built-in demo data, no sign-up needed.

A personal finance tracker (Xpense Bee) you run on your own computer: income and expenses, a bank-style statement with running balance, insight charts, and payment reminders with a calendar file. Everything is stored in a local SQLite file. The repository holds **synthetic demo data only**.

## Features

- **Sign up and sign in**: the card-style sign-up asks only for name, email and password (or Continue with Google). Home greets you by name. Add age, sex, job, salary and your starting balance later under Settings. Sign out is at the top of Settings.
- **Look**: pure black with a faint honeycomb background; the card has a honeycomb on its right side fading to the left, a small bee logo, and this month's income and expenses.
- **Home**: your profile on a card, available balance with a show/hide control, "Add income" (Salary, Freelance, Others with a note), upcoming payments, recent activity.
- **Expense**: quick-access category buttons (EMI, Loan, Gym, Shopping, Rent, Bills, Education, Subscription, Food and more), quick-access buttons open an add dialog with that category preselected, recent expenses, and an all-expenses list you can sort and filter by category, payment mode and amount range (0-20, 21-50, 51-100, 101-500, 501-2500, 2501-10000, 10000+).
- **Insight**: a calendar at the top - a dropdown that shrinks once you pick a day or a month, and every chart, total and PDF follows that period (there is also a Compare months section for side-by-side spending by category, and payment reminders, with a `.ics` download). Charts: daily spending area chart, category donut, balance line, monthly income vs spending columns, histogram of expense sizes, payment-method bars. Download the report as PDF.
- **Statement**: each entry shows its date and time (like "18 Oct 14:32"; set in the add and edit forms, default now), with Debit and Credit columns (credit green, debit red), grouped by month with a month separator, filter all/credit/debit, balance after each entry. Download as PDF.
- **Settings**: profile, opening balance, credit-card handling, CSV export, demo data.

## Run it

```bash
conda create -n xpensebee python=3.12 -y
conda activate xpensebee
pip install -r requirements.txt
streamlit run app.py
```

Open the **Set up** screen, enter your name and exact bank balance, or press "explore with demo data". Run the tests with `pytest`.

## Continue with Google (optional)

Google sign-in needs your own Google OAuth client, so the button stays disabled until you add one. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, fill in the client ID and secret (steps are in the file), and run `pip install -r requirements.txt` again so Authlib is installed. The first Google account to sign in becomes the profile for this computer; other accounts are refused.

## How the balance works

Balance = opening balance + income - expenses, counting only entries dated on or after the opening date. Credit-card spending reduces the balance by default; turn that off in Settings if you record the card bill payment instead. Amounts in other currencies are converted to SAR with a default rate you can override per entry.

## Notes and limits

- The bottom bar is a CSS-fixed container; inactive tabs show icons only on small screens. The offline phone app in `personal-app` is the real installable app.
- The sign-in is a local convenience (salted PBKDF2 hash in the SQLite file), not encryption of your data.
- The statement and expense tables open an entry for editing through the "Edit or delete an entry" picker rather than clicking a row.
- PDF text uses a standard font, so names in non-Latin scripts show as "?" in the PDF.
- Money is stored as integer minor units, never floats. The data file is `data/finance.db` (override with `EXPENSE_DB`) and is git-ignored.
