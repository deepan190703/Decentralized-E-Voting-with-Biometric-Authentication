from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import sqlite3
import hashlib
import base64
import os
import requests
import json
import serial
import time
import threading
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from ecdsa import SigningKey, SECP256k1
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from functools import lru_cache
import weakref
import io

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production

# Configuration
BLOCKCHAIN_API_URL = "http://127.0.0.1:8000"
VOTERS_DB = "../voters.db"
CANDIDATES_DB = "../candidates.db"
ARDUINO_PORT = "/dev/cu.usbserial-110"  # Change this to your Arduino port (e.g., /dev/ttyUSB0 on Linux)
ARDUINO_BAUDRATE = 9600

# In-memory image cache with expiration
class ImageCache:
    def __init__(self, max_size=100, default_ttl_minutes=30):
        self.cache = {}
        self.access_times = {}
        self.max_size = max_size
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self._lock = threading.Lock()
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, (_, timestamp) in self.cache.items():
            if current_time - timestamp > self.default_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
    
    def _evict_lru(self):
        """Evict least recently used item if cache is full"""
        if len(self.cache) >= self.max_size:
            # Find least recently accessed item
            lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            self.cache.pop(lru_key, None)
            self.access_times.pop(lru_key, None)
    
    def set(self, key, image_data):
        """Store image data in cache"""
        with self._lock:
            self._cleanup_expired()
            self._evict_lru()
            
            current_time = datetime.now()
            self.cache[key] = (image_data, current_time)
            self.access_times[key] = current_time
    
    def get(self, key):
        """Retrieve image data from cache"""
        with self._lock:
            self._cleanup_expired()
            
            if key in self.cache:
                image_data, _ = self.cache[key]
                self.access_times[key] = datetime.now()  # Update access time
                return image_data
            return None
    
    def has(self, key):
        """Check if key exists in cache"""
        with self._lock:
            self._cleanup_expired()
            return key in self.cache
    
    def clear(self):
        """Clear all cached images"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
    
    def get_stats(self):
        """Get cache statistics"""
        with self._lock:
            self._cleanup_expired()
            return {
                'total_entries': len(self.cache),
                'max_size': self.max_size,
                'cache_hit_ratio': getattr(self, '_hit_count', 0) / max(getattr(self, '_request_count', 1), 1)
            }

# Global image cache instance
image_cache = ImageCache(max_size=200, default_ttl_minutes=60)

# Arduino connection with auto-reconnect
arduino = None
arduino_status = {"connected": False, "last_attempt": None, "error_message": ""}

def connect_arduino():
    """Attempt to connect to Arduino"""
    global arduino, arduino_status
    try:
        if arduino and arduino.is_open:
            arduino.close()
        
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUDRATE, timeout=10)
        time.sleep(2)  # Wait for Arduino to initialize
        
        # Test connection by sending a simple command
        arduino.write(b"STATUS\n")
        arduino.flush()
        
        arduino_status["connected"] = True
        arduino_status["error_message"] = ""
        arduino_status["last_attempt"] = datetime.now()
        print("Arduino connected successfully")
        return True
        
    except Exception as e:
        arduino = None
        arduino_status["connected"] = False
        arduino_status["error_message"] = str(e)
        arduino_status["last_attempt"] = datetime.now()
        print(f"Arduino connection failed: {e}")
        return False

def arduino_connection_monitor():
    """Background thread to monitor and reconnect Arduino"""
    while True:
        try:
            if not arduino_status["connected"]:
                print("Attempting to reconnect Arduino...")
                connect_arduino()
            elif arduino and not arduino.is_open:
                print("Arduino disconnected, attempting reconnection...")
                arduino_status["connected"] = False
                connect_arduino()
            
            time.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            print(f"Arduino monitor error: {e}")
            time.sleep(10)

# Initial Arduino connection
connect_arduino()

# Start Arduino monitoring thread
arduino_thread = threading.Thread(target=arduino_connection_monitor, daemon=True)
arduino_thread.start()

# Encryption helper functions
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def encrypt_data(data: str, password: str) -> str:
    salt = os.urandom(16)
    key = derive_key(password, salt)
    cipher_suite = Fernet(key)
    encrypted = cipher_suite.encrypt(data.encode())
    return base64.urlsafe_b64encode(salt + encrypted).decode()

def decrypt_data(encrypted_data: str, password: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(encrypted_data.encode())
        salt = raw[:16]
        encrypted = raw[16:]
        key = derive_key(password, salt)
        cipher_suite = Fernet(key)
        return cipher_suite.decrypt(encrypted).decode()
    except Exception as e:
        return None

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def verify_password(stored_hash, password):
    return check_password_hash(stored_hash, password)

def get_voter_nonce(public_key):
    try:
        response = requests.get(f"{BLOCKCHAIN_API_URL}/nonce/{public_key}")
        if response.status_code == 200:
            return int(response.text.strip('"'))
        return 0
    except:
        return 0

def sign_transaction(private_key_hex, sender_pub, receiver, amount, nonce):
    message = f"{sender_pub}{receiver}{amount}{nonce}".encode()
    sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    signature = sk.sign(message).hex()
    return signature

def send_vote_transaction(voter_private_key, voter_public_key, candidate_public_key):
    try:
        nonce = get_voter_nonce(voter_public_key)
        signature = sign_transaction(voter_private_key, voter_public_key, candidate_public_key, 1, nonce)
        
        transaction = {
            "sender": voter_public_key,
            "receiver": candidate_public_key,
            "amount": 1,
            "nonce": nonce,
            "signature": signature
        }
        
        response = requests.post(f"{BLOCKCHAIN_API_URL}/transaction", json=transaction)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

# Image handling functions using in-memory cache
def load_voter_image_to_cache(voter_id):
    """Load voter image from database to cache"""
    try:
        cache_key = f"voter_{voter_id}"
        
        # Check if already in cache
        if image_cache.has(cache_key):
            return True
        
        # Load from database
        conn = get_db_connection(VOTERS_DB)
        voter = conn.execute('SELECT photo_base64 FROM voters WHERE id = ?', (voter_id,)).fetchone()
        conn.close()
        
        if voter and voter['photo_base64']:
            # Clean base64 data
            base64_data = voter['photo_base64']
            if base64_data.startswith('data:image'):
                base64_data = base64_data.split(',')[1]
            
            # Decode and store in cache
            try:
                image_bytes = base64.b64decode(base64_data)
                image_cache.set(cache_key, image_bytes)
                return True
            except Exception as e:
                print(f"Error decoding image for voter {voter_id}: {e}")
                return False
        
        return False
    except Exception as e:
        print(f"Error loading voter image: {e}")
        return False

def get_voter_image_data(voter_id):
    """Get voter image data from cache or database"""
    cache_key = f"voter_{voter_id}"
    
    # Try to get from cache first
    image_data = image_cache.get(cache_key)
    if image_data:
        return image_data
    
    # Load to cache and try again
    if load_voter_image_to_cache(voter_id):
        return image_cache.get(cache_key)
    
    return None

def preload_voter_images():
    """Preload all voter images into cache (call during startup or periodically)"""
    try:
        conn = get_db_connection(VOTERS_DB)
        voters = conn.execute('SELECT id FROM voters WHERE photo_base64 IS NOT NULL AND photo_base64 != ""').fetchall()
        conn.close()
        
        loaded_count = 0
        for voter in voters:
            if load_voter_image_to_cache(voter['id']):
                loaded_count += 1
        
        print(f"Preloaded {loaded_count} voter images into cache")
    except Exception as e:
        print(f"Error preloading images: {e}")

# Arduino fingerprint functions
def wait_for_response(expected_response, timeout=30):
    """Wait for specific response from Arduino"""
    if not arduino or not arduino_status["connected"]:
        return None
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if arduino.in_waiting > 0:
                response = arduino.readline().decode().strip()
                print(f"Arduino response: {response}")
                if expected_response in response or response == expected_response:
                    return response
                elif "ERROR" in response:
                    return response
        except Exception as e:
            print(f"Arduino communication error: {e}")
            arduino_status["connected"] = False
            return None
        time.sleep(0.1)
    return None

def decrypt_password_with_voter_id(encrypted_password, voter_id):
    """Decrypt the password using the voter ID as encryption key"""
    try:
        encryption_key = str(voter_id)
        decrypted_password = decrypt_data(encrypted_password, encryption_key)
        return decrypted_password
    except Exception as e:
        return None

def fingerprint_login_with_arduino():
    """Authenticate user using fingerprint via Arduino"""
    try:
        if not arduino or not arduino_status["connected"]:
            return {"success": False, "message": "Arduino not connected."}

        # Send 'MATCH' command to Arduino
        arduino.write(b"MATCH\n")
        arduino.flush()

        # Wait for matching to start
        response = wait_for_response("MATCH_RUNNING", timeout=10)
        if not response:
            return {"success": False, "message": "Arduino not responding"}

        print("Fingerprint matching started. Place your finger on the sensor...")

        # Wait for match result (up to 30 seconds)
        start_time = time.time()
        while time.time() - start_time < 30:
            try:
                if arduino.in_waiting > 0:
                    response = arduino.readline().decode().strip()
                    print(f"Arduino response: {response}")
                    
                    if "Match found! ID:" in response:
                        # Extract voter ID from response
                        voter_id = int(response.split("ID: ")[1])
                        return {"success": True, "voter_id": voter_id, "message": "Fingerprint matched successfully"}
                    elif "No match found" in response:
                        continue  # Keep waiting for a match
                    elif "ERROR" in response:
                        return {"success": False, "message": f"Arduino error: {response}"}
                        
            except Exception as e:
                print(f"Arduino communication error: {e}")
                arduino_status["connected"] = False
                
            time.sleep(0.1)
        
        return {"success": False, "message": "Fingerprint matching timeout. Please try again."}
        
    except Exception as e:
        arduino_status["connected"] = False
        return {"success": False, "message": f"Arduino error: {str(e)}"}

# Routes
@app.route('/voter-image/<int:voter_id>')
def serve_voter_image(voter_id):
    """Serve voter image from cache"""
    try:
        image_data = get_voter_image_data(voter_id)
        if image_data:
            return Response(image_data, mimetype='image/jpeg')
        else:
            # Return default image or 404
            return redirect(url_for('static', filename='images/default_voter.png'))
    except Exception as e:
        print(f"Error serving image for voter {voter_id}: {e}")
        return redirect(url_for('static', filename='images/default_voter.png'))

@app.route('/voter-image-base64/<int:voter_id>')
def get_voter_image_base64(voter_id):
    """Get voter image as base64 (for direct embedding in templates)"""
    try:
        image_data = get_voter_image_data(voter_id)
        if image_data:
            base64_image = base64.b64encode(image_data).decode('utf-8')
            return jsonify({
                'success': True,
                'image_data': f"data:image/jpeg;base64,{base64_image}"
            })
        else:
            return jsonify({'success': False, 'message': 'Image not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/')
def index():
    if 'voter_id' in session:
        return redirect(url_for('voting_portal'))
    return render_template('login.html', 
                         arduino_available=arduino_status["connected"],
                         arduino_status=arduino_status)

@app.route('/login', methods=['POST'])
def login():
    voter_id = int(request.form['voter_id'])
    password = request.form['password']
    
    conn = get_db_connection(VOTERS_DB)
    voter = conn.execute('SELECT * FROM voters WHERE id = ?', (voter_id,)).fetchone()
    conn.close()
    
    if voter and verify_password(voter['password_hash'], password):
        session['voter_id'] = voter['id']
        session['voter_name'] = voter['name']
        session['voter_public_key'] = voter['public_key']
        
        # Preload voter image to cache
        load_voter_image_to_cache(voter['id'])
        
        # Decrypt private key
        decrypted_private_key = decrypt_data(voter['private_key_encrypted'], password)
        if decrypted_private_key:
            session['voter_private_key'] = decrypted_private_key
            flash('Login successful!', 'success')
            return redirect(url_for('voting_portal'))
        else:
            flash('Failed to decrypt private key. Please check your password.', 'error')
    else:
        flash('Invalid voter ID or password.', 'error')
    
    return redirect(url_for('index'))

@app.route('/fingerprint-login', methods=['POST'])
def fingerprint_login():
    """Handle fingerprint-based login"""
    try:
        result = fingerprint_login_with_arduino()
        
        if result['success']:
            voter_id = result['voter_id']
            
            # Get voter information from database
            conn = get_db_connection(VOTERS_DB)
            voter = conn.execute('SELECT * FROM voters WHERE id = ?', (voter_id,)).fetchone()
            
            if not voter:
                conn.close()
                return jsonify({'success': False, 'message': 'Voter not found in database'})
            
            # Check if voter has fingerprint hash (encrypted password)
            if not voter['fingerprint_hash']:
                conn.close()
                return jsonify({'success': False, 'message': 'Fingerprint not enrolled for this voter'})
            
            # Decrypt the password using voter ID
            decrypted_password = decrypt_password_with_voter_id(voter['fingerprint_hash'], voter_id)
            if not decrypted_password:
                conn.close()
                return jsonify({'success': False, 'message': 'Failed to decrypt voter credentials'})
            
            # Decrypt private key using the decrypted password
            decrypted_private_key = decrypt_data(voter['private_key_encrypted'], decrypted_password)
            if not decrypted_private_key:
                conn.close()
                return jsonify({'success': False, 'message': 'Failed to decrypt private key'})
            
            conn.close()
            
            # Set session variables
            session['voter_id'] = voter['id']
            session['voter_name'] = voter['name']
            session['voter_public_key'] = voter['public_key']
            session['voter_private_key'] = decrypted_private_key
            
            # Preload voter image to cache
            load_voter_image_to_cache(voter['id'])
            
            return jsonify({
                'success': True, 
                'message': f'Welcome {voter["name"]}! Fingerprint login successful.',
                'redirect_url': url_for('voting_portal')
            })
        
        else:
            return jsonify({'success': False, 'message': result['message']})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login failed: {str(e)}'})

@app.route('/check-fingerprint-status')
def check_fingerprint_status():
    """Check if Arduino is connected and ready for fingerprint operations"""
    return jsonify({
        'arduino_connected': arduino_status["connected"],
        'status': 'ready' if arduino_status["connected"] else 'disconnected',
        'last_attempt': arduino_status["last_attempt"].isoformat() if arduino_status["last_attempt"] else None,
        'error_message': arduino_status["error_message"]
    })

@app.route('/reconnect-arduino', methods=['POST'])
def reconnect_arduino():
    """Manually trigger Arduino reconnection"""
    success = connect_arduino()
    return jsonify({
        'success': success,
        'connected': arduino_status["connected"],
        'message': 'Connected successfully' if success else arduino_status["error_message"]
    })

@app.route('/voting-portal')
def voting_portal():
    if 'voter_id' not in session:
        return redirect(url_for('index'))
    
    # Get candidates
    conn = get_db_connection(CANDIDATES_DB)
    candidates = conn.execute('SELECT * FROM candidates').fetchall()
    conn.close()
    
    voter_id = session['voter_id']
    return render_template('voting_portal.html', 
                         voter_name=session['voter_name'],
                         voter_id=voter_id,
                         candidates=candidates)

@app.route('/cast-vote', methods=['POST'])
def cast_vote():
    if 'voter_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    candidate_id = request.form['candidate_id']
    
    # Get candidate public key
    conn = get_db_connection(CANDIDATES_DB)
    candidate = conn.execute('SELECT * FROM candidates WHERE id = ?', (candidate_id,)).fetchone()
    conn.close()
    
    if not candidate:
        return jsonify({'success': False, 'message': 'Candidate not found'})
    
    # Send transaction to blockchain
    success, message = send_vote_transaction(
        session['voter_private_key'],
        session['voter_public_key'],
        candidate['public_key']
    )
    
    if success:
        return jsonify({'success': True, 'message': 'Vote cast successfully!'})
    else:
        return jsonify({'success': False, 'message': f'Failed to cast vote: {message}'})

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/check-balance')
def check_balance():
    if 'voter_id' not in session:
        return jsonify({'balance': 0})
    
    try:
        response = requests.get(f"{BLOCKCHAIN_API_URL}/balance?address={session['voter_public_key']}")
        if response.status_code == 200:
            data = response.json()
            balance = int(data.get('balance', 0))
            return jsonify({'balance': balance})
    except:
        pass
    
    return jsonify({'balance': 0})

@app.route('/preload-images')
def preload_images():
    """Manually trigger image preloading"""
    preload_voter_images()
    return jsonify({'message': 'Image preloading completed', 'cache_stats': image_cache.get_stats()})

@app.route('/cache-stats')
def cache_stats():
    """Get cache statistics"""
    return jsonify(image_cache.get_stats())

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear image cache"""
    image_cache.clear()
    return jsonify({'message': 'Cache cleared successfully'})

if __name__ == '__main__':
    # Preload images on startup
    preload_voter_images()
    app.run(debug=True, port=5004)