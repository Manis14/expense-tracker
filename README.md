# 💸 Expense Tracker with Forecasting

A web-based **Expense Tracker** built with **FastAPI**, **PostgreSQL**, and integrated with **ARIMA-based forecasting** and **Plotly visualizations**. Users can register, log in, manage expenses, analyze spending habits, and forecast future expenses.

---

## 🚀 Features

- 🔐 User Authentication (Register/Login/Logout)
- 📆 Add, Edit, Filter, Delete Expenses
- 📊 Visual Analysis using Plotly (Daily/Monthly trends)
- ⏳ Forecast future expenses using ARIMA
- 📁 HTML templating using Jinja2
- 📚 PostgreSQL for persistent storage

---

## 🧠 Tech Stack

| Area            | Technology             |
|-----------------|------------------------|
| Backend         | FastAPI                |
| Frontend        | Jinja2 + HTML/CSS      |
| Styling         | Custom CSS (static folder) |
| Database        | PostgreSQL             |
| Forecast Model  | ARIMA (Statsmodels)    |
| Visualization   | Plotly Express         |
| Authentication  | bcrypt                 |

---

## 📁 Project Structure
expense-tracker/
│
├── static/ # CSS files
│ └── style.css
│
├── templates/ # HTML templates (Jinja2)
│ ├── index.html
│ ├── login.html
│ ├── registration.html
│ ├── view_expense.html
│ ├── add_expense.html
│ ├── edit_expense.html
│ ├── analyze_expense.html
│ ├── filter_expense.html
│ ├── checking_plot.html
│ └── error.html
│
├── Forecast.py # ARIMA model logic
├── checking_plotly.py # Plotly visualizations
├── database.py # PostgreSQL connection and CRUD
├── main.py # FastAPI app entry point
├── mail_config.py # Password reset via email
├── requirements.txt
└── .env # Environment variables (DB, email)


---

## 🛠️ Installation & Setup

### ✅ 1. Clone the Repository

```bash
git clone https://github.com/your-username/expense-tracker.git
cd expense-tracker
```
### 2. Install Requirements
```bash
pip install -r requirements.txt
```
### 3. Set Up *.env*
```bash
DATABASE_URL=your_postgresql_url
MAIL_USERNAME=youremail@example.com
MAIL_PASSWORD=yourpassword
MAIL_FROM=youremail@example.com
SECRET_KEY=your_secret_key
```

### 4. Run the app 
```bash
uvicorn main:app --reload
```

📈 Forecasting Model (ARIMA)
The app uses ARIMA (AutoRegressive Integrated Moving Average) to:

  - Train on user's historical expenses
  - Forecast future spending trends
  - Visualize predictions using Plotly charts

Implemented in ''' Forecast.py'''.





