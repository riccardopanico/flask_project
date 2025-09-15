// === FIRMWARE – Scanner NIVA PRO v4.1 ===
// © 2025 – NIVA SRL | Compatto, task via lista comandi

/* ---------------- CONFIG ---------------- */
#define STEP_B         5
#define DIR_B          4
#define STEP_P         8
#define DIR_P          7
#define LIM_B_MIN      2
#define LIM_B_MAX      3
#define BAUDRATE       115200

#define STEPS_PER_DEG_B (164207.0f / 360.0f)
#define STEPS_PER_DEG_P (164207.0f / 360.0f)

#define SPEED_MIN_US     50
#define DEFAULT_SPEED_B  50
#define DEFAULT_SPEED_P  50
#define RAMP_STEPS_B     3000    // step rampa braccio
#define RAMP_STEPS_P     3000    // step rampa piattaforma
/* ---------------------------------------- */

/* ------------- VARIABILI --------------- */
static float    angleB = 0.0f;
static float    angleP = 0.0f;
static uint16_t speedB_us = DEFAULT_SPEED_B;
static uint16_t speedP_us = DEFAULT_SPEED_P;
static bool     swLimitB = true;
static bool     hwLimitB = true;
static bool     swLimitP = true;
static volatile bool abortAll = false;
static volatile bool isMoving = false;
static unsigned int movementDelay = 0;
static String   lastCommand;
/* ---------------------------------------- */

inline void pulse(uint8_t pin, uint16_t delayUs) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(delayUs);
  digitalWrite(pin, LOW);
  delayMicroseconds(delayUs);
}

// Funzione unificata per calcolo rampa
uint16_t calculateRampDelay(long currentStep, long totalSteps, long rampSteps, long decelStartStep, uint16_t targetSpeed) {
  uint16_t startDelay = targetSpeed * 4;
  
  if (currentStep < rampSteps) {
    // Zona A: Accelerazione
    return startDelay - ((startDelay - targetSpeed) * currentStep / rampSteps);
  } else if (currentStep >= decelStartStep) {
    // Zona C: Decelerazione
    long decStep = currentStep - decelStartStep;
    long decRamp = totalSteps - decelStartStep;
    return targetSpeed + ((startDelay - targetSpeed) * decStep / decRamp);
  } else {
    // Zona B: Crociera
    return targetSpeed;
  }
}

void moveBraccio(float tgt) {
  lastCommand = "B=" + String(tgt, 1);

  if (swLimitB && (tgt < 0.0f || tgt > 90.0f)) {
    Serial.println(F("ERROR: B_OUT_OF_RANGE"));
    sendStatus();
    return;
  }

  long steps = lround((tgt - angleB) * STEPS_PER_DEG_B);
  if (steps == 0) {
    Serial.println(F("INFO: NO_MOVE B"));
    sendStatus();
    return;
  }

  Serial.print(F("MOVE_START: ")); Serial.println(lastCommand);

  bool dirUp = (steps > 0);                 // TRUE → verso 90°, FALSE → verso 0°
  digitalWrite(DIR_B, dirUp);
  steps = abs(steps);
  abortAll = false;
  isMoving = true;

  // Calcola zone rampa correttamente
  long ramp = (steps < RAMP_STEPS_B * 2) ? steps / 2 : RAMP_STEPS_B;

  // Calcola quando iniziare decelerazione in base alla posizione angolare
  float rampDegrees = (float)ramp / STEPS_PER_DEG_B;
  float decelStartAngle = tgt - rampDegrees;
  long decelStartStep = (angleB + rampDegrees < decelStartAngle) ? 
                        lround((decelStartAngle - angleB) * STEPS_PER_DEG_B) : 
                        steps - ramp;

  for (long i = 0; i < steps && !abortAll; ++i) {
    // ------ FIX: controlla solo il fine-corsa pertinente al verso ------
    if (hwLimitB) {
      if (dirUp) {
        // Salita: interessa solo LIM_B_MAX
        if (digitalRead(LIM_B_MAX)) {
          Serial.println(F("ERROR: HW_LIMIT_B"));
          break;
        }
      } else {
        // Discesa: interessa solo LIM_B_MIN
        if (digitalRead(LIM_B_MIN)) {
          Serial.println(F("ERROR: HW_LIMIT_B"));
          break;
        }
      }
    }
    //-------------------------------------------------------------------
    
    // Calcola delay rampa
    uint16_t currentDelay = calculateRampDelay(i, steps, ramp, decelStartStep, speedB_us);
    pulse(STEP_B, currentDelay);
    angleB += (dirUp ? 1.0f : -1.0f) / STEPS_PER_DEG_B;
    if ((i & 0x1F) == 0) handleSerial();
  }

  if (abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else {
    Serial.print(F("MOVE_DONE: ")); Serial.println(lastCommand);
  }
  isMoving = false;
  sendStatus();
}

void homingBraccio() {
  lastCommand = F("HOMING_B");
  Serial.println(F("HOMING: STARTED"));
  bool swBak = swLimitB;
  swLimitB = false;
  abortAll = false;
  isMoving = true;

  const long ESCAPE_STEPS  = lround(2.0f * STEPS_PER_DEG_B);
  const long RETURN_STEPS  = lround(95.0f * STEPS_PER_DEG_B);
  bool hitMin = false;

  // Salita verso ~90° (libera eventuale LIM_B_MIN premuto)
  digitalWrite(DIR_B, HIGH);
  
  // Calcola rampa per movimento di escape
  long escapeRamp = (ESCAPE_STEPS < RAMP_STEPS_B * 2) ? ESCAPE_STEPS / 2 : RAMP_STEPS_B;
  
  for (long i = 0; i < ESCAPE_STEPS && !abortAll; ++i) {
    if (hwLimitB && digitalRead(LIM_B_MAX)) {
      Serial.println(F("WARN: LIMIT_MAX_DURING_ASCENT"));
      break;
    }
    
    // Calcola delay rampa escape
    uint16_t currentDelay = calculateRampDelay(i, ESCAPE_STEPS, escapeRamp, ESCAPE_STEPS - escapeRamp, speedB_us);
    pulse(STEP_B, currentDelay);
    angleB += 1.0f / STEPS_PER_DEG_B;
    if ((i & 0x1F) == 0) handleSerial();
  }

  // Discesa verso finecorsa MIN
  digitalWrite(DIR_B, LOW);
  
  // Calcola rampa per movimento di ritorno
  long returnRamp = (RETURN_STEPS < RAMP_STEPS_B * 2) ? RETURN_STEPS / 2 : RAMP_STEPS_B;
  
  for (long i = 0; i < RETURN_STEPS && !abortAll; ++i) {
    if (digitalRead(LIM_B_MIN)) {
      hitMin = true;
      break;
    }
    
    // Calcola delay rampa return
    uint16_t currentDelay = calculateRampDelay(i, RETURN_STEPS, returnRamp, RETURN_STEPS - returnRamp, speedB_us);
    pulse(STEP_B, currentDelay);
    angleB -= 1.0f / STEPS_PER_DEG_B;
    if ((i & 0x1F) == 0) handleSerial();
  }

  if (abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else if (hitMin) {
    angleB = 0.0f;
    Serial.println(F("HOMING: DONE"));
  } else {
    Serial.println(F("HOMING: FAIL"));
  }

  swLimitB = swBak;
  isMoving = false;
  sendStatus();
}

void movePiattaforma(float tgt, int mode) {
  while (tgt < 0.0f) tgt += 360.0f;
  while (tgt >= 360.0f) tgt -= 360.0f;
  lastCommand = "P=" + String(tgt, 1);

  if (swLimitP && (tgt < 0.0f || tgt >= 360.0f)) {
    Serial.println(F("ERROR: P_OUT_OF_RANGE"));
    sendStatus();
    return;
  }

  float d;
  if (mode == 0) {
    d = tgt - angleP;
    if (d > 180.0f) d -= 360.0f;
    else if (d < -180.0f) d += 360.0f;
  } else if (mode > 0) {
    d = (tgt >= angleP) ? (tgt - angleP) : (360.0f - angleP + tgt);
  } else {
    d = (tgt <= angleP) ? (angleP - tgt) : (angleP + (360.0f - tgt));
    d = -d;
  }

  long steps = lround(d * STEPS_PER_DEG_P);
  if (steps == 0) {
    Serial.println(F("INFO: NO_MOVE P"));
    sendStatus();
    return;
  }

  Serial.print(F("MOVE_START: ")); Serial.println(lastCommand);
  bool dir = (steps > 0);
  digitalWrite(DIR_P, dir);
  steps = abs(steps);
  abortAll = false;
  isMoving = true;

  // Calcola zone rampa correttamente
  long ramp = (steps < RAMP_STEPS_P * 2) ? steps / 2 : RAMP_STEPS_P;

  // Calcola quando iniziare decelerazione in base alla posizione angolare
  float rampDegrees = (float)ramp / STEPS_PER_DEG_P;
  float decelStartAngle = tgt - rampDegrees;
  long decelStartStep = (angleP + rampDegrees < decelStartAngle) ? 
                        lround((decelStartAngle - angleP) * STEPS_PER_DEG_P) : 
                        steps - ramp;

  for (long i = 0; i < steps && !abortAll; ++i) {
    // Calcola delay rampa
    uint16_t currentDelay = calculateRampDelay(i, steps, ramp, decelStartStep, speedP_us);
    pulse(STEP_P, currentDelay);
    angleP += (dir ? 1.0f : -1.0f) / STEPS_PER_DEG_P;
    if (angleP < 0.0f) angleP += 360.0f;
    else if (angleP >= 360.0f) angleP -= 360.0f;
    if ((i & 0x3F) == 0) handleSerial();
  }

  if (abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else {
    Serial.print(F("MOVE_DONE: ")); Serial.println(lastCommand);
  }
  isMoving = false;
  sendStatus();
}

void movePiattaformaGiri(int numGiri, int mode, const String& cmd) {
  if (numGiri <= 0) {
    Serial.println(F("ERROR: GIRO_INVALID"));
    sendStatus();
    return;
  }
  lastCommand = cmd;
  Serial.print(F("MOVE_START: ")); Serial.println(lastCommand);
  abortAll = false;
  isMoving = true;

  long stepsPerGiro = lround(360.0f * STEPS_PER_DEG_P);
  bool dir = (mode > 0);
  digitalWrite(DIR_P, dir);

  for (int g = 0; g < numGiri && !abortAll; ++g) {
    for (long i = 0; i < stepsPerGiro && !abortAll; ++i) {
      pulse(STEP_P, speedP_us);
      angleP += (dir ? 1.0f : -1.0f) / STEPS_PER_DEG_P;
      if (angleP < 0.0f) angleP += 360.0f;
      else if (angleP >= 360.0f) angleP -= 360.0f;
      if ((i & 0x3F) == 0) handleSerial();
    }
  }

  if (abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else {
    Serial.print(F("MOVE_DONE: ")); Serial.println(lastCommand);
  }
  isMoving = false;
  sendStatus();
}

void execCmd(String c) {
  c.trim();
  if      (c.startsWith("B="))      moveBraccio(c.substring(2).toFloat());
  else if (c.startsWith("P="))      movePiattaforma(c.substring(2).toFloat(), 0);
  else if (c.startsWith("P_OR="))   {
    float a = c.substring(5).toFloat();
    int  g = (int)(a / 360.0f);
    float r = a - g * 360.0f;
    if (g > 0) movePiattaformaGiri(g,  1, c);
    if (r > 0 || g == 0) movePiattaforma(r, 1);
  } else if (c.startsWith("P_AN=")) {
    float a = c.substring(5).toFloat();
    int  g = (int)(a / 360.0f);
    float r = a - g * 360.0f;
    if (g > 0) movePiattaformaGiri(g, -1, c);
    if (r > 0 || g == 0) movePiattaforma(r,-1);
  } else if (c.startsWith("RESET_POS")) {
    lastCommand = "RESET_POS";
    Serial.println(F("OK: RESET_POS"));
    moveBraccio(0.0f);
    movePiattaforma(0.0f, 0);
  } else if (c.startsWith("HOMING_B")) {
    homingBraccio();
  } else if (c.startsWith("SPEED_B=")) {
    speedB_us = max(SPEED_MIN_US, c.substring(8).toInt());
    lastCommand = "SPEED_B=" + String(speedB_us);
    Serial.print(F("OK: SPEED_B ")); Serial.println(speedB_us);
    sendStatus();
  } else if (c.startsWith("SPEED_P=")) {
    speedP_us = max(SPEED_MIN_US, c.substring(8).toInt());
    lastCommand = "SPEED_P=" + String(speedP_us);
    Serial.print(F("OK: SPEED_P ")); Serial.println(speedP_us);
    sendStatus();
  } else if (c.startsWith("MOVE_DELAY=")) {
    movementDelay = max(0, c.substring(11).toInt());
    lastCommand = "MOVE_DELAY=" + String(movementDelay);
    Serial.print(F("OK: MOVE_DELAY ")); Serial.println(movementDelay);
    sendStatus();
  } else if (c == "SW_B_OFF") {
    swLimitB = false;
    lastCommand = "SW_B OFF";
    Serial.println(F("OK: SW_B OFF"));
    sendStatus();
  } else if (c == "SW_B_ON") {
    swLimitB = true;
    lastCommand = "SW_B ON";
    Serial.println(F("OK: SW_B ON"));
    sendStatus();
  } else if (c == "HW_B_OFF") {
    hwLimitB = false;
    lastCommand = "HW_B OFF";
    Serial.println(F("OK: HW_B OFF"));
    sendStatus();
  } else if (c == "HW_B_ON") {
    hwLimitB = true;
    lastCommand = "HW_B ON";
    Serial.println(F("OK: HW_B ON"));
    sendStatus();
  } else if (c == "SW_P_OFF") {
    swLimitP = false;
    lastCommand = "SW_P OFF";
    Serial.println(F("OK: SW_P OFF"));
    sendStatus();
  } else if (c == "SW_P_ON") {
    swLimitP = true;
    lastCommand = "SW_P ON";
    Serial.println(F("OK: SW_P ON"));
    sendStatus();
  } else if (c == "STOP") {
    abortAll = true;
    isMoving = false;
    lastCommand = "STOP";
    Serial.println(F("STOP: EMERGENCY"));
    sendStatus();
  } else if (c == "STATUS") {
    sendStatus();
  } else {
    lastCommand = c;
    Serial.print(F("ERROR: CMD_UNKNOWN ")); Serial.println(c);
    sendStatus();
  }
}

void handleSerial() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.startsWith("TASK=")) {
      Serial.println(F("TASK: STARTED"));
      String seq = line.substring(5);
      int idx;
      while ((idx = seq.indexOf(';')) != -1) {
        execCmd(seq.substring(0, idx));
        if (movementDelay) delay(movementDelay);
        seq.remove(0, idx + 1);
      }
      if (seq.length()) execCmd(seq);
      Serial.println(F("TASK: DONE"));
    } else {
      execCmd(line);
    }
  }
}

void sendStatus() {
  bool minActive = (digitalRead(LIM_B_MIN) == LOW);
  bool maxActive = (digitalRead(LIM_B_MAX) == LOW);
  Serial.print(F("STATUS {"));
  Serial.print(F("\"angle_braccio\":")); Serial.print(angleB, 1);
  Serial.print(F(",\"angle_piattaforma\":")); Serial.print(angleP, 1);
  Serial.print(F(",\"speed_braccio_us\":")); Serial.print(speedB_us);
  Serial.print(F(",\"speed_piattaforma_us\":")); Serial.print(speedP_us);
  Serial.print(F(",\"finecorsa_min_braccio\":")); Serial.print(minActive ? F("true") : F("false"));
  Serial.print(F(",\"finecorsa_max_braccio\":")); Serial.print(maxActive ? F("true") : F("false"));
  Serial.print(F(",\"sw_limit_braccio\":")); Serial.print(swLimitB ? F("true") : F("false"));
  Serial.print(F(",\"hw_limit_braccio\":")); Serial.print(hwLimitB ? F("true") : F("false"));
  Serial.print(F(",\"sw_limit_piattaforma\":")); Serial.print(swLimitP ? F("true") : F("false"));
  Serial.print(F(",\"is_moving\":")); Serial.print(isMoving ? F("true") : F("false"));
  Serial.print(F(",\"last_command\":")); Serial.print(F("\"")); Serial.print(lastCommand); Serial.print(F("\"}"));
  Serial.println();
}

void setup() {
  Serial.begin(BAUDRATE);
  pinMode(STEP_B, OUTPUT);
  pinMode(DIR_B, OUTPUT);
  pinMode(STEP_P, OUTPUT);
  pinMode(DIR_P, OUTPUT);
  pinMode(LIM_B_MIN, INPUT_PULLUP);
  pinMode(LIM_B_MAX, INPUT_PULLUP);
  // homingBraccio();
  Serial.println(F("OK: READY"));
}

void loop() {
  handleSerial();
}
