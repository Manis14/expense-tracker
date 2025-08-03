import calendar
from datetime import datetime
from typing import Optional, List
import bcrypt
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from plotly.io import to_html
from starlette.middleware.sessions import SessionMiddleware
from Forecast import ForeCast
from database import Database
from mail_config import send_reset_email

load_dotenv()

app = FastAPI(title="Expense Tracker", description="Personal Expense Management System")
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key-change-in-production")

# Add static files support
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
db = Database()
db.initialize_schema()
# Add password hashing functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    user_email = request.session.get("user_email")
    if user_email:
        user_name = str.title(db.get_user_name(user_email))
        user_id = db.get_user_id(user_email)

        # Get dashboard statistics
        dashboard_stats = db.get_dashboard_stats(user_id)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user_name": user_name,
            "dashboard_stats": dashboard_stats
        })
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})

@app.post("/registration", response_class=HTMLResponse)
async def registration(request: Request, user: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        count = db.email_verification(email)
        if count == 0:
            hashed_password = hash_password(password)
            db.add_user_database(user, email, hashed_password)
            message = "User registered successfully! Please login."
            message_type = "success"
        else:
            message = "User already exists with this email."
            message_type = "error"

        return templates.TemplateResponse("registration.html", {
            "request": request,
            "message": message,
            "message_type": message_type
        })
    except Exception as e:
        return templates.TemplateResponse("registration.html", {
            "request": request,
            "message": "Registration failed. Please try again.",
            "message_type": "error"
        })

@app.get("/forgot-password", response_class=HTMLResponse)
def show_forgot_password(request: Request):
    return templates.TemplateResponse("forgot-password.html", {"request": request})

@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request, background_tasks: BackgroundTasks, name: str = Form(...), email: str = Form(...)):
    try:
        count = db.email_verification(email)
        if count == 1:
            background_tasks.add_task(send_reset_email, email, name)
            message = f"A password reset link has been sent to {email}."
        else:
            message = "Email not registered."
        return templates.TemplateResponse("forgot-password.html", {"request": request, "message": message})
    except Exception as e:
        return templates.TemplateResponse("forgot-password.html", {"request": request, "message": "Error occurred"})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        if db.login(email, password):
            request.session["user_email"] = email
            return RedirectResponse(url="/", status_code=302)
        else:
            return templates.TemplateResponse("login.html", {"request": request, "message": "Invalid credentials"})
    except Exception as e:
        return templates.TemplateResponse("login.html", {"request": request, "message": "Login failed"})

@app.get("/add-expense", response_class=HTMLResponse)
async def add_expense(request: Request):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    try:
        user_id = db.get_user_id(user_email)
        categories = db.fetch_categories()
        today_stats = db.get_today_stats(user_id)

        return templates.TemplateResponse("add_expense.html", {
            "request": request,
            "categories": categories,
            "today_stats": today_stats
        })
    except Exception as e:
        print(f"Error loading add expense page: {e}")
        categories = db.fetch_categories()
        return templates.TemplateResponse("add_expense.html", {
            "request": request,
            "categories": categories,
            "today_stats": {'count': 0, 'amount': 0.0}
        })

@app.post("/submit-expense", response_class=HTMLResponse)
def submit_expense(
        request: Request,
        amount: float = Form(...),
        description: str = Form(None),
        date: str = Form(...),
        category: str = Form(...)
):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        user_id = db.get_user_id(user_email)
        db.insert_expense(amount, description or None, date_obj, category, user_id)
        return RedirectResponse("/add-expense?success=true", status_code=303)
    except Exception as e:
        print(f"Error adding expense: {e}")
        return RedirectResponse("/add-expense?error=true", status_code=303)

@app.get("/view-expense", response_class=HTMLResponse)
def view_expense(request: Request,
                 start_date: Optional[str] = Query(None),
                 end_date: Optional[str] = Query(None),
                 category: Optional[List[str]] = Query(None),
                 min_amount: Optional[str] = Query(None),
                 max_amount: Optional[str] = Query(None)):
    try:
        user_email = request.session.get("user_email")
        if not user_email:
            return RedirectResponse("/", status_code=302)

        user_id = db.get_user_id(user_email)

        # Convert empty strings to None and validate float values
        min_amount_float = None
        max_amount_float = None

        if min_amount and min_amount.strip():
            try:
                min_amount_float = float(min_amount)
            except ValueError:
                min_amount_float = None

        if max_amount and max_amount.strip():
            try:
                max_amount_float = float(max_amount)
            except ValueError:
                max_amount_float = None

        # Handle multiple categories - improved handling
        categories_filter = None
        if category:
            # Filter out empty strings and None values
            categories_filter = [cat.strip() for cat in category if cat and cat.strip()]
            if not categories_filter:
                categories_filter = None

        # Fetch filtered expenses
        expenses = db.fetch_filtered_expenses(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            categories=categories_filter,
            min_amount=min_amount_float,
            max_amount=max_amount_float
        )

        # Get all categories for filter
        categories = db.fetch_categories()

        return templates.TemplateResponse("view_expense.html", {
            "request": request,
            "expenses": expenses,
            "categories": categories,
            "filters": {
                "start_date": start_date or "",
                "end_date": end_date or "",
                "selected_categories": categories_filter or [],
                "min_amount": min_amount or "",
                "max_amount": max_amount or ""
            }
        })

    except Exception as e:
        print(f"View expense error: {e}")
        try:
            categories = db.fetch_categories()
            return templates.TemplateResponse("view_expense.html", {
                "request": request,
                "expenses": [],
                "categories": categories,
                "filters": {
                    "start_date": "",
                    "end_date": "",
                    "selected_categories": [],
                    "min_amount": "",
                    "max_amount": ""
                },
                "error_message": f"Error loading expenses: {str(e)}"
            })
        except:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Failed to load expenses page"
            })



@app.get("/edit_expense/{expense_id}", response_class=HTMLResponse)
async def edit_expense_form(request: Request, expense_id: int):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    try:
        user_id = db.get_user_id(user_email)

        # Get the expense to edit
        expense = db.get_expense_by_id(user_id, expense_id)
        if not expense:
            return RedirectResponse("/view-expense?error=Expense not found", status_code=303)

        # Get categories for dropdown
        categories = db.fetch_categories()

        return templates.TemplateResponse("edit_expense.html", {
            "request": request,
            "expense": expense,
            "categories": categories
        })

    except Exception as e:
        print(f"Error loading edit form: {e}")
        return RedirectResponse("/view-expense?error=Failed to load expense", status_code=303)


@app.post("/edit_expense/{expense_id}", response_class=HTMLResponse)
async def edit_expense_submit(
        request: Request,
        expense_id: int,
        amount: Optional[float] = Form(None),
        description: Optional[str] = Form(None),
        date: Optional[str] = Form(None),
        category: Optional[str] = Form(None)
):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    try:
        user_id = db.get_user_id(user_email)

        # Convert date string to date object if provided
        date_obj = None
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()

        # Call the edit method
        result = db.expenses_edit(
            user_id=user_id,
            expense_id=expense_id,
            date=date_obj,
            category=category,
            amount=amount,
            description=description
        )

        if result.get("success"):
            return RedirectResponse("/view-expense?success=Expense updated successfully", status_code=303)
        else:
            return RedirectResponse(f"/view-expense?error={result.get('message', 'Edit failed')}", status_code=303)

    except Exception as e:
        print(f"Edit expense error: {e}")
        return RedirectResponse("/view-expense?error=Edit failed", status_code=303)


@app.get("/analyze-expense", response_class=HTMLResponse)
async def analyze_expense(
        request: Request,
        forecast_mode: str = Query("months", description="Forecast mode: months or year"),
        forecast_value: int = Query(1, description="Number of months or year value"),
        selected_year: int = Query(datetime.now().year, description="Year for analysis")
):
    try:
        user_email = request.session.get("user_email")
        if not user_email:
            return RedirectResponse(url="/", status_code=302)

        user_id = db.get_user_id(user_email)

        category_expenses = db.fetch_catrgories_outcome(user_id,selected_year)

        forecast_data = ForeCast(user_email,forecast_mode,forecast_value).result
        try:
            float(forecast_data)
            is_numeric_forecast = True
        except (ValueError, TypeError):
            is_numeric_forecast = False

        available_year = db.get_available_years(user_id)
        stats = db.fetch_yearly_stats(user_id, selected_year)

        # print(forecast_data)
        # Pie chart data
        categories = db.fetch_catrgories_outcome_pie_plot(user_id,selected_year)
        df_pie = pd.DataFrame(categories, columns=['Category', 'Amount'])
        fig_pie = px.pie(df_pie, values='Amount', names='Category', title='Amount in Category')
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        pie_html = to_html(fig_pie, full_html=False)

        # Bar chart data
        months = db.fetch_catrgories_outcome_bar_plot(user_id,selected_year)
        df = pd.DataFrame(months, columns=['Amount', 'Month', 'Category'])
        df['Month'] = pd.to_datetime(df['Month'], format='%m').dt.month_name()
        fig_bar = px.bar(df, x='Month', y='Amount', color='Category', title='Monthly Spending by Category')
        bar_html = to_html(fig_bar, full_html=False)

        return templates.TemplateResponse("analyze_expense.html", {
            "request": request,
            "category_expenses": category_expenses,
            "forecast_mode": forecast_mode,
            "forecast_value":forecast_value,
            "selected_year":selected_year,
            "forecast":forecast_data,
            "plot_bar": bar_html,
            "plot_pie": pie_html,
            "is_numeric_forecast": is_numeric_forecast,
            "available_years":available_year,
            "yearly_stats": {
                "total": stats["total_amount"],
                "average": stats["average_amount"],
                "highest_month": calendar.month_name[stats["max_month"]] if stats["max_month"] else "N/A",
                "highest_amount": stats["max_amount"],
                "lowest_month": calendar.month_name[stats["min_month"]] if stats["min_month"] else "N/A",
                "lowest_amount": stats["min_amount"]
            }

        })

    except Exception as e:

        print(f"Error in analyze_expense: {e}")  # Add logging

        return templates.TemplateResponse("analyze_expense.html", {

            "request": request,
            "forecast": "Forecasting temporarily unavailable",
            "is_numeric_forecast": False,
            "forecast_mode": "months",
            "forecast_value": 1,
            "selected_year": datetime.now().year,
            "category_expenses": [],
            "available_years": [],
            "yearly_stats": {
                                "total": 0,
                                "average": 0,
                                "highest_month": "N/A",
                                "highest_amount": 0,
                                "lowest_month": "N/A",
                                "lowest_amount": 0
                            }
        })

@app.post("/delete_expense/{expense_id}", response_class=HTMLResponse)
def delete_expense(request: Request, expense_id: int):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    try:
        rows_affected = db.delete_expense(expense_id)
        if rows_affected > 0:
            return RedirectResponse("/view-expense", status_code=303)
        else:
            return HTMLResponse(content="<h2>Expense not found</h2>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h2>Error deleting expense: {e}</h2>", status_code=500)

@app.post("/delete_multiple_expenses", response_class=HTMLResponse)
def delete_multiple_expenses(request: Request, expense_ids: List[int] = Form(...)):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    try:
        user_id = db.get_user_id(user_email)
        rows_affected = db.delete_multiple_expenses(expense_ids, user_id)
        return RedirectResponse("/view-expense", status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"<h2>Error deleting expenses: {e}</h2>", status_code=500)

@app.get("/download_expenses_csv")
def download_expenses_csv(request: Request,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          category: Optional[List[str]] = Query(None),
                          min_amount: Optional[str] = None,
                          max_amount: Optional[str] = None):
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse("/", status_code=302)

    # Process filters same as view_expense
    if start_date == "":
        start_date = None
    if end_date == "":
        end_date = None

    categories_filter = None
    if category and len(category) > 0:
        categories_filter = [cat for cat in category if cat.strip()]
        if not categories_filter:
            categories_filter = None

    parsed_min_amount = None
    parsed_max_amount = None

    if min_amount and min_amount.strip():
        try:
            parsed_min_amount = float(min_amount)
        except ValueError:
            parsed_min_amount = None

    if max_amount and max_amount.strip():
        try:
            parsed_max_amount = float(max_amount)
        except ValueError:
            parsed_max_amount = None

    user_id = db.get_user_id(user_email)
    expenses = db.fetch_filtered_expenses(user_id, start_date, end_date, categories_filter, parsed_min_amount, parsed_max_amount)

    # Generate CSV content
    csv_content = db.generate_expenses_csv(expenses)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
