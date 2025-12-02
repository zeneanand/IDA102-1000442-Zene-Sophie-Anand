# app.py
"""
Water Buddy - Streamlit version (final, fixed)
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
    check_badges_and_streaks()

def get_totals_for_days(days: int = 7) -> List[Dict]:
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

        # first-log badge: award when there is at least one log and badge doesn't exist yet
        c.execute('SELECT COUNT(*) FROM logs')
        total_logs_row = c.fetchone()
        total_logs = int(total_logs_row[0]) if total_logs_row and total_logs_row[0] else 0

        c.execute('SELECT * FROM badges WHERE name = ?', ('first-log',))
        first_log_badge_exists = bool(c.fetchone())

        if total_logs >= 1 and not first_log_badge_exists:
            c.execute('INSERT INTO badges (name, earned_at) VALUES (?, ?)', ('first-log', datetime.utcnow().isoformat()))

        conn.commit()

def get_badges() -> List[Tuple[str, str]]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute('SELECT name, earned_at FROM badges ORDER BY earned_at DESC')
        rows = c.fetchall()
    return rows

# ---------------------------
# Visuals (matplotlib)
# ---------------------------
def plot_progress_donut(consumed_ml: int, goal_ml: int):
    pct = min(1.0, consumed_ml / max(1, goal_ml))
    fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=80)
    ax.axis('equal')
    achieved = pct
    sizes = [achieved, 1 - achieved]
    colors = ["#00E5FF", "#04262B"]
    wedges, _ = ax.pie(sizes, startangle=90, colors=colors, wedgeprops=dict(width=0.38))
    c = Circle((0, 0), 0.62, color="#071927")
    ax.add_patch(c)
    ax.text(0, 0.08, f"{int(pct*100)}%", ha='center', va='center', fontsize=18, color="#CFF8FF", weight='bold')
    ax.text(0, -0.18, f"{int(consumed_ml)} / {int(goal_ml)} ml", ha='center', va='center', fontsize=9, color="#AEEFF6")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.patch.set_facecolor('#071927')
    ax.set_facecolor('#071927')
    plt.tight_layout()
    return fig

def plot_weekly_bars(totals: List[Dict], goal: int):
    dates = [t['date'].strftime("%a") for t in totals]
    vals = [t['total_ml'] for t in totals]
    fig, ax = plt.subplots(figsize=(6, 3.2), dpi=80)
    bars = ax.bar(dates, vals, color="#00CFEA", alpha=0.95)
    ax.axhline(goal, color='#89F9FF', linestyle='--', linewidth=1)
    ax.set_ylabel("ml")
    ax.set_title("Weekly Hydration (ml)")
    for rect, v in zip(bars, vals):
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width() / 2, height + max(10, 0.02 * max(1, goal)), str(int(v)), ha='center', fontsize=8, color="#DFF9FF")
    ax.set_facecolor('#071927')
    fig.patch.set_facecolor('#071927')
    plt.tight_layout()
    return fig

# ---------------------------
# Streamlit app UI
# ---------------------------
st.set_page_config(page_title="Water Buddy", layout="wide", initial_sidebar_state="expanded")

# App header
col1, col2 = st.columns([1, 3])
with col1:
    st.image("https://img.icons8.com/fluency/96/water.png", width=72)
with col2:
    st.markdown("<h1 style='margin-bottom:0px; color:#00E5FF'>Water Buddy</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:#BFEFF6'>Formative Assessment 1 — Python · Streamlit port</div>", unsafe_allow_html=True)

st.markdown("---")

# Sidebar: Profile + Quick actions + Reminders
with st.sidebar:
    st.markdown("### Profile")
    profile = get_profile()
    if profile:
        st.markdown(f"**{profile['name']}**  \\nAge: {profile['age']}  \\nWeight: {profile['weight_kg']} kg  \\nActivity: {profile['activity']}")
    else:
        st.info("No profile set yet. Fill the form below and click Save.")

    with st.expander("Edit / Create profile"):
        name = st.text_input("Name", value=profile['name'] if profile else "")
        age = st.number_input("Age", min_value=1, max_value=120, value=int(profile['age']) if profile and profile.get('age') is not None else 25)
        weight = st.number_input("Weight (kg)", min_value=20.0, max_value=300.0, value=float(profile['weight_kg']) if profile and profile.get('weight_kg') is not None else 65.0)
        activities = ['low', 'normal', 'high']
        index = activities.index(profile['activity']) if profile and profile.get('activity') in activities else 1
        activity = st.selectbox("Activity level", options=activities, index=index)
        if st.button("Save profile"):
            set_profile(name or "You", age, weight, activity)
            st.success("Profile saved. Refreshing...")
            st.experimental_rerun()

    st.markdown("---")
    st.markdown("### Quick Log")
    qcol1, qcol2 = st.columns(2)
    with qcol1:
        if st.button("+50 ml"):
            log_water_ml(50)
            st.success("Logged 50 ml")
            st.experimental_rerun()
        if st.button("+250 ml"):
            log_water_ml(250)
            st.success("Logged 250 ml")
            st.experimental_rerun()
    with qcol2:
        if st.button("+100 ml"):
            log_water_ml(100)
            st.success("Logged 100 ml")
            st.experimental_rerun()
        if st.button("+500 ml"):
            log_water_ml(500)
            st.success("Logged 500 ml")
            st.experimental_rerun()

    st.markdown("Custom log (ml)")
    custom_ml = st.number_input("", min_value=1, step=50, value=250, key="custom_ml_input")
    if st.button("Log custom"):
        log_water_ml(custom_ml)
        st.success(f"Logged {custom_ml} ml")
        st.experimental_rerun()

    st.markdown("---")
    st.markdown("### Reminders (browser)")
    default_interval = int(st.session_state.get("rem_int", 60))
    remind_interval = st.number_input("Interval (minutes)", min_value=5, max_value=240, value=default_interval, step=5, key="rem_int")
    start_reminders = st.button("Enable reminders")
    stop_reminders = st.button("Disable reminders")
    st.markdown("**Note:** Notifications use the browser Notification API. Keep the app tab open and allow notifications when asked.")

    st.markdown("---")
    st.markdown("### Utilities")
    csv_bytes = export_logs_csv_bytes()
    st.download_button("Export logs CSV", data=csv_bytes, file_name="water_buddy_logs.csv", mime="text/csv")
    if st.button("Show Badges"):
        badges = get_badges()
        if badges:
            for name, earned in badges:
                st.write(f"- **{name}** (earned {earned[:10]})")
        else:
            st.info("No badges yet.")

# Main area
profile = get_profile()
if profile:
    goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
else:
    goal = 2000

today = get_today_total()
st.markdown(f"### Goal: **{goal} ml**  —  Today: **{today} ml**")

left_col, right_col = st.columns([1, 2])
with left_col:
    st.markdown("#### Progress")
    fig = plot_progress_donut(today, goal)
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("#### AI Suggestion")
    adj = predictor_adjustment()
    if adj > 1.05:
        st.info("We noticed recent intake is below goal — consider smaller frequent sips. We'll nudge more often.")
    else:
        st.success("You're doing well! Keep the streak going.")

with right_col:
    st.markdown("#### Weekly Hydration")
    totals = get_totals_for_days(7)
    fig2 = plot_weekly_bars(totals, goal)
    st.pyplot(fig2)
    plt.close(fig2)

st.markdown("### Insights")
col_a, col_b, col_c = st.columns(3)
with col_a:
    totals14 = get_totals_for_days(14)
    avg14 = int(sum(t['total_ml'] for t in totals14) / max(1, len(totals14)))
    st.metric("14-day average (ml)", avg14)
with col_b:
    total_week = sum(t['total_ml'] for t in totals)
    bottles = estimate_bottles_saved(total_week, 500)
    st.metric("This week's total (ml)", int(total_week))
    st.metric("Refill bottles (500ml)", f"{bottles:.1f}")
with col_c:
    badges = get_badges()
    st.write("Badges")
    if badges:
        for name, earned in badges:
            st.write(f"- **{name}** (earned {earned[:10]})")
    else:
        st.write("_No badges yet._")

st.markdown("---")
st.markdown("### Eco Mode — Environmental impact")
eco_col1, eco_col2 = st.columns([2, 1])
with eco_col1:
    st.write(f"This week you consumed **{int(total_week)} ml**.")
    st.write(f"Equivalent refillable bottles used: **{bottles:.1f}** (500 ml)")
    co2_saved_kg = bottles * 0.082
    st.write(f"Estimated CO₂ saved: **{co2_saved_kg:.2f} kg**")
with eco_col2:
    if st.button("Log 250 ml (quick)"):
        log_water_ml(250)
        st.success("Logged 250 ml")
        st.experimental_rerun()

st.markdown("---")
st.markdown("### How suggestions are generated")
st.write("The predictor checks the last few days' average vs. your daily goal and adjusts nudges if you're below 70% or 90% thresholds.")

with st.expander("Show raw logs"):
    df = export_logs_df()
    if df.empty:
        st.info("No logs yet.")
    else:
        st.dataframe(df)

# Notification JS (client-side reminders)
if 'rem_int' not in st.session_state:
    st.session_state['rem_int'] = 60
if 'reminders_enabled' not in st.session_state:
    st.session_state['reminders_enabled'] = False

notification_js = f"""
<script>
const intervalMinutes = {int(st.session_state.get('rem_int', 60))};
let timerId = null;
function askPermissionAndStart() {{
    if (!("Notification" in window)) {{
        console.log("This browser does not support notifications.");
        return;
    }}
    if (Notification.permission === "granted") {{
        startTimer();
    }} else if (Notification.permission !== "denied") {{
        Notification.requestPermission().then(permission => {{
            if (permission === "granted") startTimer();
        }});
    }}
}}
function startTimer() {{
    if (timerId) clearInterval(timerId);
    timerId = setInterval(() => {{
        const notif = new Notification("Water Buddy — Time to sip!", {{
            body: "Open the app to log a quick drink. Stay hydrated! 💧",
            icon: ""
        }});
        setTimeout(()=>notif.close(), 8000);
    }}, intervalMinutes * 60 * 1000);
}}
function stopTimer() {{
    if (timerId) clearInterval(timerId);
    timerId = null;
}}
window.startWaterBuddyReminders = askPermissionAndStart;
window.stopWaterBuddyReminders = stopTimer;
</script>
"""
st.components.v1.html(notification_js, height=0)

# React to sidebar start/stop buttons (session_state is updated earlier in sidebar)
# Because start_reminders/stop_reminders are defined in the sidebar block, they exist in this scope.
if 'start_reminders' in locals() and start_reminders:
    st.session_state['reminders_enabled'] = True
    st.session_state['rem_int'] = int(remind_interval)
    st.components.v1.html("<script>window.startWaterBuddyReminders();</script>", height=0)
    st.success(f"Reminders enabled every {int(remind_interval)} minutes (browser notifications).")

if 'stop_reminders' in locals() and stop_reminders:
    st.session_state['reminders_enabled'] = False
    st.components.v1.html("<script>window.stopWaterBuddyReminders();</script>", height=0)
    st.info("Reminders disabled.")

st.markdown("---")
st.markdown("Built from a Tkinter prototype — ported to Streamlit. Keep this tab open to receive browser reminders.")
