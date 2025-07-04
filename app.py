import os
import requests
import pandas as pd
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
# SECURELY get API keys from environment variables.
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Check if keys were loaded correctly
if not all([AMADEUS_API_KEY, AMADEUS_API_SECRET, OPENAI_API_KEY]):
    raise ValueError("API keys not found! Please create a .env file and add your keys.")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Amadeus API Helper Functions ---
def get_amadeus_access_token():
    """Fetches a new access token from Amadeus API."""
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET,
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Amadeus token: {e}")
        return None

def search_flight_offers(token, destination_code):
    """Searches for flight offers to a specific destination."""
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    headers = {"Authorization": f"Bearer {token}"}
    
    start_date = (pd.Timestamp.now() + pd.DateOffset(days=1)).strftime('%Y-%m-%d')
    
    params = {
        # SOLUTION: Changed origin to a major hub with available test data.
        "originLocationCode": "MAD", # Madrid, Spain
        "destinationLocationCode": destination_code,
        "departureDate": start_date,
        "adults": 1,
        "nonStop": "false",
        "max": 50,
        # SOLUTION: Changed currency to match the new European route.
        "currencyCode": "EUR" 
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching flight offers: {e}")
        return None

# --- Data Processing and Insight Generation ---
def process_flight_data(flight_data):
    """Processes raw flight data into structured insights using Pandas."""
    if not flight_data or 'data' not in flight_data or not flight_data['data']:
        return None

    carriers = flight_data.get('dictionaries', {}).get('carriers', {})
    
    offers = []
    for offer in flight_data['data']:
        offers.append({
            'price': float(offer['price']['total']),
            'airline': carriers.get(offer['itineraries'][0]['segments'][0]['carrierCode'], 'Unknown Airline')
        })
    
    df = pd.DataFrame(offers)
    
    if df.empty:
        return None

    price_trends = {
        'min_price': df['price'].min(),
        'avg_price': df['price'].mean(),
        'max_price': df['price'].max()
    }
    
    popular_routes = df.groupby('airline')['price'].agg(['count', 'mean']).reset_index()
    popular_routes = popular_routes.rename(columns={'count': 'deal_count', 'mean': 'avg_price'})
    popular_routes = popular_routes.sort_values(by='deal_count', ascending=False)
    
    return {
        'price_trends': price_trends,
        'popular_routes': popular_routes.to_dict(orient='records')
    }

def get_ai_summary(insights):
    """Generates a human-readable summary using OpenAI's API."""
    if not insights:
        return "No data available to generate a summary."
        
    prompt = f"""
    You are a market analyst. Based on the following airline booking data, provide a short, actionable summary for a manager.
    Focus on pricing and airline popularity.

    Data:
    - Average flight price: €{insights['price_trends']['avg_price']:.2f}
    - Price range: From €{insights['price_trends']['min_price']:.2f} to €{insights['price_trends']['max_price']:.2f}
    - Airline Deals: {insights['popular_routes']}

    Provide a concise, professional summary of 2-3 sentences.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful travel market analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Could not generate AI summary due to an error."

# --- Flask Routes ---
@app.route("/")
def index():
    """Renders the main web page."""
    return render_template("index.html")

@app.route("/api/market-demand", methods=["POST"])
def get_market_demand():
    """API endpoint to fetch, process, and return market demand data."""
    data = request.get_json()
    destination_code = data.get("destination")

    if not destination_code:
        return jsonify({"error": "Destination city code is required."}), 400

    token = get_amadeus_access_token()
    if not token:
        return jsonify({"error": "Could not authenticate with flight data provider."}), 503

    flight_data = search_flight_offers(token, destination_code)
    if not flight_data or not flight_data.get('data'):
        return jsonify({"error": f"No flight data found for destination {destination_code}. This may be due to limited availability in the test API for this route."}), 404
        
    processed_insights = process_flight_data(flight_data)
    if not processed_insights:
        return jsonify({"error": "Could not process the flight data."}), 500
        
    ai_summary = get_ai_summary(processed_insights)

    return jsonify({
        "insights": processed_insights,
        "ai_summary": ai_summary
    })

if __name__ == "__main__":
    app.run(debug=False)