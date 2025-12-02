# app.py
"""
Water Buddy - Streamlit version (cleaned & fixed)
Run with: streamlit run app.py
"""

import streamlit as st
import sqlite3
from datetime import datetime, date, timedelta
import io
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# ---------------------------
# Constants & DB
# ---------------------------
HERE = Path(__file__).parent
DB_PATH = HERE / "water_buddy_local.db"
BASE_ML_PER_KG = 35  # ml per kg base guideline

# ---------------------------
# Database helpers
# ---------------------------
def get_conn():
    # ensure the folder exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return conn

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY,
                name TEXT,
                age INTEGER,
                weight_kg REAL,
                activity TEXT,
                created_at TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY,
                logged_at TEXT,
                amount_ml INTEGER
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY,
                name TEXT,
                earned_at TEXT
            )
            """
        )
        conn.commit()

init_db()

# ---------------------------
# Data functions
# ---------------------------
def get_profile() -> Optional[Dict]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM profile ORDER BY id DESC LIMIT 1')
        row = c.fetchone()
    if row:
        return {'id': row[0], 'name': row[1], 'age': row[2], 'weight_kg': row[3], 'activity': row[4], 'created_at': row[5]}
    return None

def set_profile(name: str, age: int, weight_kg: float, activity: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            'INSERT INTO profile (name, age, weight_kg, activity, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, int(age), float(weight_kg), activity, datetime.utcnow().isoformat())
        )
        conn.commit()

def log_water_ml(amount_ml: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO logs (logged_at, amount_ml) VALUES (?, ?)', (datetime.utcnow().isoformat(), int(amount_ml)))
        conn.commit()
    # update badges and streaks after a successful insert
    check_badges_and_streaks()

def get_totals_for_days(days: int = 7) -> List[Dict]:
    """Return list of dicts: [{'date': date, 'total_ml': int}, ...] for the last `days` days (oldest -> newest)."""
    results = []
    with get_conn() as conn:
        c = conn.cursor()
        for i in range(days-1, -1, -1):
            d = date.today() - timedelta(days=i)
            start = datetime.combine(d, datetime.min.time()).isoformat()
            end = datetime.combine(d, datetime.max.time()).isoformat()
            c.execute('SELECT SUM(amount_ml) FROM logs WHERE logged_at BETWEEN ? AND ?', (start, end))
            row = c.fetchone()
            total = int(row[0]) if row and row[0] else 0
            results.append({'date': d, 'total_ml': total})
    return results

def get_today_total() -> int:
    with get_conn() as conn:
        c = conn.cursor()
        start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        end = datetime.combine(date.today(), datetime.max.time()).isoformat()
        c.execute('SELECT SUM(amount_ml) FROM logs WHERE logged_at BETWEEN ? AND ?', (start, end))
        row = c.fetchone()
    return int(row[0]) if row and row[0] else 0

def export_logs_df() -> pd.DataFrame:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute('SELECT logged_at, amount_ml FROM logs ORDER BY logged_at')
        rows = c.fetchall()
    df = pd.DataFrame(rows, columns=['logged_at', 'amount_ml'])
    return df

def export_logs_csv_bytes() -> bytes:
    df = export_logs_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')

# ---------------------------
# Business logic
# ---------------------------
def calculate_goal_ml(weight_kg: float, age: Optional[int] = None, activity: str = 'normal', weather_temp_c: Optional[float] = None) -> int:
    base = weight_kg * BASE_ML_PER_KG
    multiplier = 1.0
    if activity == 'low':
        multiplier *= 0.95
    elif activity == 'high':
        multiplier *= 1.2
    if age is not None and age >= 65:
        multiplier *= 0.9
    if weather_temp_c is not None:
        if weather_temp_c >= 30:
            multiplier *= 1.25
        elif weather_temp_c >= 25:
            multiplier *= 1.10
    return int(base * multiplier)

def estimate_bottles_saved(total_ml: float, bottle_size_ml: int = 500) -> float:
    try:
        return float(total_ml) / float(bottle_size_ml)
    except Exception:
        return 0.0

def predictor_adjustment() -> float:
    totals = get_totals_for_days(7)
    # take the last up-to-3 days (safely)
    recent = totals[-3:] if len(totals) >= 1 else totals
    count = len(recent) if len(recent) > 0 else 1
    avg = sum(t['total_ml'] for t in recent) / count
    profile = get_profile()
    if not profile:
        return 1.0
    goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
    if avg < 0.7 * goal:
        return 1.2
    elif avg < 0.9 * goal:
        return 1.05
    else:
        return 1.0

# Badges & streaks
def check_badges_and_streaks():
    with get_conn() as conn:
        c = conn.cursor()
        profile = get_profile()
        if not profile:
            return
        totals = get_totals_for_days(7)
        goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
        good_days = sum(1 for t in totals if t['total_ml'] >= 0.75 * goal)
        # 7-day streak badge
        c.execute('SELECT * FROM badges WHERE name = ?', ('7-day-streak',))
        if good_days == 7 and not c.fetchone():
            c.execute('INSERT INTO badges (name, earned_at) VALUES (?, ?)', ('7-day-streak', datetime.utcnow().isoformat()))
        # first-log badge
        c.execute('SELECT COUNT(*) FROM logs')
        total_logs = c.fetchone()[0]
        c.execute('SELECT * FROM badges WHERE name = ?', ('first-log',))
        if total_logs >= 1:
