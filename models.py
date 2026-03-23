from typing import Any, Dict, List, Optional, Tuple

import datetime as dt
import pandas as pd

from db import execute

def create_user(username: str, password_hash: str) -> int:
    cur = execute(
        """
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
        """,
        (username, password_hash),
        commit=True,
    )
    return cur.lastrowid


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    cur = execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    return dict(row) if row else None

def create_budget(
    user_id: int,
    name: str,
    total_amount: float,
    start_date: Optional[str],
    end_date: Optional[str],
    frequency: Optional[str] = None,
    currency: Optional[str] = "TRY",
) -> int:
    cur = execute(
        """
        INSERT INTO budgets (user_id, name, total_amount, start_date, end_date, frequency, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, total_amount, start_date, end_date, frequency, currency),
        commit=True,
    )
    return cur.lastrowid

def update_budget(
    budget_id: int,
    name: str,
    total_amount: float,
    start_date: Optional[str],
    end_date: Optional[str],
    frequency: Optional[str] = None,
    currency: Optional[str] = "TRY",
) -> None:
    execute(
        """
        UPDATE budgets
        SET name = ?, total_amount = ?, start_date = ?, end_date = ?, frequency = ?, currency = ?
        WHERE id = ?
        """,
        (name, total_amount, start_date, end_date, frequency, currency, budget_id),
        commit=True,
    )

def delete_budget(budget_id: int) -> None:
    execute("DELETE FROM budgets WHERE id = ?", (budget_id,), commit=True)

def list_budgets_for_user(user_id: int) -> List[Dict[str, Any]]:
    cur = execute(
        """
        SELECT b.id,
               b.name,
               b.total_amount,
               b.start_date,
               b.end_date,
               b.frequency,
               b.currency
        FROM budgets b
        WHERE b.user_id = ?
        ORDER BY b.start_date IS NULL, b.start_date DESC
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]

def get_budget_by_id(budget_id: int) -> Optional[Dict[str, Any]]:
    cur = execute(
        """
        SELECT id, user_id, name, total_amount, start_date, end_date, frequency, currency
        FROM budgets
        WHERE id = ?
        """,
        (budget_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None

def create_transaction(
    budget_id: int,
    type_: str,
    category: str,
    amount: float,
    description: Optional[str],
    date: Optional[str],
) -> int:
    cur = execute(
        """
        INSERT INTO transactions (budget_id, type, category, amount, description, date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (budget_id, type_, category, amount, description, date),
        commit=True,
    )
    return cur.lastrowid

def update_transaction(
    transaction_id: int,
    type_: str,
    category: str,
    amount: float,
    description: Optional[str],
    date: Optional[str],
) -> None:
    execute(
        """
        UPDATE transactions
        SET type = ?, category = ?, amount = ?, description = ?, date = ?
        WHERE id = ?
        """,
        (type_, category, amount, description, date, transaction_id),
        commit=True,
    )

def delete_transaction(transaction_id: int) -> None:
    execute(
        "DELETE FROM transactions WHERE id = ?",
        (transaction_id,),
        commit=True,
    )

def list_transactions_for_budget(budget_id: int) -> List[Dict[str, Any]]:
    cur = execute(
        """
        SELECT id, budget_id, type, category, amount, description, date
        FROM transactions
        WHERE budget_id = ?
        ORDER BY date
        """,
        (budget_id,),
    )
    return [dict(row) for row in cur.fetchall()]

def get_budget_summary_and_frame(
    budget_id: int, total_amount: float
) -> Tuple[Dict[str, float], pd.DataFrame]:
    transactions = list_transactions_for_budget(budget_id)
    if transactions:
        df = pd.DataFrame(transactions)
    else:
        df = pd.DataFrame(
            columns=["id", "budget_id", "type", "category", "amount", "description", "date"]
        )

    planned = float(total_amount)
    income_tx_sum = float(
        df.loc[df["type"] == "income", "amount"].sum() if not df.empty else 0.0
    )
    total_income_display = planned
    total_expenses = float(
        df.loc[df["type"] == "expense", "amount"].sum() if not df.empty else 0.0
    )
    remaining = float(total_income_display - total_expenses)
    percentage_used = float((total_expenses / planned) * 100) if planned > 0 else 0.0

    summary = {
        "total_income": total_income_display,
        "total_expenses": total_expenses,
        "remaining": remaining,
        "percentage_used": percentage_used,
        "added_income": income_tx_sum,
    }
    return summary, df

def get_user_dashboard_summary(user_id: int) -> Tuple[pd.DataFrame, Dict[str, float]]:
    budgets = list_budgets_for_user(user_id)
    rows = []
    totals = {
        "total_budget_amount": 0.0,
        "total_income": 0.0,
        "total_expenses": 0.0,
        "total_remaining": 0.0,
    }

    for b in budgets:
        summary, _df = get_budget_summary_and_frame(
            budget_id=b["id"], total_amount=float(b["total_amount"])
        )
        row = {
            "id": b["id"],
            "name": b["name"],
            "total_amount": float(b["total_amount"]),
            "total_income": summary["total_income"],
            "total_expenses": summary["total_expenses"],
            "remaining": summary["remaining"],
            "percentage_used": summary["percentage_used"],
        }
        rows.append(row)

        totals["total_budget_amount"] += row["total_amount"]
        totals["total_income"] += row["total_income"]
        totals["total_expenses"] += row["total_expenses"]
        totals["total_remaining"] += row["remaining"]

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=[
            "id",
            "name",
            "total_amount",
            "total_income",
            "total_expenses",
            "remaining",
            "percentage_used",
        ]
    )
    return df, totals

def _parse_date(date_str: Optional[str]) -> Optional[dt.date]:
    if not date_str:
        return None
    try:
        return dt.date.fromisoformat(date_str)
    except ValueError:
        return None

def ensure_current_budget_for_user(user_id: int) -> None:
    budgets = list_budgets_for_user(user_id)
    if not budgets:
        return

    latest = budgets[0]
    freq = latest.get("frequency")
    end = _parse_date(latest.get("end_date"))
    start = _parse_date(latest.get("start_date"))

    if not freq or not end:
        return

    today = dt.date.today()
    if end >= today:
        return

    if start:
        period_days = (end - start).days
    else:
        period_days = 0

    if period_days <= 0:
        period_days = 6 if freq == "weekly" else 29

    new_start = end + dt.timedelta(days=1)
    if freq == "weekly":
        new_end = new_start + dt.timedelta(days=period_days)
    elif freq == "monthly":
        new_end = new_start + dt.timedelta(days=period_days)
    else:
        return

    create_budget(
        user_id=user_id,
        name=latest["name"],
        total_amount=float(latest["total_amount"]),
        start_date=new_start.isoformat(),
        end_date=new_end.isoformat(),
        frequency=freq,
        currency=latest.get("currency", "TRY"),
    )

