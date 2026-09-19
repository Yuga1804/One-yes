import os
import smtplib
import socket
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

# ---------------------------------------------------------------------------
# Credentials and settings (loaded from environment/secrets with fallbacks)
# ---------------------------------------------------------------------------
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "thahrinah05@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "cwjp dkou chbq vlqj")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "yugadharshini18@gmail.com")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "my_openweather_api_key")  # Put your OpenWeather API key here if you have one
ZAPIER_WEBHOOK_URL = os.environ.get("ZAPIER_WEBHOOK_URL", "my_existing_zapier_webhook_url")  # Put your Zapier Catch Hook URL here if you have one

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Bangalore, India coordinates
BANGALORE_LAT = 12.9716
BANGALORE_LON = 77.5946

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# WMO Weather interpretation codes for Open-Meteo
WMO_CODES = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    61: "Slight Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    71: "Slight Snow",
    73: "Moderate Snow",
    75: "Heavy Snow",
    80: "Slight Rain Showers",
    81: "Moderate Rain Showers",
    82: "Violent Rain Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Slight Hail",
    99: "Thunderstorm with Heavy Hail",
}


def get_weather_open_meteo():
    """Fetch current weather for Bangalore via free Open-Meteo API (requires NO API key)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": BANGALORE_LAT,
        "longitude": BANGALORE_LON,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "hourly": "precipitation_probability",
        "wind_speed_unit": "ms",
        "forecast_days": 1,
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        hourly = data.get("hourly", {})

        weather_code = current.get("weather_code", 0)
        condition = WMO_CODES.get(weather_code, "Partly Cloudy")

        # Chance of rain from current hour
        probs = hourly.get("precipitation_probability", [])
        rain_prob = probs[0] if probs else None

        weather = {
            "city": "Bangalore",
            "country": "IN",
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "condition": condition,
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_ms": current.get("wind_speed_10m"),
            "chance_of_rain_percent": rain_prob,
        }
        print("[SUCCESS] Weather data fetched from Open-Meteo (free API, no key needed).")
        return weather
    except Exception as e:
        print(f"[ERROR] Could not reach Open-Meteo API: {e}")
        return None


def get_weather_openweather():
    """Fetch current weather for Bangalore using OpenWeatherMap API."""
    params = {
        "lat": BANGALORE_LAT,
        "lon": BANGALORE_LON,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(CURRENT_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        weather = {
            "city": "Bangalore",
            "country": "IN",
            "temperature_c": data["main"]["temp"],
            "feels_like_c": data["main"]["feels_like"],
            "condition": data["weather"][0]["description"].title(),
            "humidity_percent": data["main"]["humidity"],
            "wind_speed_ms": data["wind"]["speed"],
            "chance_of_rain_percent": None,
        }
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Weather API returned an HTTP error: {e}")
        if e.response is not None and e.response.status_code == 401:
            print("        Check that OPENWEATHER_API_KEY is valid and activated.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not reach the Weather API: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        print(f"[ERROR] Unexpected Weather API response format: {e}")
        return None

    try:
        forecast_params = dict(params, cnt=1)
        forecast_response = requests.get(FORECAST_URL, params=forecast_params, timeout=15)
        forecast_response.raise_for_status()
        pop = forecast_response.json()["list"][0].get("pop")
        if pop is not None:
            weather["chance_of_rain_percent"] = round(pop * 100)
    except (requests.exceptions.RequestException, KeyError, IndexError, ValueError) as e:
        print(f"[WARNING] Chance of rain not available: {e}")

    print("[SUCCESS] Weather data fetched from OpenWeatherMap.")
    return weather


def get_weather():
    """Fetch weather: uses OpenWeatherMap if a real key is provided; otherwise falls back to free Open-Meteo."""
    if OPENWEATHER_API_KEY and OPENWEATHER_API_KEY != "my_openweather_api_key":
        weather = get_weather_openweather()
        if weather:
            return weather
        print("[INFO] Falling back to free Open-Meteo weather API...")

    return get_weather_open_meteo()


def send_to_zapier(weather):
    """POST the weather data as JSON to the Zapier Catch Hook. Returns True/False/None."""
    if not ZAPIER_WEBHOOK_URL or ZAPIER_WEBHOOK_URL == "my_existing_zapier_webhook_url" or not ZAPIER_WEBHOOK_URL.startswith("http"):
        print("[INFO] Zapier webhook URL is not configured (placeholder detected). Skipping Zapier.")
        return None

    try:
        response = requests.post(ZAPIER_WEBHOOK_URL, json=weather, timeout=15)
        response.raise_for_status()
        print(f"[SUCCESS] Weather data sent to Zapier webhook (status {response.status_code}).")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Zapier webhook returned an HTTP error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Zapier webhook request failed: {e}")
    return False


def build_email_body(weather):
    rain = weather["chance_of_rain_percent"]
    rain_text = f"{rain}%" if rain is not None else "N/A"

    return (
        "Current Bangalore Weather\n"
        "\n"
        f"Temperature: {weather['temperature_c']} °C\n"
        f"Feels Like: {weather['feels_like_c']} °C\n"
        f"Weather Condition: {weather['condition']}\n"
        f"Humidity: {weather['humidity_percent']}%\n"
        f"Wind Speed: {weather['wind_speed_ms']} m/s\n"
        f"Chance of Rain: {rain_text}\n"
    )


def send_email(weather):
    """Send the weather email directly through Gmail SMTP. Returns True/False."""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = "Current Bangalore Weather"
    msg.attach(MIMEText(build_email_body(weather), "plain", "utf-8"))

    server = None

    # Step 1: connect, start TLS, and log in
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(GMAIL_ADDRESS.strip(), GMAIL_APP_PASSWORD.strip())
        print("[SUCCESS] Connected to Gmail SMTP and logged in.")
    except smtplib.SMTPAuthenticationError:
        print("[ERROR] SMTP login failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
              "(use a 16-character Gmail App Password, not your normal password).")
        return False
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
            socket.gaierror, socket.timeout, TimeoutError, ConnectionError) as e:
        print(f"[ERROR] Could not connect to the SMTP server: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error during connection/login: {e}")
        return False
    except OSError as e:
        print(f"[ERROR] Network error while connecting to SMTP: {e}")
        return False

    # Step 2: send the email
    try:
        server.send_message(msg)
        print(f"[SUCCESS] Email sent to {RECIPIENT_EMAIL}.")
        return True
    except smtplib.SMTPException as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False
    except OSError as e:
        print(f"[ERROR] Network error while sending email: {e}")
        return False
    finally:
        try:
            server.quit()
        except Exception:
            pass


def main():
    print("Fetching current weather for Bangalore...")
    weather = get_weather()
    if weather is None:
        print("[FAILED] Stopping because weather data could not be retrieved.")
        sys.exit(1)

    print("Sending weather data to Zapier...")
    zapier_ok = send_to_zapier(weather)

    print("Sending email via Gmail SMTP...")
    email_ok = send_email(weather)

    print("\n----- Summary -----")
    print(f"Weather fetch : SUCCESS")
    if zapier_ok is None:
        print("Zapier webhook: SKIPPED (URL not configured)")
    else:
        print(f"Zapier webhook: {'SUCCESS' if zapier_ok else 'FAILED'}")
    print(f"Email         : {'SUCCESS' if email_ok else 'FAILED'}")

    if not email_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()