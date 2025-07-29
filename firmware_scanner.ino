// === FIRMWARE – Scanner NIVA PRO v4.1 ===
// © 2025 – NIVA SRL  |  Compatto, task via lista comandi

/* ---------------- CONFIG ---------------- */
#define STEP_B 5
#define DIR_B  4
#define STEP_P 8
#define DIR_P  7
#define LIM_B_MIN 2
#define LIM_B_MAX 3
#define BAUDRATE 115200

#define STEPS_PER_DEG_B (164207.0 / 360.0)
#define STEPS_PER_DEG_P (164207.0 / 360.0)

#define SPEED_MIN_US 50
#define DEFAULT_SPEED_B 50
#define DEFAULT_SPEED_P 50
/* ---------------------------------------- */

/* ------------- VARIABILI --------------- */
float angleB = 0, angleP = 0;
uint16_t speedB_us = DEFAULT_SPEED_B, speedP_us = DEFAULT_SPEED_P;
bool swLimitB = true, hwLimitB = true, swLimitP = true;
volatile bool abortAll = false;

/* ---- TELEMETRIA OUTPUT ---- */
volatile bool isMoving = false;
String lastCommand = "";
/* ---------------------------------------- */

void pulse(uint8_t pin, uint16_t d){ digitalWrite(pin,1); delayMicroseconds(d); digitalWrite(pin,0); delayMicroseconds(d); }

void moveBraccio(float tgt){
  lastCommand = String("B=") + String(tgt,1);

  if(swLimitB && (tgt<0||tgt>90)){
    Serial.println(F("ERROR: B_OUT_OF_RANGE"));
    sendStatus();
    return;
  }
  long st = lround((tgt-angleB)*STEPS_PER_DEG_B);
  if(!st){
    Serial.println(F("INFO: NO_MOVE B"));
    sendStatus();
    return;
  }

  Serial.print(F("MOVE_START: ")); Serial.println(lastCommand);
  bool dir=st>0; digitalWrite(DIR_B,dir); st=abs(st); abortAll=false; isMoving=true;
  for(long i=0;i<st && !abortAll;i++){
    if(hwLimitB && (digitalRead(LIM_B_MIN) || digitalRead(LIM_B_MAX))){
      Serial.println(F("ERROR: HW_LIMIT_B"));
      break;
    }
    pulse(STEP_B,speedB_us);
    angleB+= (dir?1:-1)/STEPS_PER_DEG_B;
    if(!(i&0x1F)) handleSerial();          // check STOP
  }
  if(abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else { Serial.print(F("MOVE_DONE: ")); Serial.println(lastCommand); }
  isMoving=false;
  sendStatus();
}

void homingBraccio() {
  lastCommand = F("HOMING_B");
  Serial.println(F("HOMING: STARTED"));
  bool swBackup = swLimitB; swLimitB = false; abortAll = false; isMoving = true;
  const long ESCAPE_STEPS = lround(45.0f * STEPS_PER_DEG_B);
  const long RETURN_MAX_STEPS = lround(95.0f * STEPS_PER_DEG_B);
  bool hitMin = false;
  // Step A: Salita verso ~90°
  digitalWrite(DIR_B, true); // Verso 90°
  for (long i = 0; i < ESCAPE_STEPS && !abortAll; ++i) {
    if (hwLimitB && digitalRead(LIM_B_MAX)) {
      Serial.println(F("WARN: LIMIT_MAX_DURING_ASCENT"));
      break;
    }
    pulse(STEP_B, speedB_us);
    angleB += 1.0f / STEPS_PER_DEG_B;
    if (!(i & 0x1F)) handleSerial();
  }
  // Step B: Discesa verso finecorsa MIN
  digitalWrite(DIR_B, false); // Verso 0°
  for (long i = 0; i < RETURN_MAX_STEPS && !abortAll; ++i) {
    if (digitalRead(LIM_B_MIN)) { hitMin = true; break; }
    pulse(STEP_B, speedB_us);
    angleB -= 1.0f / STEPS_PER_DEG_B;
    if (!(i & 0x1F)) handleSerial();
  }
  if (abortAll) {
    Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  } else if (hitMin) {
    angleB = 0.0f;
    Serial.println(F("HOMING: DONE"));
  } else {
    Serial.println(F("HOMING: FAIL"));
  }
  swLimitB = swBackup; isMoving = false;
  sendStatus();
}

/* mode: 0 breve, 1 orario, -1 antiorario */
void movePiattaforma(float tgt,int mode){
  while(tgt<0) tgt+=360; while(tgt>=360) tgt-=360;
  lastCommand = String("P=") + String(tgt,1);
  if(swLimitP && (tgt<0||tgt>=360)){
    Serial.println(F("ERROR: P_OUT_OF_RANGE"));
    sendStatus();
    return;
  }

  float d;
  if(mode==0){                    // percorso breve
    d=tgt-angleP; if(d>180) d-=360; if(d<-180) d+=360;
  }else if(mode==1){              // orario
    d = (tgt>=angleP)? tgt-angleP : 360-angleP+tgt;
  }else{                          // antiorario
    d = (tgt<=angleP)? angleP-tgt : angleP+(360-tgt);
    d=-d;
  }
  long st=lround(d*STEPS_PER_DEG_P);
  if(!st){
    Serial.println(F("INFO: NO_MOVE P"));
    sendStatus();
    return;
  }
  Serial.print(F("MOVE_START: ")); Serial.println(lastCommand);
  bool dir=st>0; digitalWrite(DIR_P,dir); st=abs(st); abortAll=false; isMoving=true;
  for(long i=0;i<st && !abortAll;i++){
    pulse(STEP_P,speedP_us);
    angleP+= (dir?1:-1)/STEPS_PER_DEG_P;
    if(angleP<0) angleP+=360; else if(angleP>=360) angleP-=360;
    if(!(i&0x3F)) handleSerial();
  }
  if(abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else { Serial.print(F("MOVE_DONE: ")); Serial.println(lastCommand); }
  isMoving=false;
  sendStatus();
}

/* mode: 1 orario, -1 antiorario */
void movePiattaformaGiri(int numGiri, int mode){
  if(numGiri <= 0){
    Serial.println(F("ERROR: GIRO_INVALID"));
    sendStatus();
    return;
  }
  lastCommand = String(mode==1 ? "P_GIRO_OR=" : "P_GIRO_AN=") + String(numGiri);
  Serial.print(F("MOVE_START: ")); Serial.println(lastCommand);

  abortAll = false; isMoving = true;
  long stepsPerGiro = lround(360.0 * STEPS_PER_DEG_P);
  bool dir = (mode == 1); // true = orario, false = antiorario
  digitalWrite(DIR_P, dir);

  for(int giro = 0; giro < numGiri && !abortAll; giro++){
    for(long i = 0; i < stepsPerGiro && !abortAll; i++){
      pulse(STEP_P, speedP_us);
      angleP += (dir ? 1 : -1) / STEPS_PER_DEG_P;
      if(angleP < 0) angleP += 360; else if(angleP >= 360) angleP -= 360;
      if(!(i & 0x3F)) handleSerial(); // check STOP ogni 64 step
    }
  }
  if(abortAll) Serial.println(F("STOP: EMERGENCY_ACTIVE"));
  else { Serial.print(F("MOVE_DONE: ")); Serial.println(lastCommand); }
  isMoving=false;
  sendStatus();
}

void execCmd(String c){ c.trim();
  if(c.startsWith("B="))       moveBraccio(c.substring(2).toFloat());
  else if(c.startsWith("P="))  movePiattaforma(c.substring(2).toFloat(),0);
  else if(c.startsWith("P_OR=")) movePiattaforma(c.substring(5).toFloat(),1);
  else if(c.startsWith("P_AN=")) movePiattaforma(c.substring(5).toFloat(),-1);
  else if(c.startsWith("P_GIRO_OR=")) movePiattaformaGiri(c.substring(10).toInt(),1);
  else if(c.startsWith("P_GIRO_AN=")) movePiattaformaGiri(c.substring(10).toInt(),-1);
  else if(c=="RESET_POS"){ lastCommand="RESET_POS"; Serial.println(F("OK: RESET_POS")); moveBraccio(0); movePiattaforma(0,0); }
  else if(c=="HOMING_B"){ homingBraccio(); }
  else if(c.startsWith("SPEED_B=")){ speedB_us=max(SPEED_MIN_US,c.substring(8).toInt()); lastCommand="SPEED_B="+String(speedB_us); Serial.print(F("OK: SPEED_B ")); Serial.println(speedB_us); sendStatus(); }
  else if(c.startsWith("SPEED_P=")){ speedP_us=max(SPEED_MIN_US,c.substring(8).toInt()); lastCommand="SPEED_P="+String(speedP_us); Serial.print(F("OK: SPEED_P ")); Serial.println(speedP_us); sendStatus(); }
  else if(c=="SW_B_OFF"){ swLimitB=false; lastCommand="SW_B OFF"; Serial.println(F("OK: SW_B OFF")); sendStatus(); }
  else if(c=="SW_B_ON"){  swLimitB=true;  lastCommand="SW_B ON";  Serial.println(F("OK: SW_B ON"));  sendStatus(); }
  else if(c=="HW_B_OFF"){ hwLimitB=false; lastCommand="HW_B OFF"; Serial.println(F("OK: HW_B OFF")); sendStatus(); }
  else if(c=="HW_B_ON"){  hwLimitB=true;  lastCommand="HW_B ON";  Serial.println(F("OK: HW_B ON"));  sendStatus(); }
  else if(c=="SW_P_OFF"){ swLimitP=false; lastCommand="SW_P OFF"; Serial.println(F("OK: SW_P OFF")); sendStatus(); }
  else if(c=="SW_P_ON"){  swLimitP=true;  lastCommand="SW_P ON";  Serial.println(F("OK: SW_P ON"));  sendStatus(); }
  else if(c=="STOP"){ abortAll=true; lastCommand="STOP"; Serial.println(F("STOP: EMERGENCY")); sendStatus(); }
  else if(c=="STATUS"){ /* richiesta esplicita di status */ sendStatus(); }
  else { lastCommand=c; Serial.print(F("ERROR: CMD_UNKNOWN ")); Serial.println(c); sendStatus(); }
}

/* --- Parsing seriale --- */
void handleSerial(){
  while(Serial.available()){
    String l=Serial.readStringUntil('\n'); l.trim();
    if(l.startsWith("TASK=")){                    // sequenza X;Y;Z
      Serial.println(F("TASK: STARTED"));
      String seq=l.substring(5);
      int idx; while((idx=seq.indexOf(';'))!=-1){ execCmd(seq.substring(0,idx)); seq.remove(0,idx+1); }
      if(seq.length()) execCmd(seq);              // ultimo comando
      Serial.println(F("TASK: DONE"));
    }else execCmd(l);
  }
}

/* --- Serial helper --- */
void sendStatus(){
  // finecorsa attivi quando il pin è LOW
  bool minActive = (digitalRead(LIM_B_MIN) == LOW);
  bool maxActive = (digitalRead(LIM_B_MAX) == LOW);

  Serial.print(F("STATUS {"));
  Serial.print(F("\"angle_braccio\":"));           Serial.print(angleB,1);
  Serial.print(F(",\"angle_piattaforma\":"));      Serial.print(angleP,1);
  Serial.print(F(",\"speed_braccio_us\":"));       Serial.print(speedB_us);
  Serial.print(F(",\"speed_piattaforma_us\":"));   Serial.print(speedP_us);
  Serial.print(F(",\"finecorsa_min_braccio\":"));  Serial.print(minActive ? F("true") : F("false"));
  Serial.print(F(",\"finecorsa_max_braccio\":"));  Serial.print(maxActive ? F("true") : F("false"));
  Serial.print(F(",\"sw_limit_braccio\":"));       Serial.print(swLimitB ? F("true") : F("false"));
  Serial.print(F(",\"hw_limit_braccio\":"));       Serial.print(hwLimitB ? F("true") : F("false"));
  Serial.print(F(",\"sw_limit_piattaforma\":"));   Serial.print(swLimitP ? F("true") : F("false"));
  Serial.print(F(",\"is_moving\":"));              Serial.print(isMoving ? F("true") : F("false"));
  Serial.print(F(",\"last_command\":\""));         Serial.print(lastCommand); Serial.print(F("\"}"));
  Serial.println();
}

/* --- Arduino --- */
void setup(){
  Serial.begin(BAUDRATE);
  pinMode(STEP_B,OUTPUT); pinMode(DIR_B,OUTPUT);
  pinMode(STEP_P,OUTPUT); pinMode(DIR_P,OUTPUT);
  pinMode(LIM_B_MIN,INPUT_PULLUP); pinMode(LIM_B_MAX,INPUT_PULLUP);
  
  // Esegui homing automatico del braccio all'avvio
  homingBraccio();
  
  Serial.println(F("OK: READY"));
}
void loop(){ handleSerial(); }
