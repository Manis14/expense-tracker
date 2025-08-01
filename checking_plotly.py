from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import plotly.express as px
from plotly.io import to_html
from database import Database
from datetime import datetime

app = FastAPI()
db = Database()
templates = Jinja2Templates(directory="templates")  # Ensure this folder exists

@app.get("/")
def root():
    return {"message": "Welcome to the Titanic API"}

@app.get("/plot", response_class=HTMLResponse)
def plot(request: Request):
    # Pie chart data
    categories = db.fetch_catrgories_outcome_pie_plot(1)
    df_pie = pd.DataFrame(categories, columns=['Category', 'Amount'])
    fig_pie = px.pie(df_pie, values='Amount', names='Category', title='Amount in Category')
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    pie_html = to_html(fig_pie, full_html=False)

    # Bar chart data
    months = db.fetch_catrgories_outcome_bar_plot(1)
    df = pd.DataFrame(months, columns=['Amount', 'Month', 'Category'])
    df['Month'] = pd.to_datetime(df['Month'], format='%m').dt.month_name()
    fig_bar = px.bar(df, x='Month', y='Amount', color='Category', title='Monthly Spending by Category')
    bar_html = to_html(fig_bar, full_html=False)

    return templates.TemplateResponse("checking_plot.html", {
        "request": request,
        "plot_bar": bar_html,
        "plot_pie": pie_html
    })
