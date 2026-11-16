#include <Adafruit_Fingerprint.h>

// Define serial communication pins for the fingerprint sensor
#if (defined(__AVR__) || defined(ESP8266)) && !defined(__AVR_ATmega2560__)
#include <SoftwareSerial.h>
SoftwareSerial mySerial(4, 0); // RX, TX
#else
#define mySerial Serial
#endif

Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

void setup()
{
  Serial.begin(9600); // Serial communication with the backend
  while (!Serial)
    ;

  mySerial.begin(57600); // Serial communication with the fingerprint sensor
  delay(100);

  // Initialize fingerprint sensor
  if (finger.verifyPassword())
  {
    Serial.println("Fingerprint sensor initialized.");
  }
  else
  {
    Serial.println("ERROR: Fingerprint sensor not detected. Check connections.");
    while (1)
      ; // Stop execution if the sensor is not found
  }
}

void loop()
{
  if (Serial.available())
  {
    // Read command from the backend
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "ENROLL")
    {
      enrollFingerprint(); // Handle enrollment
    }
    else if (command == "MATCH")
    {
      matchFingerprint(); // Handle matching
    }
  }
}

void enrollFingerprint()
{
  // Serial.println("ENROLL_START");

  int id = -1;
  // Wait for ID from the backend
  unsigned long startTime = millis();
  while (id <= 0)
  {
    // delay(1000);
    Serial.println("SEND_ID"); // Request an ID from the backend
    while (!Serial.available())
    {
      if (millis() - startTime > 10000)
      { // 5-second timeout
        Serial.println("ERROR: Timeout waiting for ID.");
        return;
      }
    }
    id = Serial.parseInt();
  }

  Serial.print("ENROLL_ID: ");
  Serial.println(id);

  // Enroll the fingerprint
  int p = enrollFinger(id);
  if (p == FINGERPRINT_OK)
  {
    Serial.println("ENROLL_SUCCESS");
  }
  else
  {
    Serial.println("ENROLL_FAILED");
  }
}

int enrollFinger(uint8_t id)
{
  int p = -1;
  Serial.println("Place finger on the sensor.");

  // Step 1: Capture the first fingerprint image
  while (p != FINGERPRINT_OK)
  {
    p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER)
      continue;
    if (p != FINGERPRINT_OK)
    {
      Serial.println("ERROR: Failed to capture image.");
      return p;
    }
  }
  p = finger.image2Tz(1); // Convert image to template
  if (p != FINGERPRINT_OK)
  {
    Serial.println("ERROR: Failed to process image.");
    return p;
  }

  // Step 2: Wait for the finger to be removed
  Serial.println("Remove finger.");
  delay(2000);
  while (p != FINGERPRINT_NOFINGER)
  {
    p = finger.getImage();
  }

  // Step 3: Capture the second fingerprint image
  Serial.println("Place the same finger again.");
  p = -1;
  while (p != FINGERPRINT_OK)
  {
    p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER)
      continue;
    if (p != FINGERPRINT_OK)
    {
      Serial.println("ERROR: Failed to capture second image.");
      return p;
    }
  }
  p = finger.image2Tz(2); // Convert second image to template
  if (p != FINGERPRINT_OK)
  {
    Serial.println("ERROR: Failed to process second image.");
    return p;
  }

  // Step 4: Create and store the model
  p = finger.createModel();
  if (p != FINGERPRINT_OK)
  {
    Serial.println("ERROR: Failed to create fingerprint model.");
    return p;
  }

  p = finger.storeModel(id);
  if (p == FINGERPRINT_OK)
  {
    Serial.println("Fingerprint stored successfully.");
  }
  else
  {
    Serial.println("ERROR: Failed to store fingerprint.");
  }
  return p;
}
void matchFingerprint()
{
  Serial.println("MATCH_RUNNING"); // Notify the backend that matching has started

  unsigned long startTime = millis();
  while (millis() - startTime < 30000)
  {
    uint8_t result = getFingerprintID(); // Call a helper function to handle the match logic
  }
}

uint8_t getFingerprintID()
{
  uint8_t p = finger.getImage();

  if (p == FINGERPRINT_NOFINGER)
  {
    Serial.println("No finger detected.");
    return FINGERPRINT_NOFINGER;
  }

  if (p != FINGERPRINT_OK)
  {
    Serial.println("Image capture failed.");
    return FINGERPRINT_IMAGEFAIL;
  }

  p = finger.image2Tz();
  if (p != FINGERPRINT_OK)
  {
    Serial.println("Feature extraction failed.");
    return FINGERPRINT_FEATUREFAIL;
  }

  p = finger.fingerSearch();
  if (p == FINGERPRINT_OK)
  {
    Serial.print("Match found! ID: ");
    Serial.println(finger.fingerID);
    // Serial.print("Confidence: ");
    // Serial.println(finger.confidence);
    return finger.fingerID; // Return the matched fingerprint ID
  }
  else if (p == FINGERPRINT_NOTFOUND)
  {
    Serial.println("No match found.");
    return FINGERPRINT_NOTFOUND;
  }
  else
  {
    Serial.println("Error occurred while searching.");
    return FINGERPRINT_PACKETRECIEVEERR;
  }
}