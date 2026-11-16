from flask import Flask, render_template, jsonify
import sqlite3
import requests
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Global variables to store voting data
voting_data = {}
last_update = None

# Database connection to your existing candidates table
def get_db_connection():
    # Replace 'your_database.db' with your actual database path
    conn = sqlite3.connect('../candidates.db')
    conn.row_factory = sqlite3.Row
    return conn

# Fetch all candidates from your existing table
def get_candidates():
    conn = get_db_connection()
    candidates = conn.execute('SELECT * FROM candidates').fetchall()
    conn.close()
    return candidates

# Fetch balance from blockchain API
def fetch_balance(public_key):
    try:
        # Your blockchain API endpoint
        url = f"http://127.0.0.1:8000/balance?address={public_key}"
        headers = {'accept': 'application/json'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse balance from your API response
            # Adjust the key name based on your actual API response format
            # Common formats: 'balance', 'result', 'data', etc.
            balance = data.get('balance', 0)
            
            # If balance is in smallest unit (like wei, satoshi), convert to main unit
            # For example: balance = balance / 1000000000000000000  # wei to ETH
            # Or: balance = balance / 100000000  # satoshi to BTC
            # Adjust based on your token's decimal places
            
            return float(balance) if balance else 0
        else:
            print(f"API error for {public_key}: Status {response.status_code}")
            return 0
            
    except requests.exceptions.Timeout:
        print(f"Timeout fetching balance for {public_key}")
        return 0
    except requests.exceptions.ConnectionError:
        print(f"Connection error fetching balance for {public_key}")
        return 0
    except Exception as e:
        print(f"Error fetching balance for {public_key}: {e}")
        return 0

# Update voting data by fetching balances
def update_voting_data():
    global voting_data, last_update
    
    candidates = get_candidates()
    new_data = {}
    
    for candidate in candidates:
        balance = fetch_balance(candidate['public_key'])
        new_data[candidate['id']] = {
            'id': candidate['id'],
            'name': candidate['name'],
            'party': candidate['party'],
            'public_key': candidate['public_key'],
            'image_base64': candidate['image_base64'],  # Add image data
            'logo_base64': candidate['logo_base64'],    # Add logo data
            'balance': balance,
            'votes': int(balance * 1)  # Convert balance to vote count
        }
    
    voting_data = new_data
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Background thread to update data every 30 seconds
def background_updater():
    while True:
        update_voting_data()
        time.sleep(30)

# Start background thread
update_thread = threading.Thread(target=background_updater, daemon=True)
update_thread.start()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/voting-data')
def get_voting_data():
    if not voting_data:
        update_voting_data()
    
    # Calculate total votes and percentages
    total_votes = sum(candidate['votes'] for candidate in voting_data.values())
    
    results = []
    for candidate in voting_data.values():
        percentage = (candidate['votes'] / total_votes * 100) if total_votes > 0 else 0
        results.append({
            'id': candidate['id'],
            'name': candidate['name'],
            'party': candidate['party'],
            'votes': candidate['votes'],
            'balance': candidate['balance'],
            'percentage': round(percentage, 2),
            'image_base64': candidate['image_base64'],  # Include image data in API response
            'logo_base64': candidate['logo_base64']     # Include logo data in API response
        })
    
    # Sort by votes (descending)
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    return jsonify({
        'candidates': results,
        'total_votes': total_votes,
        'last_update': last_update
    })

if __name__ == '__main__':
    # Initial data load
    update_voting_data()
    app.run(debug=True, threaded=True, port=5003)