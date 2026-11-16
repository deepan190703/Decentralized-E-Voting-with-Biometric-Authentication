# Decentralized E-Voting with Biometric Authentication

A secure, transparent, and tamper-proof electronic voting system built on blockchain technology with biometric authentication to ensure voter identity verification and prevent fraud.

## 🌟 Features

- **Blockchain-based Voting**: Immutable and transparent vote recording using Proof of Authority (PoA) consensus
- **Biometric Authentication**: Secure voter identity verification using R307 fingerprint sensor
- **Decentralized Network**: Multiple nodes ensuring system resilience
- **Real-time Results**: Instant vote tallying and result display
- **Voter Registration**: Secure voter enrollment system
- **Admin Dashboard**: Administrative controls and monitoring
- **Balance Query**: Voter account and transaction management

## 🏗️ System Architecture

The system consists of several interconnected components:

### Blockchain Network
- **Chain Nodes (n0, n1, n2, n3)**: Distributed blockchain nodes
- **Proof of Authority**: Consensus mechanism with validator nodes
- **P2P Network**: Peer-to-peer communication between nodes

### Biometric Authentication
- **R307 Fingerprint Sensor**: Hardware-based identity verification
- **Arduino Interface**: Microcontroller for sensor communication
- **Serial Communication**: Integration with voting system

### Web Applications
- **Admin Panel**: System administration and monitoring
- **Voter Registration**: Secure voter enrollment
- **Voting Interface**: User-friendly voting experience
- **Results Dashboard**: Real-time vote counting and display
- **Balance Query**: Account management system

## 🚀 Installation & Setup

### 1. Arduino R307 Fingerprint Sensor Setup

#### Hardware Requirements
- Arduino Uno/Nano
- R307 Fingerprint Sensor Module
- Jumper wires
- USB cable for Arduino

#### Wiring Connections
```
R307 Module    Arduino
VCC       ->   5V
GND       ->   GND
TXD       ->   Pin 2 (Digital)
RXD       ->   Pin 3 (Digital)
```

#### Arduino Code Setup
1. Open Arduino IDE
2. Copy the code from `Arduino/a.ino` file in the repository
3. Upload the code to your Arduino board
4. Open Serial Monitor at 9600 baud rate
5. Test sensor connection and functionality
6. Available commands: `ENROLL`, `MATCH`

### 2. Clone the Repository
```bash
git clone https://github.com/yourusername/Decentralized-E-Voting-with-Biometric-Authentication.git
cd Decentralized-E-Voting-with-Biometric-Authentication
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Blockchain Network

#### Node Configuration
Each node requires a configuration file. Example configurations are provided:

**Validator Node (PoA) - n0/config.json:**
```json
{
  "node_type": "PoA",
  "private_key": "your_private_key_here",
  "validator_keys": [
    "validator_key_1",
    "validator_key_2"
  ],
  "bootstrap_node": "http://localhost:8000",
  "known_peers": [
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003"
  ],
  "hop_limit": 4,
  "host": "0.0.0.0",
  "port": 8000
}
```

**Regular Node - n1/config1.json:**
```json
{
  "node_type": "normal",
  "private_key": "your_private_key_here",
  "validator_keys": [
    "validator_key_1",
    "validator_key_2"
  ],
  "bootstrap_node": "http://localhost:8000",
  "known_peers": [
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003"
  ],
  "hop_limit": 4,
  "host": "0.0.0.0",
  "port": 8001
}
```

### 5. Start the Blockchain Network

#### Start Individual Nodes
```bash
# Terminal 1 - Start bootstrap node (n0)
cd n0
python main.py

# Terminal 2 - Start node 1 (n1)
cd n1
python main1.py

# Terminal 3 - Start node 2 (n2)
cd n2
python main2.py

# Terminal 4 - Start node 3 (n3)
cd n3
python main3.py
```

#### Or use the convenience scripts
```bash
# Start all nodes
./startchain.sh

# Stop all nodes
./stopchain.sh
```

### 6. Generate Accounts
```bash
cd n3
python generate_accounts.py
```

### 7. Launch Web Applications

#### Admin Dashboard
```bash
cd combined_projects/admin
python app.py
```

#### Voter Registration
```bash
cd combined_projects/registration
python app.py
```

#### Voting System
```bash
cd combined_projects/voting
python app.py
```

#### Results Dashboard
```bash
cd combined_projects/result
python app.py
```

#### Balance Query
```bash
cd combined_projects/balance_qr
python app.py
```

## 🔧 Configuration

### Blockchain Settings
- **Consensus**: Proof of Authority (PoA)
- **Block Time**: Configurable
- **Network Ports**: 8000-8003 (default)
- **Hop Limit**: 4 (for message propagation)

### Biometric Authentication Settings
- **Sensor Model**: R307 Fingerprint Module
- **Communication**: Serial (57600 baud)
- **Storage**: Up to 1000 fingerprint templates
- **Arduino Serial**: 9600 baud for system communication

### Security Features
- **Private Key Management**: Secure key storage
- **Biometric Verification**: Hardware-based identity confirmation
- **Encrypted Communication**: Secure node communication
- **Tamper Detection**: Blockchain immutability ensures vote integrity

## 🧪 Testing

### Manual Transaction Testing
For creating and testing blockchain transactions manually via terminal:

```bash
# Create transactions manually through terminal interface
python Tx.py

# Generate test accounts first
python generate_accounts.py
```

### Biometric Testing
1. Connect Arduino with R307 sensor
2. Upload `Arduino/a.ino` code
3. Test fingerprint enrollment and verification
4. Integrate with voting system for authentication

## 📱 Web Interface Access

Once all components are running, access the system through:

- **Admin Dashboard**: http://localhost:5002
- **Voter Registration**: http://localhost:5001
- **Voting Interface**: http://localhost:5004
- **Results Dashboard**: http://localhost:5003
- **Balance Query**: http://localhost:5005

## 🔒 Security Considerations

- **Biometric Data**: Fingerprint templates are stored securely on the R307 module
- **Private Keys**: Never share or expose private keys
- **Network Security**: Use secure connections for production deployment
- **Voter Privacy**: Votes are anonymous while maintaining verification capability
- **System Integrity**: Blockchain ensures tamper-proof vote storage

## 🚨 Troubleshooting

### Arduino Issues
- Check wiring connections
- Verify baud rates (9600 for Serial, 57600 for fingerSerial)
- Ensure R307 sensor power supply is stable (5V)

### Blockchain Issues
- Verify all nodes are running and connected
- Check port availability (8000-8003)
- Ensure proper configuration files

### Web Application Issues
- Check if all required dependencies are installed
- Verify Flask applications are running on correct ports
- Ensure blockchain nodes are accessible

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📞 Support

For support and questions, please open an issue in the GitHub repository.
