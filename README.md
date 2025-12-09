
NAME - ZENE-SOPHIE-ANAND  
WACP no-1000442 
CRS -PYTHON
COURSE NAME - IBCP (AI)   
SCHOOL NAME - Aspen Nutan Academy 
# **README.md**

# 🧊 Water Buddy — Hydration Tracker (No-SQL, Streamlit)

Water Buddy is a lightweight hydration-tracking app built using **Streamlit** and **file-based storage (JSON)** instead of SQLite.
It helps users build healthier water-drinking habits through goals, logs, badges, eco-mode, and progress tracking.

This project is perfect for beginners learning:

* Streamlit UI development
* File-based persistence (without databases)
* State management
* Health & wellness tracking logic

---

## 🚀 **Features**

### ✅ **User Profile**

* Set **name**, **age**, **weight**, **activity level**, and **daily water goal**
* Auto-saves to `data/profile.json`

### 💧 **Easy Water Logging**

* Quick Log buttons (+50 ml, +100 ml, +250 ml, +500 ml)
* Custom amount entry
* Logs stored per day in `data/logs.json`

### 🌱 **Eco Mode**

* Enables minimal-impact hydration suggestions
* Logs eco-drinks like infused water
* Works with all tracking features

### 🏅 **Badges & Achievements**

Earn badges for:

* Completing your daily goal
* 7-day streak
* 1-liter challenge
  Badges saved in `data/badges.json`

### 📊 **Analytics**

* Daily progress bar
* Total water consumed
* How much is left
* “Push For Today” motivation badge (auto-generated)

### 📝 **Persistent Storage (No Database)**

* All data stored in **JSON files**
* Completely offline
* No SQLite, no SQL code

---

## 📂 **Project Structure**

```
water-buddy/
│
├── app.py                 # Main Streamlit application
│
├── data/
│   ├── profile.json       # Profile storage
│   ├── logs.json          # Daily logs
│   └── badges.json        # User achievements
│
├── images/
│   ├── logo.png           # Optional app logo
│   └── badges/            # Badge images (optional)
│
└── README.md              # Project documentation
```

---

## 🛠️ **Installation & Setup**

### **1. Clone the repository**

```bash
git clone https://github.com/your-username/water-buddy.git
cd water-buddy
```

### **2. Install dependencies**

```bash
pip install streamlit
```

(If your project uses extra libraries, add them here.)

### **3. Run the app**

```bash
streamlit run app.py
```

---

## 📁 **Data Storage Details**

Water Buddy stores all information in local JSON files:

| File           | Purpose                            |
| -------------- | ---------------------------------- |
| `profile.json` | User profile information           |
| `logs.json`    | Daily water logs (date → total ml) |
| `badges.json`  | Achievement progress               |

This keeps the app simple, portable, and easy to deploy—**no database setup required**.

---





---

## 🧑‍💻 **Contributing**

Feel free to:

* Submit pull requests
* Open issues
* Suggest features

Contributions are welcome!

---



## ❤️ Acknowledgements

Built using:

* **Streamlit**
* **Python**
* **JSON-based storage**
* Hydration science guidelines


