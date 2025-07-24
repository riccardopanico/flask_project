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

#define STEPS_PER_DEG_B 50.0
#define STEPS_PER_DEG_P (164207.0 / 360.0)

#define SPEED_MIN_US 50
#define DEFAULT_SPEED_B 300
#define DEFAULT_SPEED_P 300
/* ---------------------------------------- */

/* ------------- VARIABILI --------------- */
float angleB = 0, angleP = 0;
uint16_t speedB_us = DEFAULT_SPEED_B, speedP_us = DEFAULT_SPEED_P;
bool swLimitB = true, hwLimitB = true, swLimitP = true;
volatile bool abortAll = false;
/* ---------------------------------------- */

void pulse(uint8_t pin, uint16_t d){ digitalWrite(pin,1); delayMicroseconds(d); digitalWrite(pin,0); delayMicroseconds(d); }

void moveBraccio(float tgt){
  if(swLimitB && (tgt<0||tgt>90)){ Serial.println(F("ERR_B_OUT")); return; }
  long st = round((tgt-angleB)*STEPS_PER_DEG_B); if(!st){ Serial.println(F("NO_MOVE_B")); return; }
  bool dir=st>0; digitalWrite(DIR_B,dir); st=abs(st); abortAll=false;
  for(long i=0;i<st && !abortAll;i++){
    if(hwLimitB){
      if(dir && !digitalRead(LIM_B_MAX)){ Serial.println(F("HW_MAX_B")); break; }
      if(!dir && !digitalRead(LIM_B_MIN)){ Serial.println(F("HW_MIN_B")); break; }
    }
    pulse(STEP_B,speedB_us);
    angleB+= (dir?1:-1)/STEPS_PER_DEG_B;
    if(!(i&0x1F)) handleSerial();          // check STOP
  }
  sendStatus();
}

/* mode: 0 breve, 1 orario, -1 antiorario */
void movePiattaforma(float tgt,int mode){
  while(tgt<0) tgt+=360; while(tgt>=360) tgt-=360;
  if(swLimitP && (tgt<0||tgt>=360)){ Serial.println(F("ERR_P_OUT")); return; }

  float d;
  if(mode==0){                    // percorso breve
    d=tgt-angleP; if(d>180) d-=360; if(d<-180) d+=360;
  }else if(mode==1){              // orario
    d = (tgt>=angleP)? tgt-angleP : 360-angleP+tgt;
  }else{                          // antiorario
    d = (tgt<=angleP)? angleP-tgt : angleP+(360-tgt);
    d=-d;
  }
  long st=round(d*STEPS_PER_DEG_P); if(!st){ Serial.println(F("NO_MOVE_P")); return; }
  bool dir=st>0; digitalWrite(DIR_P,dir); st=abs(st); abortAll=false;
  for(long i=0;i<st && !abortAll;i++){
    pulse(STEP_P,speedP_us);
    angleP+= (dir?1:-1)/STEPS_PER_DEG_P;
    if(angleP<0) angleP+=360; else if(angleP>=360) angleP-=360;
    if(!(i&0x3F)) handleSerial();
  }
  sendStatus();
}

void execCmd(String c){ c.trim();
  if(c.startsWith("B="))       moveBraccio(c.substring(2).toFloat());
  else if(c.startsWith("P="))  movePiattaforma(c.substring(2).toFloat(),0);
  else if(c.startsWith("P_OR=")) movePiattaforma(c.substring(5).toFloat(),1);
  else if(c.startsWith("P_AN=")) movePiattaforma(c.substring(5).toFloat(),-1);
  else if(c=="RESET_POS"){ moveBraccio(0); movePiattaforma(0,0); }
  else if(c.startsWith("SPEED_B=")){ speedB_us=max(SPEED_MIN_US,c.substring(8).toInt()); }
  else if(c.startsWith("SPEED_P=")){ speedP_us=max(SPEED_MIN_US,c.substring(8).toInt()); }
  else if(c=="SW_B_OFF"){ swLimitB=false; }  else if(c=="SW_B_ON"){ swLimitB=true; }
  else if(c=="HW_B_OFF"){ hwLimitB=false; }  else if(c=="HW_B_ON"){ hwLimitB=true; }
  else if(c=="SW_P_OFF"){ swLimitP=false; }  else if(c=="SW_P_ON"){ swLimitP=true; }
  else if(c=="STOP"){ abortAll=true; }
  else if(c=="STATUS"){ sendStatus(); }
  else Serial.print(F("ERR_CMD=")),Serial.println(c);
}

/* --- Parsing seriale --- */
void handleSerial(){
  while(Serial.available()){
    String l=Serial.readStringUntil('\n'); l.trim();
    if(l.startsWith("TASK=")){                    // sequenza X;Y;Z
      String seq=l.substring(5);
      int idx; while((idx=seq.indexOf(';'))!=-1){ execCmd(seq.substring(0,idx)); seq.remove(0,idx+1); }
      if(seq.length()) execCmd(seq);              // ultimo comando
    }else execCmd(l);
  }
}

/* --- Serial helper --- */
void sendStatus(){
  Serial.print(F("STATUS_B=")); Serial.print(angleB,1);
  Serial.print(F(";P="));       Serial.print(angleP,1);
  Serial.println();
}

/* --- Arduino --- */
void setup(){
  Serial.begin(BAUDRATE);
  pinMode(STEP_B,OUTPUT); pinMode(DIR_B,OUTPUT);
  pinMode(STEP_P,OUTPUT); pinMode(DIR_P,OUTPUT);
  pinMode(LIM_B_MIN,INPUT_PULLUP); pinMode(LIM_B_MAX,INPUT_PULLUP);
  Serial.println(F("READY"));
}
void loop(){ handleSerial(); }
