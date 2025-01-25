from flask import Flask, render_template, request, send_from_directory
import requests
from datetime import datetime, timedelta
import pycountry

app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')
# Function to convert country name to ISO country code
def get_country_code(country_name):
    try:
        country = pycountry.countries.get(name=country_name)
        return country.alpha_2  # ISO 3166-1 alpha-2 country code
    except AttributeError:
        return None

# Function to fetch government holidays from Nager.Date API
def fetch_government_holidays_nager(start_date, end_date, country_code):
    api_url = f"https://date.nager.at/api/v3/PublicHolidays/{start_date.year}/{country_code}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        holidays = response.json()
        holidays_in_range = [
            datetime.strptime(holiday["date"], "%Y-%m-%d")
            for holiday in holidays
            if start_date <= datetime.strptime(holiday["date"], "%Y-%m-%d") <= end_date
        ]
        return holidays_in_range
    except (requests.exceptions.RequestException, ValueError):
        return None

# Function to fetch government holidays from Calendarific API
def fetch_government_holidays_calendarific(start_date, end_date, country_code):
    api_key = "Your_API_KEY"  # Replace with your API key
    api_url = f"https://calendarific.com/api/v2/holidays"
    params = {
        "api_key": api_key,
        "country": country_code.lower(),
        "year": start_date.year
    }
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        holidays = response.json()["response"]["holidays"]
        holidays_in_range = [
            datetime.strptime(holiday["date"]["iso"].split("T")[0], "%Y-%m-%d")
            for holiday in holidays
            if start_date <= datetime.strptime(holiday["date"]["iso"].split("T")[0], "%Y-%m-%d") <= end_date
        ]
        return holidays_in_range
    except (requests.exceptions.RequestException, ValueError):
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get input from the form
        semester_start_date = datetime.strptime(request.form["semester_start_date"], "%Y-%m-%d")
        semester_end_date = datetime.strptime(request.form["semester_end_date"], "%Y-%m-%d")
        today_date = datetime.strptime(request.form["today_date"], "%Y-%m-%d")
        past_working_days_off = int(request.form["past_working_days_off"])
        country_name = request.form["country_name"].strip()

        # Get country code from the country name
        country_code = get_country_code(country_name)
        if not country_code:
            return render_template("index.html", error="Invalid country name.")

        # Fetch holidays
        holidays_in_semester = fetch_government_holidays_nager(semester_start_date, semester_end_date, country_code)
        if holidays_in_semester is None:
            holidays_in_semester = fetch_government_holidays_calendarific(semester_start_date, semester_end_date, country_code)
        if holidays_in_semester is None:
            return render_template("index.html", error="Unable to fetch holidays.")

        # Calculate holidays and off days
        remaining_govt_holidays = [holiday for holiday in holidays_in_semester if holiday > today_date]
        total_days_in_semester = (semester_end_date - semester_start_date).days + 1
        days_passed = (today_date - semester_start_date).days + 1
        days_remaining = (semester_end_date - today_date).days
        total_weekends = sum(1 for i in range(total_days_in_semester)
                             if (semester_start_date + timedelta(days=i)).weekday() in (5, 6))
        remaining_weekends = sum(1 for i in range(days_remaining + 1)
                                 if (today_date + timedelta(days=i)).weekday() in (5, 6))
        total_working_days = total_days_in_semester - total_weekends - len(holidays_in_semester)
        remaining_working_days = days_remaining - remaining_weekends - len(remaining_govt_holidays)
        minimum_attendance_days = int(0.75 * total_working_days)
        days_attended = days_passed - past_working_days_off - (
            sum(1 for i in range(days_passed) if (semester_start_date + timedelta(days=i)).weekday() in (5, 6))
            + sum(1 for holiday in holidays_in_semester if holiday < today_date)
        )
        total_days_off_allowed = max(0, remaining_working_days - (minimum_attendance_days - days_attended))
        weeks_remaining = days_remaining // 7 + (1 if days_remaining % 7 else 0)
        weekly_off_days = total_days_off_allowed // weeks_remaining if weeks_remaining > 0 else 0

        # Render results
        return render_template("index.html", total_days_off=total_days_off_allowed, 
                               weekly_off_days=weekly_off_days, 
                               govt_holidays=remaining_govt_holidays)
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
