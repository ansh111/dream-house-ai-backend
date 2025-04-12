from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import google.generativeai as genai
import requests
from twilio.rest import Client
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Initialize app
app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# API keys and config
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
search_id = os.getenv("SEARCH_ENGINE_ID")
search_api_key = os.getenv("SEARCH_API_KEY")

# Twilio config
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_WHATSAPP_SENDER = "whatsapp:" + TWILIO_PHONE_NUMBER
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def fetch_property_data(query):
    property_data = []
    for start in range(1, 101, 10):
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&cx={search_id}&key={search_api_key}&start={start}"
        search_data = requests.get(url).json()
        for item in search_data.get('items', []):
            property_data.append({
                "title": item["title"],
                "link": item["link"],
                "description": item["snippet"]
            })

    return "\n".join(
        [f"{idx + 1}. {prop['title']} - {prop['link']}\nDescription: {prop['description']}"
         for idx, prop in enumerate(property_data)]
    )


def get_gemini_resp(input_prompt, response):
    model = genai.GenerativeModel('gemini-1.5-flash')
    output = model.generate_content([input_prompt, response])
    return output.text


@app.route('/api/find-properties', methods=['POST'])
def find_properties():
    data = request.get_json()
    user_query = data.get('query')
    whatsapp_number = data.get('whatsappNumber')  # Optional

    if not user_query:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    # Define Gemini input prompt
    new_input_prompt = """
    You are a specialist in finding houses for rent, so based on the provided data, suggest the best
    possible matches. Optimize the search results based on the user's budget and preferences.

    Please analyze the listings and provide a summary of the best available options, highlighting:
    1. Show the selected listing details (title, description).
    2. Show the selected exact matching listing URLs.
    3. If possible display the price of the house if available in description or title.
    4. Show URL of listing under heading URL

    Be concise and easy to understand. Only include the BEST listing available and try to provide top 5 options

    Data:
    """

    try:
        property_info = fetch_property_data(user_query)
        gemini_response = get_gemini_resp(new_input_prompt, property_info)

        # Send via WhatsApp if number provided
        if whatsapp_number:
            try:
                client.messages.create(
                    body=gemini_response,
                    from_=TWILIO_WHATSAPP_SENDER,
                    to=f"whatsapp:{whatsapp_number}"
                )
            except Exception as e:
                return jsonify({"error": f"Failed to send WhatsApp message: {str(e)}"}), 500

        return jsonify({"response": gemini_response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
