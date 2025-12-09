# app.py
"""
Water Buddy - Streamlit version (No SQLite, JSON file storage)
Run with: streamlit run app.py
"""

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
# Config
# ---------------------------
st.set_page_config(page_title="Water Buddy", layout="wide", initial_sidebar_state="expanded")

# ---------------------------
# Constants & File Paths
# ---------------------------
HERE = Path(__file__).parent
DATA_DIR = HERE / "water_buddy_data"
PROFILE_FILE = DATA_DIR / "profile.json"
LOGS_FILE = DATA_DIR / "logs.json"
BADGES_FILE = DATA_DIR / "badges.json"
BASE_ML_PER_KG = 35  # ml per kg base guideline

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------
# JSON Helpers
# ---------------------------
def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------------------
# Data functions
# ---------------------------
def get_profile() -> Optional[Dict]:
    data = read_json(PROFILE_FILE, None)
    return data

def set_profile(name: str, age: int, weight_kg: float, activity: str):
    data = {
        "name": name or "You",
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
    # update badges after writing log
    check_badges_and_streaks()

def get_totals_for_days(days: int = 7) -> List[Dict]:
    logs = read_logs()
    results = []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        total = 0
        for log in logs:
            try:
                dt = datetime.fromisoformat(log["logged_at"])
            except Exception:
                # ignore malformed entries
                continue
            if dt.date() == d:
                total += int(log.get("amount_ml", 0))
        results.append({"date": d, "total_ml": total})
    return results

def get_today_total() -> int:
    logs = read_logs()
    today = date.today()
    total = 0
    for log in logs:
        try:
            dt = datetime.fromisoformat(log["logged_at"])
        except Exception:
            continue
        if dt.date() == today:
            total += int(log.get("amount_ml", 0))
    return total

def export_logs_df() -> pd.DataFrame:
    logs = read_logs()
    if not logs:
        return pd.DataFrame(columns=["logged_at", "amount_ml"])
    df = pd.DataFrame(logs)
    # Ensure columns order
    if "logged_at" in df.columns and "amount_ml" in df.columns:
        df = df[["logged_at", "amount_ml"]]
    return df

def export_logs_csv_bytes() -> bytes:
    df = export_logs_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

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
    recent = totals[-3:] if len(totals) >= 3 else totals
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

# ---------------------------
# Badges & streaks (file-based)
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
    existing = {b['name'] for b in badges}

    totals = get_totals_for_days(7)
    goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
    good_days = sum(1 for t in totals if t['total_ml'] >= 0.75 * goal)

    # Award 7-day streak
    if good_days == 7 and "7-day-streak" not in existing:
        badges.append({"name": "7-day-streak", "earned_at": datetime.utcnow().isoformat()})

    # Award first-log
    logs = read_logs()
    if len(logs) >= 1 and "first-log" not in existing:
        badges.append({"name": "first-log", "earned_at": datetime.utcnow().isoformat()})

    # Save badges if changed
    if len(badges) != len(existing):
        write_badges(badges)
    else:
        # There might be new badges added (avoid duplicates) - ensure no duplicates then write
        names_now = {b['name'] for b in badges}
        if names_now != existing:
            write_badges(badges)

def get_badges() -> List[Tuple[str, str]]:
    badges = read_badges()
    # return list of (name, earned_at)
    return [(b.get("name", ""), b.get("earned_at", "")) for b in sorted(badges, key=lambda x: x.get("earned_at", ""), reverse=True)]

# ---------------------------
# Visuals (matplotlib)
# ---------------------------
def plot_progress_donut(consumed_ml: int, goal_ml: int):
    pct = min(1.0, consumed_ml / max(1, goal_ml))
    fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=80)
    ax.axis('equal')
    sizes = [pct, 1 - pct]
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
        offset = max(10, 0.02 * max(1, goal))
        ax.text(rect.get_x() + rect.get_width() / 2, height + offset, str(int(v)), ha='center', fontsize=8, color="#DFF9FF")
    ax.set_facecolor('#071927')
    fig.patch.set_facecolor('#071927')
    plt.tight_layout()
    return fig

# ---------------------------
# Initialize session state keys used for reminders
# ---------------------------
if 'rem_int' not in st.session_state:
    st.session_state['rem_int'] = 60
if 'reminders_enabled' not in st.session_state:
    st.session_state['reminders_enabled'] = False

# ---------------------------
# App header
# ---------------------------
col1, col2 = st.columns([1, 3])
with col1:
    st.image("https://img.icons8.com/fluency/96/water.png", width=72)
with col2:
    st.markdown("<h1 style='margin-bottom:0px; color:#00E5FF'>Water Buddy</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:#BFEFF6'>No-SQLite Edition — File storage</div>", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------
# Sidebar: Profile + Quick actions + Reminders
# ---------------------------
with st.sidebar:
    st.markdown("### Profile")
    profile = get_profile()
    if profile:
        st.markdown(f"**{profile.get('name','You')}**  \nAge: {profile.get('age','-')}  \nWeight: {profile.get('weight_kg','-')} kg  \nActivity: {profile.get('activity','-')}")
    else:
        st.info("No profile set yet. Fill the form below and click Save.")

    with st.expander("Edit / Create profile"):
        name = st.text_input("Name", value=profile['name'] if profile and profile.get('name') else "")
        age = st.number_input("Age", min_value=1, max_value=120, value=int(profile['age']) if profile and profile.get('age') is not None else 25)
        weight = st.number_input("Weight (kg)", min_value=20.0, max_value=300.0, value=float(profile['weight_kg']) if profile and profile.get('weight_kg') is not None else 65.0)
        activities = ['low', 'normal', 'high']
        index = activities.index(profile['activity']) if profile and profile.get('activity') in activities else 1
        activity = st.selectbox("Activity level", options=activities, index=index)
        if st.button("Save profile"):
            set_profile(name or "You", age, weight, activity)
            st.success("Profile saved.")
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
    remind_interval = st.number_input("Interval (minutes)", min_value=5, max_value=240, value=default_interval, step=5, key="rem_int_input")
    if st.button("Enable reminders"):
        st.session_state['reminders_enabled'] = True
        st.session_state['rem_int'] = int(remind_interval)
        st.components.v1.html("<script>window.startWaterBuddyReminders();</script>", height=0)
        st.success(f"Reminders enabled every {int(remind_interval)} minutes (browser notifications).")
    if st.button("Disable reminders"):
        st.session_state['reminders_enabled'] = False
        st.components.v1.html("<script>window.stopWaterBuddyReminders();</script>", height=0)
        st.info("Reminders disabled.")

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

# ---------------------------
# Main area
# ---------------------------
profile = get_profile()
if profile:
    try:
        goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
    except Exception:
        goal = 2000
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

# ---------------------------
# Notification JS (client-side reminders)
# ---------------------------
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
// Auto-start reminders if enabled in session_state
if ({'true' if st.session_state.get('reminders_enabled', False) else 'false'}) {{
    askPermissionAndStart();
}}
</script>
"""
st.components.v1.html(notification_js, height=0)

st.markdown("---")
st.markdown("Built from a Tkinter prototype — ported to Streamlit. Keep this tab open to receive browser reminders.")
