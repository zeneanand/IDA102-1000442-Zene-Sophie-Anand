# Water Buddy - Streamlit version (No SQLite, JSON File Storage)
# Run with: streamlit run app.py

import streamlit as st
import json
from datetime import datetime, date, timedelta
import io
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# ---------------------------
# Constants & File Paths
# ---------------------------
HERE = Path(__file__).parent
DATA_DIR = HERE / "water_buddy_data"
PROFILE_FILE = DATA_DIR / "profile.json"
LOGS_FILE = DATA_DIR / "logs.json"
BADGES_FILE = DATA_DIR / "badges.json"
BASE_ML_PER_KG = 35  # ml per kg

DATA_DIR.mkdir(exist_ok=True)

# ---------------------------
# JSON Helpers
# ---------------------------
def read_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------------------------
# Data functions
# ---------------------------
def get_profile() -> Optional[Dict]:
    return read_json(PROFILE_FILE, None)

def set_profile(name: str, age: int, weight_kg: float, activity: str):
    data = {
        "name": name,
        "age": int(age),
        "weight_kg": float(weight_kg),
        "activity": activity,
        "created_at": datetime.utcnow().isoformat(),
    }
    write_json(PROFILE_FILE, data)

def read_logs() -> List[Dict]:
    return read_json(LOGS_FILE, [])

def write_logs(logs: List[Dict]):
    write_json(LOGS_FILE, logs)

def log_water_ml(amount_ml: int):
    logs = read_logs()
    logs.append({
        "logged_at": datetime.utcnow().isoformat(),
        "amount_ml": int(amount_ml)
    })
    write_logs(logs)
    check_badges_and_streaks()

def get_totals_for_days(days: int = 7) -> List[Dict]:
    logs = read_logs()
    results = []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        total = 0
        for log in logs:
            t = datetime.fromisoformat(log["logged_at"]).date()
            if t == d:
                total += log["amount_ml"]
        results.append({"date": d, "total_ml": total})
    return results

def get_today_total() -> int:
    logs = read_logs()
    today = date.today()
    return sum(log["amount_ml"] for log in logs if datetime.fromisoformat(log["logged_at"]).date() == today)

def export_logs_df() -> pd.DataFrame:
    logs = read_logs()
    if not logs:
        return pd.DataFrame(columns=["logged_at", "amount_ml"])
    return pd.DataFrame(logs)

def export_logs_csv_bytes() -> bytes:
    df = export_logs_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# ---------------------------
# Business Logic
# ---------------------------
def calculate_goal_ml(weight_kg: float, age: Optional[int] = None, activity: str = 'normal', weather_temp_c: Optional[float] = None) -> int:
    base = weight_kg * BASE_ML_PER_KG
    multiplier = 1.0
    if activity == "low": multiplier *= 0.95
    elif activity == "high": multiplier *= 1.2
    if age is not None and age >= 65: multiplier *= 0.9
    if weather_temp_c is not None:
        if weather_temp_c >= 30: multiplier *= 1.25
        elif weather_temp_c >= 25: multiplier *= 1.10
    return int(base * multiplier)

def estimate_bottles_saved(total_ml: float, bottle_size_ml: int = 500) -> float:
    try:
        return total_ml / bottle_size_ml
    except:
        return 0.0

def predictor_adjustment() -> float:
    totals = get_totals_for_days(7)
    recent = totals[-3:]
    avg = sum(t['total_ml'] for t in recent) / max(1, len(recent))
    profile = get_profile()
    if not profile: return 1.0
    goal = calculate_goal_ml(profile['weight_kg'], profile['age'], profile['activity'])
    if avg < 0.7 * goal: return 1.2
    elif avg < 0.9 * goal: return 1.05
    return 1.0

# ---------------------------
# Badges
# ---------------------------
def read_badges():
    return read_json(BADGES_FILE, [])


def write_badges(badges):
    write_json(BADGES_FILE, badges)


def check_badges_and_streaks():
    profile = get_profile()
    if not profile:
        return

    badges = read_badges()
    badge_names = {b['name'] for b in badges}

    totals = get_totals_for_days(7)
    goal = calculate_goal_ml(profile['weight_kg'], profile['age'], profile['activity'])
    good_days = sum(1 for t in totals if t['total_ml'] >= 0.75 * goal)

    # 7-day streak badge
    if good_days == 7 and "7-day-streak" not in badge_names:
        badges.append({"name": "7-day-streak", "earned_at": datetime.utcnow().isoformat()})

    # First log badge
    logs = read_logs()
    if len(logs) >= 1 and "first-log" not in badge_names:
        badges.append({"name": "first-log", "earned_at": datetime.utcnow().isoformat()})

    write_badges(badges)


def get_badges() -> List[Tuple[str, str]]:
    badges = read_badges()
    return [(b["name"], b["earned_at"]) for b in badges]

# ---------------------------
# Matplotlib Visuals
# ---------------------------
def plot_progress_donut(consumed_ml: int, goal_ml: int):
    pct = min(1.0, consumed_ml / max(1, goal_ml))
    fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=80)
    ax.axis("equal")
    sizes = [pct, 1 - pct]
    colors = ["#00E5FF", "#04262B"]
    ax.pie(sizes, startangle=90, colors=colors, wedgeprops=dict(width=0.38))
    c = Circle((0, 0), 0.62, color="#071927")
    ax.add_patch(c)
    ax.text(0, 0.08, f"{int(pct*100)}%", ha="center", fontsize=18, color="#CFF8FF", weight="bold")
    ax.text(0, -0.18, f"{consumed_ml} / {goal_ml} ml", ha="center", fontsize=9, color="#AEEFF6")
    fig.patch.set_facecolor('#071927')
    ax.set_facecolor('#071927')
    plt.tight_layout()
    return fig


def plot_weekly_bars(totals: List[Dict], goal: int):
    dates = [t['date'].strftime('%a') for t in totals]
    vals = [t['total_ml'] for t in totals]
    fig, ax = plt.subplots(figsize=(6, 3.2), dpi=80)
    bars = ax.bar(dates, vals, color="#00CFEA", alpha=0.95)
    ax.axhline(goal, color='#89F9FF', linestyle='--', linewidth=1)
    ax.set_ylabel("ml")
    for rect, v in zip(bars, vals):
        ax.text(rect.get_x()+rect.get_width()/2, rect.get_height()+10, str(v), ha='center', color="#DFF9FF", fontsize=8)
    fig.patch.set_facecolor('#071927')
    ax.set_facecolor('#071927')
    plt.tight_layout()
    return fig

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Water Buddy", layout="wide", initial_sidebar_state="expanded")

# Header
col1, col2 = st.columns([1,3])
with col1:
    st.image("https://img.icons8.com/fluency/96/water.png", width=72)
with col2:
    st.markdown("<h1 style='color:#00E5FF'>Water Buddy</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:#BFEFF6'>No-SQLite Edition — File Storage</div>", unsafe_allow_html=True)

st.markdown("---")

# Sidebar
with st.sidebar:
    st.markdown("### Profile")
    profile = get_profile()
    if profile:
        st.write(f"**{profile['name']}**  ")
        st.write(f"Age: {profile['age']}")
        st.write(f"Weight: {profile['weight_kg']} kg")
        st.write(f"Activity: {profile['activity']}")
    else:
        st.info("No profile set.")

    with st.expander("Create / Edit Profile"):
        name = st.text_input("Name", value=profile['name'] if profile else "")
