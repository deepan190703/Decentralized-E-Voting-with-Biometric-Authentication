from flask import Flask, render_template, request, jsonify
import cv2
import numpy as np
from pyzbar import pyzbar
import requests
import base64
import io
from PIL import Image
import json

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan_qr', methods=['POST'])
def scan_qr():
    try:
        # Get image data from request
        data = request.get_json()
        image_data = data['image'].split(',')[1]  # Remove data:image/jpeg;base64, prefix
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert PIL image to OpenCV format
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Decode QR codes
        qr_codes = pyzbar.decode(opencv_image)
        
        if qr_codes:
            # Get the first QR code data
            qr_data = qr_codes[0].data.decode('utf-8')
            
            # Extract public key from QR data
            # Assuming QR contains the public key directly or in a specific format
            public_key = qr_data.strip()
            
            # Fetch balance from API
            balance_url = f"http://127.0.0.1:8000/balance?address={public_key}"
            
            try:
                response = requests.get(balance_url, timeout=10)
                if response.status_code == 200:
                    balance_data = response.json()
                    return jsonify({
                        'success': True,
                        'public_key': public_key,
                        'balance_data': balance_data,
                        'qr_data': qr_data
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'API request failed with status {response.status_code}'
                    })
            except requests.exceptions.RequestException as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to fetch balance: {str(e)}'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'No QR code found in image'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error processing image: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True, port=5005)