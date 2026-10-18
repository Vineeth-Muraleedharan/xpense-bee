# Xpense Bee (Streamlit edition)

A personal finance tracker (working name: Xpense Bee) you run on your own computer: income and expenses, a bank-style statement with running balance, insight charts, and payment reminders with a calendar file. Everything is stored in a local SQLite file. The repository holds **synthetic demo data only**.

## Features

- **Sign in**: create a local account (email and password) or explore with demo data; Home greets you by name. Sign out is in Settings.
- **Look**: pure black with a faint honeycomb background; the card has a honeycomb on its right side fading to the left, a small bee logo, and this month's income and expenses.
- **Home**: your profile on a card, available balance with a show/hide control, "Add income" (Salary, Freelance, Others with a note), upcoming payments, recent activity.
- **Expense**: quick-access category buttons (EMI, Loan, Gym, Shopping, Rent, Bills, Education, Subscription, Food and more), quick-access buttons open an add dialog with that category preselected, recent expenses, and an all-expenses list you can sort and filter by category, payment mode and amount range (0-20, 21-50, 51-100, 101-500, 501-2500, 2501-10000, 10000+).
- **Insight**: a calendar at the top - pick a day or a month and every chart, total and PDF follows that period (also lists payment reminders, with a `.ics` download). Charts: daily spending area chart, category donut, balance line, monthly income vs spending columns, histogram of expense sizes, payment-method bars. Download the report as PDF.
- **Statement**: Debit and Credit columns (credit green, debit red), grouped by month with a month separator, filter all/credit/debit, balance after each entry. Download as PDF.
- **Settings**: profile, opening balance, credit-card handling, CSV export, demo data.

## Run it

```bash
conda create -n xpensebee python=3.12 -y
conda activate xpensebee
pip install -r requirements.txt
streamlit run app.py
```

Open the **Set up** screen, enter your name and exact bank balance, or press "explore with demo data". Run the tests with `pytest`.

## How the balance works

Balance = opening balance + income - expenses, counting only entries dated on or after the opening date. Credit-card spending reduces the balance by default; turn that off in Settings if you record the card bill payment instead. Amounts in other currencies are converted to SAR with a default rate you can override per entry.

## Notes and limits

- The bottom bar is a CSS-fixed container; inactive tabs show icons only on small screens. The offline phone app in `personal-app` is the real installable app.
- The sign-in is a local convenience (salted PBKDF2 hash in the SQLite file), not encryption of your data.
- The statement and expense tables open an entry for editing through the "Edit or delete an entry" picker rather than clicking a row.
- PDF text uses a standard font, so names in non-Latin scripts show as "?" in the PDF.
- Money is stored as integer minor units, never floats. The data file is `data/finance.db` (override with `EXPENSE_DB`) and is git-ignored.
