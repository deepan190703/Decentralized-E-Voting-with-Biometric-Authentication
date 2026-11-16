from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import sqlite3
import json
import os
import base64
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from cryptography.fernet import Fernet
from ecdsa import SigningKey, SECP256k1
import qrcode
from PIL import Image
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import blue, black, gray, white ,red,Color
from reportlab.lib.units import inch
import tempfile
import serial
import time
import hashlib
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Generate encryption key (in production, store this securely)
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Arduino Configuration - Updated to match ATM system
ARDUINO_PORT = "/dev/cu.usbserial-110"  # Replace with your Arduino port
BAUD_RATE = 9600
ARDUINO_TIMEOUT = 30  # Timeout (in seconds) for Arduino responses

# Initialize Arduino connection
try:
    arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=2)
    print(f"Arduino connected successfully on {ARDUINO_PORT}")
except Exception as e:
    print(f"Error initializing Arduino: {e}")
    arduino = None

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    """Initialize the database with voters table"""
    conn = sqlite3.connect('../voters.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            dob TEXT NOT NULL,
            photo_base64 TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            private_key_encrypted TEXT NOT NULL,
            public_key TEXT NOT NULL UNIQUE,
            fingerprint_hash TEXT,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def create_key_pair():
    """Generate ECDSA key pair"""
    sk = SigningKey.generate(curve=SECP256k1)
    pk = sk.verifying_key
    
    return {
        "private_key": sk.to_string().hex(),
        "public_key": pk.to_string().hex()
    }

def generate_unique_key_pair():
    """Generate ECDSA key pair and ensure public key is unique"""
    max_attempts = 10  # Prevent infinite loop
    attempt = 0
    
    while attempt < max_attempts:
        # Generate new key pair
        keys = create_key_pair()
        
        # Check if public key already exists in database
        conn = sqlite3.connect('../voters.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM voters WHERE public_key = ?', (keys['public_key'],))
        existing = cursor.fetchone()
        conn.close()
        
        if not existing:
            # Public key is unique
            return keys
        
        attempt += 1
    
    # If we couldn't generate a unique key after max_attempts
    raise Exception("Unable to generate unique public key after multiple attempts")






# Function to derive a Fernet key from a password and salt
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

# Encrypt function using password
def encrypt_data(data: str, password: str) -> str:
    salt = os.urandom(16)  # Secure random salt
    key = derive_key(password, salt)
    cipher_suite = Fernet(key)
    encrypted = cipher_suite.encrypt(data.encode())

    # Return base64-encoded salt + encrypted data
    return base64.urlsafe_b64encode(salt + encrypted).decode()

# Decrypt function using password
def decrypt_data(encrypted_data: str, password: str) -> str:
    raw = base64.urlsafe_b64decode(encrypted_data.encode())
    salt = raw[:16]
    encrypted = raw[16:]
    key = derive_key(password, salt)
    cipher_suite = Fernet(key)
    return cipher_suite.decrypt(encrypted).decode()

def create_fingerprint_hash(voter_id):
    """Create a hash for fingerprint storage using voter ID"""
    # Create a hash using voter ID and timestamp for uniqueness
    # timestamp = str(int(time.time()))
    hash_input = f"{voter_id}"
    fingerprint_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]  # Use first 16 chars
    return fingerprint_hash

# Updated Arduino communication functions to match ATM system
def wait_for_response(expected_response, timeout=ARDUINO_TIMEOUT):
    """Function to wait for a response from Arduino - Same as ATM system"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if arduino.in_waiting > 0:
            response = arduino.readline().decode().strip()
            if response == expected_response or response.startswith(expected_response):
                return response
    return None

# def enroll_fingerprint_with_arduino(voter_id):
#     """Enroll fingerprint using Arduino - Updated to match ATM system logic"""
#     try:
#         if not arduino:
#             return {"success": False, "message": "Arduino not connected."}

#         # Send 'ENROLL' command to Arduino
#         arduino.write(b"ENROLL\n")
#         arduino.flush()

#         # Wait for Arduino to request an ID
#         response = wait_for_response("SEND_ID")
#         if not response:
#             return {"success": False, "message": "Timeout waiting for SEND_ID"}

#         # Convert voter_id to bytes and encode in Base64 (same as ATM system)
#         number = voter_id
#         number_bytes = number.to_bytes((number.bit_length() + 7) // 8, byteorder="big")
#         encoded_number = base64.b64encode(number_bytes).decode()

#         # Send the voter ID to Arduino
#         arduino.write(f"{voter_id}\n".encode("utf-8"))
#         arduino.flush()

#         # Wait for enrollment success or failure
#         response = wait_for_response("ENROLL_SUCCESS")
#         if response == "ENROLL_SUCCESS":
#             # Create fingerprint hash for this voter
#             fingerprint_hash = create_fingerprint_hash(voter_id)
            
#             # Update database with fingerprint hash
#             conn = sqlite3.connect('../voters.db')
#             cursor = conn.cursor()
#             cursor.execute('UPDATE voters SET fingerprint_hash = ? WHERE id = ?', 
#                          (fingerprint_hash, voter_id))
#             conn.commit()
#             conn.close()
            
#             return {"success": True, "fingerprint_hash": fingerprint_hash, "message": "Fingerprint enrolled successfully"}

#         elif response == "ENROLL_FAILED":
#             return {"success": False, "message": "Fingerprint enrollment failed."}
#         else:
#             return {"success": False, "message": "Unexpected response from Arduino."}
            
#     except Exception as e:
#         return {"success": False, "message": f"Arduino error: {str(e)}"}


def decrypt_password_with_voter_id(encrypted_password, voter_id):
    """Decrypt the password using the voter ID"""
    try:
        encryption_key = str(voter_id)
        decrypted_password = decrypt_data(encrypted_password, encryption_key)
        return decrypted_password
    except Exception as e:
        return None

def encrypt_password_with_voter_id(password, voter_id):
    """Encrypt password using voter ID as encryption key"""
    # Use voter_id as the encryption key
    encryption_key = str(voter_id)
    encrypted_password = encrypt_data(password, encryption_key)
    return encrypted_password

def enroll_fingerprint_with_arduino(voter_id, password):
    """Enroll fingerprint using Arduino - Encrypt password with voter_id if successful"""
    try:
        if not arduino:
            return {"success": False, "message": "Arduino not connected."}

        # Send 'ENROLL' command to Arduino
        arduino.write(b"ENROLL\n")
        arduino.flush()

        # Wait for Arduino to request an ID
        response = wait_for_response("SEND_ID")
        if not response:
            return {"success": False, "message": "Timeout waiting for SEND_ID"}

        # Convert voter_id to bytes and encode in Base64 (same as ATM system)
        number = voter_id
        number_bytes = number.to_bytes((number.bit_length() + 7) // 8, byteorder="big")
        encoded_number = base64.b64encode(number_bytes).decode()

        # Send the voter ID to Arduino
        arduino.write(f"{voter_id}\n".encode("utf-8"))
        arduino.flush()

        # Wait for enrollment success or failure
        response = wait_for_response("ENROLL_SUCCESS")
        if response == "ENROLL_SUCCESS":
            # Encrypt the password using voter_id
            encrypted_password = encrypt_password_with_voter_id(password, voter_id)
            
            # Update database with encrypted password in fingerprint_hash field
            conn = sqlite3.connect('../voters.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE voters SET fingerprint_hash = ? WHERE id = ?', 
                         (encrypted_password, voter_id))
            conn.commit()
            conn.close()
            
            return {"success": True, "fingerprint_hash": encrypted_password, "message": "Fingerprint enrolled successfully"}

        elif response == "ENROLL_FAILED":
            return {"success": False, "message": "Fingerprint enrollment failed."}
        else:
            return {"success": False, "message": "Unexpected response from Arduino."}
            
    except Exception as e:
        return {"success": False, "message": f"Arduino error: {str(e)}"}


def authenticate_fingerprint_with_arduino():
    """Authenticate fingerprint using Arduino - Updated to match ATM system logic"""
    try:
        if not arduino:
            return {"success": False, "message": "Arduino not connected."}

        # Send 'MATCH' command to Arduino
        arduino.write(b"MATCH\n")
        arduino.flush()

        # Wait for up to 30 seconds for a response (same as ATM system)
        timeout = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if arduino.in_waiting:  # Check if Arduino sent any data
                response = arduino.readline().decode().strip()
                print(f"Arduino Response: {response}")

                if response.startswith("Match found! ID:"):
                    # Extract the fingerprint ID
                    fingerprint_id = int(response.split(":")[1].strip())
                    
                    # Find voter with matching fingerprint
                    conn = sqlite3.connect('../voters.db')
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM voters WHERE id = ?', (fingerprint_id,))
                    voter = cursor.fetchone()
                    conn.close()
                    
                    if voter:
                        voter_data = {
                            "id": voter[0],
                            "name": voter[1],
                            "phone": voter[2],
                            "dob": voter[3],
                            "public_key": voter[7],
                            "fingerprint_hash": voter[8]
                        }
                        return {"success": True, "message": "Fingerprint authentication successful.", "voter_data": voter_data}
                    else:
                        return {"success": False, "message": "Voter not found in database."}
                else:
                    continue

        return {"success": False, "message": "Fingerprint authentication timed out."}

    except Exception as e:
        return {"success": False, "message": f"Arduino error: {str(e)}"}

def process_image_data(image_data, is_base64=True):
    """Process image data and create passport-style crop"""
    try:
        if is_base64:
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
        else:
            # Direct file bytes
            image_bytes = image_data
        
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Passport-style cropping (3:4 aspect ratio)
        width, height = image.size
        
        # Calculate crop dimensions for passport style
        if width > height:
            # Landscape - crop to square first, then resize
            crop_size = min(width, height)
            left = (width - crop_size) // 2
            top = (height - crop_size) // 2
            image = image.crop((left, top, left + crop_size, top + crop_size))
        
        # Resize to passport dimensions (3:4 ratio, 300x400 pixels)
        passport_size = (300, 400)
        image = image.resize(passport_size, Image.Resampling.LANCZOS)
        
        # Save to base64
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return img_base64
    except Exception as e:
        raise ValueError(f"Error processing image: {str(e)}")

def generate_qr_code_image(data):
    """Generate QR code and return as temporary file path"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to temporary file
    temp_qr = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    qr_img.save(temp_qr.name)
    temp_qr.close()
    
    return temp_qr.name

def save_photo_temp_file(base64_data):
    """Save base64 photo to temporary file"""
    try:
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Save to temporary file
        temp_photo = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        image.save(temp_photo.name, 'JPEG')
        temp_photo.close()
        
        return temp_photo.name
    except:
        return None

def create_pdf_voting_card(voter_data):
    """Generate PDF voting card with voter information and QR code"""
    # Create temporary file for PDF
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_pdf.close()
    
    # Create canvas with custom page size (credit card size scaled up)
    card_width = 8.5 * inch  # 8.5 inches wide
    card_height = 5.4 * inch  # 5.4 inches tall
    c = canvas.Canvas(temp_pdf.name, pagesize=(card_width, card_height))
    
    # Set up margins
    margin = 0.3 * inch
    
    # Draw main card border
    c.setStrokeColor(black)
    c.setLineWidth(3)
    c.rect(0.1 * inch, 0.1 * inch, card_width - 0.2 * inch, card_height - 0.2 * inch)
    
    # Header background
    c.setFillColor(Color(0.0, 0.5, 0.5))
    c.rect(0.2 * inch, card_height - 1.2 * inch, card_width - 0.4 * inch, 0.8 * inch, fill=1)
    
    # Title
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 24)
    title_text = "VOTER CARD"
    text_width = c.stringWidth(title_text, "Helvetica-Bold", 24)
    c.drawString((card_width - text_width) / 2, card_height - 0.9 * inch, title_text)
    
    # Reset color for content
    c.setFillColor(black)
    
    # Voter Information Section
    info_start_y = card_height - 1.8 * inch
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, info_start_y, f"Name: {voter_data['name']}")
    
    c.setFont("Helvetica", 14)
    c.drawString(margin, info_start_y - 0.3 * inch, f"Phone: {voter_data['phone']}")
    c.drawString(margin, info_start_y - 0.6 * inch, f"Date of Birth: {voter_data['dob']}")
    c.drawString(margin, info_start_y - 0.9 * inch, f"Voter ID: {str(voter_data['id']).zfill(6)}")
    
    # Add fingerprint status
    fingerprint_status = "✓ Fingerprint Enrolled" if voter_data.get('fingerprint_hash') else "✗ No Fingerprint"
    c.setFont("Helvetica", 12)
    c.setFillColor(Color(0.0, 0.6, 0.0) if voter_data.get('fingerprint_hash') else Color(0.8, 0.0, 0.0))
    c.drawString(margin, info_start_y - 1.2 * inch, fingerprint_status)
    c.setFillColor(black)
    
    # Add photo if available
    photo_path = save_photo_temp_file(voter_data['photo_base64'])
    if photo_path:
        try:
            # Position photo on the right side
            photo_x = card_width - 2 * inch
            photo_y = info_start_y - 1.75 * inch
            photo_width = 1.6 * inch
            photo_height = 2 * inch
            
            c.drawImage(photo_path, photo_x, photo_y, 
                       width=photo_width, height=photo_height, mask='auto')
            
            # Clean up temp file
            os.unlink(photo_path)
        except Exception as e:
            # If photo fails, draw placeholder
            c.setStrokeColor(gray)
            c.rect(photo_x, photo_y, photo_width, photo_height)
            c.setFont("Helvetica", 10)
            c.drawString(photo_x + 0.5 * inch, photo_y + 0.5 * inch, "PHOTO")
    
    # Generate and add QR code
    qr_path = generate_qr_code_image(voter_data['public_key'])
    try:
        qr_x = margin
        qr_y = 0.5 * inch
        qr_size = 1.5 * inch
        
        c.drawImage(qr_path, qr_x, qr_y, width=qr_size, height=qr_size, mask='auto')
        
        # QR code label
        c.setFont("Helvetica", 10)
        c.drawString(qr_x+0.15*inch, qr_y - 0.2 * inch, "Scan for Public Key")
        
        # Clean up temp file
        os.unlink(qr_path)
    except Exception as e:
        # If QR code fails, draw placeholder
        c.setStrokeColor(gray)
        c.rect(qr_x, qr_y, qr_size, qr_size)
        c.setFont("Helvetica", 10)
        c.drawString(qr_x + .1 * inch, qr_y + 0.7 * inch, "QR CODE")
    
    # Instructions section
    instructions_x = margin + 2 * inch
    instructions_y = 1.8 * inch
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(instructions_x, instructions_y, "Instructions:")
    
    c.setFont("Helvetica", 10)
    instructions = [
        "1. Keep this card safe and secure",
        "2. Use QR code and password to login for voting",
        "3. Use fingerprint for quick authentication",
        "4. Present this card at polling station"
    ]
    
    for i, instruction in enumerate(instructions):
        c.drawString(instructions_x, instructions_y - (i + 1) * 0.25 * inch, instruction)
    
    # Public key (truncated)
    c.setFont("Helvetica", 8)
    pk_display = f"Public Key: {voter_data['public_key'][:40]}..."
    c.drawString(instructions_x, instructions_y - 1.5 * inch, pk_display)
    
    # Registration date
    c.setFont("Helvetica", 10)
    c.setFillColor(gray)
    reg_date = datetime.now().strftime("%B %d, %Y")
    c.drawString(instructions_x+300, 0.3 * inch, f"Registered: {reg_date}")
    
    # Save the PDF
    c.save()
    
    return temp_pdf.name

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        password = request.form.get('password')
        photo_data = request.form.get('photo_data')
        enroll_fingerprint = request.form.get('enroll_fingerprint') == 'on'
        
        # Validate required fields
        if not all([name, phone, dob, password]):
            flash('All fields are required!', 'error')
            return render_template('register.html')
        
        # Validate date of birth
        try:
            dob_date = datetime.strptime(dob, '%Y-%m-%d')
            if dob_date >= datetime.now():
                flash('Date of birth must be in the past!', 'error')
                return render_template('register.html')
        except ValueError:
            flash('Invalid date format!', 'error')
            return render_template('register.html')
        
        # Handle photo processing
        processed_photo = None
        
        # Check if photo_data is provided (webcam capture)
        if photo_data:
            try:
                processed_photo = process_image_data(photo_data, is_base64=True)
            except ValueError as e:
                flash(f'Photo processing failed: {str(e)}', 'error')
                return render_template('register.html')
        
        # Check if file upload is provided
        elif 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                try:
                    # Read file data
                    file_data = file.read()
                    processed_photo = process_image_data(file_data, is_base64=False)
                except ValueError as e:
                    flash(f'Photo processing failed: {str(e)}', 'error')
                    return render_template('register.html')
            else:
                flash('Please upload a valid image file (PNG, JPG, JPEG, GIF)!', 'error')
                return render_template('register.html')
        
        # If no photo provided
        if not processed_photo:
            flash('Photo is required! Please capture or upload a photo.', 'error')
            return render_template('register.html')
        
        # Generate unique key pair
        try:
            keys = generate_unique_key_pair()
        except Exception as e:
            flash(f'Key generation failed: {str(e)}', 'error')
            return render_template('register.html')
        
        # Create password hash (NOT encrypted as requested)
        password_hash = generate_password_hash(password)
        private_key_encrypted = encrypt_data(keys['private_key'], password)
        
        try:
            # Save to database first
            conn = sqlite3.connect('../voters.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO voters (name, phone, dob, photo_base64, password_hash, private_key_encrypted, public_key)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, phone, dob, processed_photo, password_hash, private_key_encrypted, keys['public_key']))
            
            voter_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Handle fingerprint enrollment if requested
            fingerprint_message = ""
            if enroll_fingerprint:
                fingerprint_result = enroll_fingerprint_with_arduino(voter_id, password)  # Pass password here
                
                if fingerprint_result['success']:
                    fingerprint_message = " Fingerprint enrolled successfully!"
                else:
                    fingerprint_message = f" Fingerprint enrollment failed: {fingerprint_result['message']}"
            
            # Store success message in session to show after redirect
            success_message = f'Registration successful! Your voting card is ready for download.{fingerprint_message}'
            flash(success_message, 'success')
            
            # Redirect to a success page that shows the message and provides download link
            return redirect(url_for('registration_success', voter_id=voter_id))
            
        except sqlite3.IntegrityError as e:
            if 'phone' in str(e):
                flash('Phone number already registered!', 'error')
            elif 'public_key' in str(e):
                flash('Key generation conflict. Please try registering again.', 'error')
            else:
                flash('Registration failed due to duplicate data!', 'error')
            return render_template('register.html')
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')
@app.route('/registration-success/<int:voter_id>')
def registration_success(voter_id):
    """Show registration success page with download link"""
    conn = sqlite3.connect('../voters.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM voters WHERE id = ?', (voter_id,))
    voter = cursor.fetchone()
    conn.close()
    
    if not voter:
        flash('Voter not found!', 'error')
        return redirect(url_for('index'))
    
    return render_template('registration_success.html', voter_name=voter[0], voter_id=voter_id)


# @app.route('/fingerprint-enroll', methods=['POST'])
# def fingerprint_enroll():
#     """AJAX endpoint for fingerprint enrollment"""
#     try:
#         data = request.get_json()
#         voter_id = data.get('voter_id')
        
#         if not voter_id:
#             return jsonify({'success': False, 'message': 'Voter ID required'})
        
#         result = enroll_fingerprint_with_arduino(voter_id)
#         return jsonify(result)
        
#     except Exception as e:
#         return jsonify({'success': False, 'message': str(e)})

@app.route('/fingerprint-enroll', methods=['POST'])
def fingerprint_enroll():
    """AJAX endpoint for fingerprint enrollment"""
    try:
        data = request.get_json()
        voter_id = data.get('voter_id')
        password = data.get('password')  # You'll need to pass this from frontend
        
        if not voter_id or not password:
            return jsonify({'success': False, 'message': 'Voter ID and password required'})
        
        result = enroll_fingerprint_with_arduino(voter_id, password)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})



@app.route('/fingerprint-auth', methods=['POST'])
def fingerprint_auth():
    """AJAX endpoint for fingerprint authentication"""
    try:
        result = authenticate_fingerprint_with_arduino()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/voting-card/<int:voter_id>')
def voting_card(voter_id):
    conn = sqlite3.connect('../voters.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM voters WHERE id = ?', (voter_id,))
    voter = cursor.fetchone()
    conn.close()
    
    if not voter:
        flash('Voter not found!', 'error')
        return redirect(url_for('index'))
    
    voter_data = {
        'id': voter[0],
        'name': voter[1],
        'phone': voter[2],
        'dob': voter[3],
        'photo_base64': voter[4],
        'public_key': voter[7],
        'fingerprint_hash': voter[8]
    }
    
    # Generate PDF voting card
    pdf_path = create_pdf_voting_card(voter_data)
    
    try:
        # Send PDF file
        response = send_file(pdf_path, mimetype='application/pdf', as_attachment=True, 
                           download_name=f'voting_card_{voter_data["name"].replace(" ", "_")}.pdf')
        
        # Clean up temp file after sending
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(pdf_path)
            except:
                pass
        
        return response
    except Exception as e:
        # Clean up on error
        try:
            os.unlink(pdf_path)
        except:
            pass
        flash(f'Error generating voting card: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/voters')
def list_voters():
    """List all registered voters (for admin purposes)"""
    conn = sqlite3.connect('../voters.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, phone, dob, fingerprint_hash, registration_date FROM voters ORDER BY registration_date DESC')
    voters = cursor.fetchall()
    conn.close()
    
    return render_template('voters.html', voters=voters)

@app.errorhandler(413)
def too_large(e):
    flash('File too large! Please upload an image smaller than 16MB.', 'error')
    return redirect(url_for('register'))



# Add these functions and routes to your app.py file

def reconnect_arduino():
    """Reconnect to Arduino"""
    global arduino
    try:
        # Close existing connection if it exists
        if arduino and arduino.is_open:
            arduino.close()
            time.sleep(1)  # Give it a moment to close properly
        
        # Reinitialize Arduino connection
        arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)  # Give Arduino time to initialize
        
        # Test the connection with a simple write/flush
        arduino.flush()
        
        return {"success": True, "message": f"Arduino reconnected successfully on {ARDUINO_PORT}"}
    except Exception as e:
        arduino = None
        return {"success": False, "message": f"Failed to reconnect Arduino: {str(e)}"}

@app.route('/arduino-reconnect', methods=['POST'])
def arduino_reconnect():
    """AJAX endpoint for Arduino reconnection"""
    try:
        result = reconnect_arduino()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/arduino-status', methods=['GET'])
def arduino_status():
    """Check Arduino connection status"""
    try:
        if arduino and arduino.is_open:
            # Try to check if the port is actually responsive
            try:
                arduino.flush()
                return jsonify({
                    'connected': True, 
                    'port': ARDUINO_PORT, 
                    'message': f'Arduino connected on {ARDUINO_PORT}'
                })
            except:
                # Port exists but not responsive
                return jsonify({
                    'connected': False, 
                    'port': ARDUINO_PORT, 
                    'message': 'Arduino port open but not responsive'
                })
        else:
            return jsonify({
                'connected': False, 
                'port': ARDUINO_PORT, 
                'message': 'Arduino not connected'
            })
    except Exception as e:
        return jsonify({
            'connected': False, 
            'port': ARDUINO_PORT, 
            'message': f'Error checking status: {str(e)}'
        })




if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)