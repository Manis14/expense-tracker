import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.stats.diagnostic import acorr_ljungbox
from datetime import datetime
import warnings
from database import Database

warnings.filterwarnings('ignore')


class ForeCast:
    def __init__(self, userEmail, mode="months", value=1):
        self.user_email = userEmail
        self.db = Database()  # Assuming you have this module
        self.mode = mode
        self.value = value
        self.result = self.forecasting_expense(mode, value)

    def correct_format(self, df):
        """Enhanced data formatting with better validation"""
        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

        # Remove invalid data
        df = df.dropna()
        df = df[df['amount'] >= 0]  # Remove negative expenses

        if df.empty:
            return None

        df.set_index('date', inplace=True)
        return df.sort_index()

    def check_data_quality(self, df):
        """Check if data is suitable for forecasting"""

        # Check for too many zeros
        zero_ratio = (df['amount'] == 0).sum() / len(df)
        if zero_ratio > 0.7:
            return False, "Too many zero values in data"

        # Check variance
        if df['amount'].var() == 0:
            return False, "No variance in expense data"

        return True, "Data quality is good"

    def prepare_monthly_data(self, df):
        """Prepare monthly aggregated data with better handling"""
        # Resample to monthly and handle missing months
        df_monthly = df.resample('M').agg({
            'amount': 'sum'
        }).fillna(0)

        # Remove leading zeros
        first_nonzero = df_monthly[df_monthly['amount'] > 0].index
        if len(first_nonzero) > 0:
            df_monthly = df_monthly.loc[first_nonzero[0]:]

        return df_monthly

    def check_stationarity(self, series, alpha=0.05):
        """Enhanced stationarity check"""
        try:
            result = adfuller(series.dropna())
            return {
                'is_stationary': result[1] < alpha,
                'p_value': result[1],
                'critical_values': result[4]
            }
        except Exception:
            return {'is_stationary': False, 'p_value': 1.0}

    def find_best_arima_order(self, series, max_p=3, max_d=2, max_q=3):
        """Find optimal ARIMA parameters using AIC"""
        best_aic = float('inf')
        best_order = (1, 1, 1)

        for p in range(max_p + 1):
            for d in range(max_d + 1):
                for q in range(max_q + 1):
                    try:
                        model = ARIMA(series, order=(p, d, q))
                        fitted = model.fit()
                        aic = fitted.aic

                        if aic < best_aic:
                            best_aic = aic
                            best_order = (p, d, q)
                    except:
                        continue

        return best_order, best_aic

    def fit_arima_model(self, series):
        """Fit ARIMA model with automatic parameter selection"""
        try:
            # First try to find best parameters
            best_order, best_aic = self.find_best_arima_order(series)

            # Fit the model
            model = ARIMA(series, order=best_order)
            fitted_model = model.fit()

            # Validate model
            residuals = fitted_model.resid
            ljung_box = acorr_ljungbox(residuals, lags=min(10, len(residuals) // 4))

            return {
                'model': fitted_model,
                'order': best_order,
                'aic': best_aic,
                'residuals_test': ljung_box
            }

        except Exception as e:
            print(f"ARIMA fitting error: {e}")
            # Fallback to simple exponential smoothing approach
            return self.simple_forecast_fallback(series)

    def simple_forecast_fallback(self, series):
        """Simple exponential smoothing fallback"""
        try:
            # Use exponential weighted mean for trend
            alpha = 0.3
            trend = series.ewm(alpha=alpha).mean().iloc[-1]
            seasonal_factor = 1.0

            # Check for seasonal pattern in recent months
            if len(series) >= 12:
                seasonal_factor = series.iloc[-12:].mean() / series.mean()

            return {
                'model': None,
                'trend': trend,
                'seasonal_factor': seasonal_factor,
                'is_fallback': True
            }
        except:
            return {
                'model': None,
                'trend': series.mean(),
                'seasonal_factor': 1.0,
                'is_fallback': True
            }

    def generate_forecast(self, model_info, steps, last_value=None):
        """Generate forecast with improved handling"""
        try:
            if model_info.get('is_fallback', False):
                # Simple trend-based forecast
                trend = model_info['trend']
                seasonal = model_info['seasonal_factor']

                # Generate forecast with slight trend and seasonal adjustment
                forecast = []
                for i in range(steps):
                    # Add small random variation and trend
                    variation = np.random.normal(0, trend * 0.1)
                    predicted_value = max(0, trend * seasonal + variation)
                    forecast.append(predicted_value)

                return pd.Series(forecast)

            else:
                # Use ARIMA model
                model = model_info['model']
                forecast = model.forecast(steps=steps)

                # Ensure non-negative values
                forecast = forecast.clip(lower=0)

                return forecast

        except Exception as e:
            print(f"Forecast generation error: {e}")
            # Return conservative estimate based on recent average
            if last_value is not None:
                return pd.Series([max(0, last_value)] * steps)
            else:
                return pd.Series([0] * steps)

    def validate_forecast_inputs(self, mode, value, past_months):
        """Validate inputs and data requirements"""
        if mode.lower() == "year":
            if past_months < 6:
                return False, "Need at least 6 months of data to predict yearly expenses"
            if value < datetime.now().year:
                return False, "Cannot forecast for past years"

        elif mode.lower() == "months":
            if value <= 0:
                return False, "Number of months must be positive"
            if value > 12:
                return False, "Cannot forecast more than 12 months ahead"
            if value > 6 and past_months < 12:
                return False, "Need at least 12 months of data to forecast more than 6 months"
            if value <= 3 and past_months < 6:
                return False, "Need at least 6 months of data for reliable short-term forecasting"
        else:
            return False, "Invalid mode. Use 'months' or 'year'"

        return True, "Validation passed"

    def forecasting_expense(self, mode="months", value=1):
        """Main forecasting method with improved error handling"""
        try:
            # Get user data
            user_id = self.db.get_user_id(self.user_email)
            if not user_id:
                return "User not found"

            # Fetch and validate data
            data = self.db.fetch_data_forecast(user_id)
            if not data:
                return "No expense data available for forecasting"

            # Process data
            df = pd.DataFrame(data, columns=["date", "amount"])
            df = self.correct_format(df)

            # Check data quality
            is_good, quality_msg = self.check_data_quality(df)
            if not is_good:
                return f"Data quality issue: {quality_msg}"

            # Prepare monthly data
            df_monthly = self.prepare_monthly_data(df)
            past_months = len(df_monthly)

            # Validate inputs
            is_valid, validation_msg = self.validate_forecast_inputs(mode, value, past_months)
            if not is_valid:
                return validation_msg

            # Check if we have recent data
            last_date = df_monthly.index[-1]
            days_since_last = (datetime.now() - last_date).days
            if days_since_last > 60:
                return "Data is too outdated for reliable forecasting"

            # Prepare series for modeling
            series = df_monthly['amount']
            last_value = series.iloc[-1]

            # Remove extreme outliers (beyond 3 standard deviations)
            std_threshold = 3
            mean_val = series.mean()
            std_val = series.std()
            series_clean = series[np.abs(series - mean_val) <= std_threshold * std_val]

            if len(series_clean) < len(series) * 0.7:
                # Too many outliers, use original data
                series_clean = series

            # Fit model
            model_info = self.fit_arima_model(series_clean)

            # Calculate forecast period
            today = pd.Timestamp(datetime.today().date())

            if mode.lower() == "months":
                future_months = value
                forecast_values = self.generate_forecast(model_info, future_months, last_value)
                total_estimate = forecast_values.sum()

            elif mode.lower() == "year":
                current_year = datetime.now().year
                target_year = value

                if target_year <= current_year:
                    # For current year, forecast remaining months
                    remaining_months = 12 - datetime.now().month + 1
                    forecast_values = self.generate_forecast(model_info, remaining_months, last_value)
                    # Add YTD expenses
                    ytd_expenses = df[df.index.year == current_year]['amount'].sum()
                    total_estimate = ytd_expenses + forecast_values.sum()
                else:
                    # For future year, forecast 12 months
                    forecast_values = self.generate_forecast(model_info, 12, last_value)
                    total_estimate = forecast_values.sum()

            # Ensure reasonable bounds
            historical_mean = series.mean()
            historical_max = series.max()

            # Cap the forecast at 3x historical maximum or 2x annual historical mean
            reasonable_cap = min(historical_max * 3, historical_mean * 24)
            total_estimate = min(total_estimate, reasonable_cap)

            # Ensure minimum reasonable value
            total_estimate = max(total_estimate, historical_mean * 0.1)

            print(f"Forecast info: Model order: {model_info.get('order', 'N/A')}, "
                  f"Historical mean: {historical_mean:.2f}, "
                  f"Forecast: {total_estimate:.2f}")

            return f"{total_estimate:.2f}"

        except Exception as e:
            print(f"Forecasting error: {e}")
            return "Forecasting temporarily unavailable"

    def get_forecast_confidence(self, model_info, steps):
        """Get confidence intervals for forecast"""
        try:
            if not model_info.get('is_fallback', False) and model_info['model']:
                forecast_result = model_info['model'].get_forecast(steps=steps)
                conf_int = forecast_result.conf_int()
                return {
                    'lower_bound': conf_int.iloc[:, 0].sum(),
                    'upper_bound': conf_int.iloc[:, 1].sum()
                }
        except:
            pass
        return None

    def plot_forecast(self, historical_data, forecast_data, confidence_intervals=None):
        """Plot historical data and forecast"""
        plt.figure(figsize=(12, 6))

        # Plot historical data
        plt.plot(historical_data.index, historical_data.values,
                 label='Historical Data', color='blue', linewidth=2)

        # Plot forecast
        forecast_index = pd.date_range(start=historical_data.index[-1],
                                       periods=len(forecast_data) + 1, freq='M')[1:]
        plt.plot(forecast_index, forecast_data,
                 label='Forecast', color='red', linestyle='--', linewidth=2)

        # Plot confidence intervals if available
        if confidence_intervals:
            plt.fill_between(forecast_index,
                             confidence_intervals['lower_bound'],
                             confidence_intervals['upper_bound'],
                             alpha=0.3, color='red', label='Confidence Interval')

        plt.title('Expense Forecast')
        plt.xlabel('Date')
        plt.ylabel('Amount')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

