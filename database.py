# Fixed database.py
import psycopg2
from typing import Optional, List, Dict
from datetime import datetime,date
import csv
import io
import bcrypt
from urllib.parse import urlparse
import  os
import warnings

warnings.filterwarnings('ignore')


class Database:  # Capitalized class name

    def __init__(self):
        result = urlparse(os.environ.get("DATABASE_URL"))
        # self.hostname = 'localhost'
        # self.database = 'expense_tracker'
        # self.username = 'postgres'
        # self.port_id = 5432
        # self.pwd = "123Qwer@"

        try:
            self.conn = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
            self.cur = self.conn.cursor()
        except Exception as e:
            print(f"Database connection error: {e}")
            raise

    def __del__(self):
        """Properly close database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def email_verification(self, email):
        self.cur.execute("SELECT count(*) FROM users WHERE email = %s", (email,))
        result = self.cur.fetchone()[0]
        return result

    def get_user_name(self, email):
        self.cur.execute("select username from users where email = %s", (email,))
        result = self.cur.fetchone()
        return result[0] if result else None

    def add_user_database(self, user, email, password):
        self.cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (user, email, password)
        )
        self.conn.commit()

    def login(self, email, password):
        try:
            # Get the hashed password from database
            self.cur.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
            result = self.cur.fetchone()

            if result:
                stored_hash = result[0]
                # Verify the password using bcrypt
                return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
            else:
                return False

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def fetch_categories(self):
        self.cur.execute("SELECT name FROM categories")
        return self.cur.fetchall()

    def get_user_id(self, email):
        self.cur.execute("select id from users where email = %s", (email,))
        result = self.cur.fetchone()
        return result[0] if result else None

    def insert_expense(self, amount, description, date, category_name, user_id):
        self.cur.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
        category_id = self.cur.fetchone()

        if category_id:
            self.cur.execute(
                """
                INSERT INTO expenses (amount, description, date, category_id, user_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (amount, description, date, category_id[0], user_id)
            )
            self.conn.commit()

    def fetch_filtered_expenses(self,
                                user_id: int,
                                start_date: Optional[str] = None,
                                end_date: Optional[str] = None,
                                categories: Optional[List[str]] = None,
                                min_amount: Optional[float] = None,
                                max_amount: Optional[float] = None
                                ) -> List[Dict]:

        query = """
            SELECT e.id, e.amount, e.description, e.date, c.name as category
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = %s
        """
        params = [user_id]

        if start_date:
            query += " AND e.date >= %s"
            params.append(start_date)

        if end_date:
            query += " AND e.date <= %s"
            params.append(end_date)

        if categories and len(categories) > 0:
            placeholders = ','.join(['%s'] * len(categories))
            query += f" AND c.name IN ({placeholders})"
            params.extend(categories)

        if min_amount is not None:
            query += " AND e.amount >= %s"
            params.append(min_amount)

        if max_amount is not None:
            query += " AND e.amount <= %s"
            params.append(max_amount)

        query += " ORDER BY e.date DESC"

        self.cur.execute(query, tuple(params))
        results = self.cur.fetchall()
        expenses = []
        for row in results:
            expense = {
                "id": row[0],
                "amount": row[1],
                "description": row[2],
                "date": row[3].strftime('%Y-%m-%d'),
                "category": row[4]
            }
            expenses.append(expense)

        return expenses

    def fetch_yearly_stats(self, user_id, year=None):
        if year is None:
            year = datetime.now().year

        # Total and Average
        amt_query = """
            SELECT SUM(amount), AVG(amount) 
            FROM expenses 
            WHERE user_id = %s AND EXTRACT(YEAR FROM date) = %s;
        """
        self.cur.execute(amt_query, (user_id, year))
        total_amount, avg_amount = self.cur.fetchone()

        # Monthly totals for finding max and min
        monthly_query = """
            SELECT EXTRACT(MONTH FROM date) AS month, SUM(amount) AS total 
            FROM expenses 
            WHERE user_id = %s AND EXTRACT(YEAR FROM date) = %s 
            GROUP BY month 
            ORDER BY total DESC;
        """
        self.cur.execute(monthly_query, (user_id, year))
        monthly_data = self.cur.fetchall()

        # Get month with max and min spending
        if monthly_data:
            max_month, max_amount = monthly_data[0][0], monthly_data[0][1]
            min_month, min_amount = monthly_data[-1][0], monthly_data[-1][1]
        else:
            max_month = max_amount = min_month = min_amount = None

        return {
            "total_amount": total_amount,
            "average_amount": avg_amount,
            "max_month": int(max_month) if max_month else None,
            "max_amount": max_amount,
            "min_month": int(min_month) if min_month else None,
            "min_amount": min_amount
        }

    def delete_expense(self, expense_id):
        """Delete an expense by its ID"""
        self.cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
        self.conn.commit()
        return self.cur.rowcount

    def delete_multiple_expenses(self, expense_ids: List[int], user_id: int):
        """Delete multiple expenses by their IDs with user verification"""
        if not expense_ids:
            return 0

        placeholders = ','.join(['%s'] * len(expense_ids))
        query = f"DELETE FROM expenses WHERE id IN ({placeholders}) AND user_id = %s"
        params = expense_ids + [user_id]

        self.cur.execute(query, params)
        self.conn.commit()
        return self.cur.rowcount

    def generate_expenses_csv(self, expenses: List[Dict]) -> str:
        """Generate CSV content from expenses data"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Date', 'Category', 'Amount', 'Description'])

        # Write data rows
        for expense in expenses:
            writer.writerow([
                expense['date'],
                expense['category'],
                expense['amount'],
                expense['description'] or ''
            ])

        csv_content = output.getvalue()
        output.close()
        return csv_content


    def fetch_data_forecast(self, user_id):
        self.cur.execute("SELECT date, amount FROM expenses WHERE user_id = %s", (user_id,))
        result = self.cur.fetchall()
        return result

    def fetch_catrgories_outcome(self, user_id, year=None):  # Fixed typo
        if year is None:
            year = datetime.now().year

        query = """
        SELECT c.name, SUM(e.amount) AS Amount, COUNT(e.amount), AVG(e.amount)
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
        WHERE e.user_id = %s and extract(year from date) = %s
        GROUP BY c.name
        ORDER BY Amount DESC;
        """
        self.cur.execute(query, (user_id,year,))
        results = self.cur.fetchall()

        cat_expenses = []
        for row in results:
            cat_expense = {
                "category": row[0],  # c.name
                "amount": float(row[1]),  # SUM (convert to float)
                "Transaction": row[2],  # COUNT
                "Avg": float(row[3])  # AVG (convert to float)
            }
            cat_expenses.append(cat_expense)
        return cat_expenses

    # def fetch_monthly_analysis(self, user_id, year=None):
    #     if year is None:
    #         year = datetime.now().year
    #
    #     query = """
    #         SELECT SUM(amount) AS total_amount, EXTRACT(MONTH FROM date) AS month
    #         FROM expenses
    #         WHERE EXTRACT(YEAR FROM date) = %s AND user_id = %s
    #         GROUP BY month
    #         ORDER BY month;
    #     """
    #     self.cur.execute(query, (year, user_id,))
    #     result = self.cur.fetchall()
    #
    #     if not result:
    #         return f"No expense data found for year {year}."
    #
    #     return result

    def get_dashboard_stats(self, user_id):
        """Get dashboard statistics for a user"""
        try:
            # Get total expenses
            self.cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = %s", (user_id,))
            total_expenses = float(self.cur.fetchone()[0])

            # Get current month expenses
            from datetime import datetime
            current_month = datetime.now().month
            current_year = datetime.now().year

            self.cur.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM expenses 
                WHERE user_id = %s 
                AND EXTRACT(MONTH FROM date) = %s 
                AND EXTRACT(YEAR FROM date) = %s
            """, (user_id, current_month, current_year))
            this_month = float(self.cur.fetchone()[0])

            # Get number of unique categories used
            self.cur.execute("""
                SELECT COUNT(DISTINCT category_id) 
                FROM expenses 
                WHERE user_id = %s
            """, (user_id,))
            categories_used = int(self.cur.fetchone()[0])

            # Get average daily expense (last 30 days)
            self.cur.execute("""
                SELECT COALESCE(AVG(daily_total), 0) FROM (
                    SELECT SUM(amount) as daily_total
                    FROM expenses 
                    WHERE user_id = %s 
                    AND date >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY date
                ) as daily_expenses
            """, (user_id,))
            avg_daily_result = self.cur.fetchone()
            average_daily = float(avg_daily_result[0]) if avg_daily_result[0] is not None else 0.0

            return {
                'total_expenses': total_expenses,
                'this_month': this_month,
                'categories_used': categories_used,
                'average_daily': average_daily
            }

        except Exception as e:
            print(f"Error getting dashboard stats: {e}")
            return {
                'total_expenses': 0.0,
                'this_month': 0.0,
                'categories_used': 0,
                'average_daily': 0.0
            }

    def get_available_years(self, user_id):
        """Get all years that have expense data for the user"""
        try:
            query = """
            SELECT DISTINCT EXTRACT(YEAR FROM date) AS year
            FROM expenses
            WHERE user_id = %s
            ORDER BY year DESC;
            """
            self.cur.execute(query, (user_id,))
            results = self.cur.fetchall()
            return [int(row[0]) for row in results] if results else [datetime.now().year]
        except Exception as e:
            print(f"Error getting available years: {e}")
            return [datetime.now().year]

    def get_today_stats(self, user_id):
        """Get today's expense statistics for a user"""
        try:
            today = date.today()

            # Get today's total expenses count
            self.cur.execute("""
                SELECT COUNT(*) 
                FROM expenses 
                WHERE user_id = %s AND date = %s
            """, (user_id, today))
            today_count = int(self.cur.fetchone()[0])

            # Get today's total amount
            self.cur.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM expenses 
                WHERE user_id = %s AND date = %s
            """, (user_id, today))
            today_amount = float(self.cur.fetchone()[0])

            return {
                'count': today_count,
                'amount': today_amount
            }
        except Exception as e:
            print(f"Error getting today's stats: {e}")
            return {
                'count': 0,
                'amount': 0.0
            }

    def expenses_edit(self, user_id, expense_id, date=None, category=None, amount=None, description=None):
        """Edit expense fields for a specific user and expense"""
        updated_list = []

        try:
            # First, verify the expense exists and belongs to the user
            self.cur.execute("SELECT id FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
            if not self.cur.fetchone():
                return {
                    "success": False,
                    "message": "Expense not found or you don't have permission to edit it"
                }

            if date is not None:
                query = """UPDATE expenses SET date = %s WHERE user_id = %s AND id = %s"""
                self.cur.execute(query, (date, user_id, expense_id))
                if self.cur.rowcount > 0:
                    updated_list.append("Date")

            if category is not None:
                # Get category ID from category name
                self.cur.execute("""SELECT id FROM categories WHERE name = %s""", (category,))
                category_result = self.cur.fetchone()
                if category_result:
                    category_id = category_result[0]
                    query = """UPDATE expenses SET category_id = %s WHERE user_id = %s AND id = %s"""
                    self.cur.execute(query, (category_id, user_id, expense_id))
                    if self.cur.rowcount > 0:
                        updated_list.append("Category")
                else:
                    self.conn.rollback()  # Rollback on error
                    return {
                        "success": False,
                        "message": f"Category '{category}' not found"
                    }

            if amount is not None:
                if amount <= 0:  # Add validation
                    self.conn.rollback()
                    return {
                        "success": False,
                        "message": "Amount must be greater than 0"
                    }
                query = """UPDATE expenses SET amount = %s WHERE user_id = %s AND id = %s"""
                self.cur.execute(query, (amount, user_id, expense_id))
                if self.cur.rowcount > 0:
                    updated_list.append("Amount")

            if description is not None:
                query = """UPDATE expenses SET description = %s WHERE user_id = %s AND id = %s"""
                self.cur.execute(query, (description, user_id, expense_id))
                if self.cur.rowcount > 0:
                    updated_list.append("Description")

            # Commit all changes
            self.conn.commit()

            if len(updated_list) > 0:
                return {
                    "success": True,
                    "updated_fields": updated_list,
                    "message": f"Successfully updated: {', '.join(updated_list)}"
                }
            else:
                return {
                    "success": False,
                    "message": "No changes were made"
                }

        except Exception as e:
            # Rollback in case of error
            self.conn.rollback()
            print(f"Database error in expenses_edit: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to update expense due to database error"
            }

    def get_expense_by_id(self, user_id, expense_id):
        """Get a specific expense for editing"""
        try:
            query = """
            SELECT e.id, e.amount, e.description, e.date, c.name as category
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = %s AND e.id = %s
            """
            self.cur.execute(query, (user_id, expense_id))
            result = self.cur.fetchone()

            if result:
                return {
                    "id": result[0],
                    "amount": result[1],
                    "description": result[2],
                    "date": result[3],
                    "category": result[4]
                }
            else:
                return None

        except Exception as e:
            print(f"Error fetching expense: {e}")
            return None

    def fetch_catrgories_outcome_pie_plot(self, user_id, year=None):

        if year == None:
            year = datetime.now().year
        query = """ 
            select c.name, sum(e.amount) from expenses e join categories c on  c.id = e.category_id 
            where e.user_id = %s and Extract(year from date)=%s group by c.name;                 
            """

        self.cur.execute(query, (user_id, year,))
        result = self.cur.fetchall()
        return result

    def fetch_catrgories_outcome_bar_plot(self, user_id, year=None):
        if year == None:
            year = datetime.now().year
        query = """ 
           select sum(e.amount),extract(month from e.date) as Month, c.name from expenses as e 
           join categories c on c.id = e.category_id
           where user_id = %s and Extract(year from date) = %s group by Month,c.name
            """

        self.cur.execute(query, (user_id, year,))
        result = self.cur.fetchall()
        return result

    def initialize_schema(self):
        """Create tables and insert default categories if not already inserted"""
        try:
            self.cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );
    
                CREATE TABLE IF NOT EXISTS categories(
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                );
    
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    amount FLOAT NOT NULL,
                    description TEXT,
                    date DATE DEFAULT CURRENT_DATE,
                    category_id INTEGER REFERENCES categories(id),
                    user_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()

            # Insert default categories if not already present
            default_categories = [
                "Groceries", "Rent", "Utilities", "Transportation", "Mobile Recharge", "Fuel", "Medical",
                "Restaurants", "Cafes", "Snacks", "Delivery", "Shopping", "Online Shopping", "Electronics",
                "Fashion & Accessories", "Personal Care Products", "Home Appliances", "Books & Media",
                "Movies", "Games", "Streaming Services", "Music", "Gym Membership", "Salon & Grooming",
                "Childcare", "Food", "Pet Care", "Tuition", "Stationery", "Online Courses",
                "Software Subscriptions", "Flight Tickets", "Hotel Bookings", "Tour Packages", "Local Transport",
                "Loan Repayment", "Insurance", "Investments", "Savings", "Donations", "Gifts", "Miscellaneous",
                "Emergency", "Others"
            ]

            for category in default_categories:
                self.cur.execute(
                    "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (category,)
                )

            self.conn.commit()
            print("✅ Tables created and default categories inserted.")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error initializing schema: {e}")
