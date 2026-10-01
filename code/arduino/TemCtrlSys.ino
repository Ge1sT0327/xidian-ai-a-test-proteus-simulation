/* ============================================================
 *  Temperature Measurement & Control Simulation System
 *  Target : Arduino UNO (ATmega328P) @ 16 MHz
 *  Threshold = 30 + last digit of student ID (0) = 30.0 C
 *
 *  Hardware (fixed by the Proteus design):
 *    LCD1602 LM016L, 4-bit mode
 *      RS -> D12      EN -> D11
 *      D4 -> D5       D5 -> D4      D6 -> D3      D7 -> D2
 *      RW -> GND      VEE -> 5k pot (contrast)
 *    BMP180 temperature/pressure sensor on I2C
 *      SDA -> A4 (PC4)     SCL -> A5 (PC5)
 *    DC motor driver
 *      D7 -> 4.7k base resistor -> 2N3904 -> relay -> MOTOR-DC
 *    COMPIM serial link to PC: COM11 @ 9600 8-N-1
 *
 *  Behaviour:
 *    1) PC sends the student ID; the Arduino then streams temperature
 *    2) LCD line 1 shows "ID:20230000000", line 2 shows "TEMP:xx.xC"
 *    3) temp >  30.0 C -> D7 high, motor runs
 *       temp <= 30.0 C -> D7 low,  motor stops
 *
 *  NOTE: replace STUDENT_ID with your own full student number, and
 *        set TEMP_LIMIT = 30 + (the last digit of your student number).
 * ============================================================ */

#include <Wire.h>
#include <LiquidCrystal.h>

/* ---------------- configuration ---------------- */
#define STUDENT_ID   "20230000000"      /* <<< 换成你自己的完整学号 */
#define TEMP_LIMIT   30.0               /* <<< 30 + 你学号末位数 */
/* #define DEBUG_TEMP10 365 */   /* force 36.5 C for hardware-free tests */

/* ---------------- pins ---------------- */
#define MOTOR_PIN    7
#define LCD_RS       12
#define LCD_EN       11
#define LCD_D4       5
#define LCD_D5       4
#define LCD_D6       3
#define LCD_D7       2

/* ---------------- BMP180 registers ---------------- */
#define BMP180_ADDR  0x77
#define BMP180_ADDR2 0x76
#define REG_CALIB    0xAA
#define REG_CTRL     0xF4
#define REG_TEMPDATA 0xF6
#define CMD_TEMP     0x2E

LiquidCrystal lcd(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, LCD_D7);

/* ---------------- globals ---------------- */
uint8_t  bmpAddr = BMP180_ADDR;
int16_t  CAL_AC1, CAL_AC2, CAL_AC3, CAL_B1, CAL_B2, CAL_MB, CAL_MC, CAL_MD;
uint16_t CAL_AC4, CAL_AC5, CAL_AC6;
long     B5;

char    rxBuf[32];
uint8_t rxLen = 0;
bool    idReceived = false;
long    temp10     = 0;          /* temperature in 0.1 C steps */
bool    motorOn    = false;

unsigned long lastSample = 0;
unsigned long lastReport = 0;

/* ============================================================
 *  I2C helpers
 * ============================================================ */
void i2cWriteByte(uint8_t dev, uint8_t reg, uint8_t val)
{
  Wire.beginTransmission(dev);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

uint16_t i2cRead16(uint8_t dev, uint8_t reg)
{
  Wire.beginTransmission(dev);
  Wire.write(reg);
  Wire.endTransmission();
  Wire.requestFrom((uint8_t)dev, (uint8_t)2);
  uint16_t msb = 0, lsb = 0;
  if (Wire.available()) msb = Wire.read();
  if (Wire.available()) lsb = Wire.read();
  return (uint16_t)((msb << 8) | lsb);
}

/* Reliable presence test: write a scratch value into the control
 * register and read it back.  (Devices that only ACK still fail this.) */
bool i2cProbe(uint8_t dev)
{
  i2cWriteByte(dev, REG_CTRL, 0x00);
  uint16_t rb = i2cRead16(dev, REG_CTRL);
  return ((rb >> 8) == 0x00);          /* readback must match what we wrote */
}

/* ============================================================
 *  BMP180 calibration read
 * ============================================================ */
bool bmp180Init()
{
  uint8_t cand[2] = { BMP180_ADDR, BMP180_ADDR2 };
  bool ok = false;
  for (uint8_t i = 0; i < 2; i++) {
    if (i2cProbe(cand[i])) { bmpAddr = cand[i]; ok = true; break; }
  }
  if (!ok) return false;

  CAL_AC1 = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 0);
  CAL_AC2 = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 2);
  CAL_AC3 = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 4);
  CAL_AC4 =            i2cRead16(bmpAddr, REG_CALIB + 6);
  CAL_AC5 =            i2cRead16(bmpAddr, REG_CALIB + 8);
  CAL_AC6 =            i2cRead16(bmpAddr, REG_CALIB + 10);
  CAL_B1  = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 12);
  CAL_B2  = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 14);
  CAL_MB  = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 16);
  CAL_MC  = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 18);
  CAL_MD  = (int16_t) i2cRead16(bmpAddr, REG_CALIB + 20);

  if (CAL_AC5 == 0 || CAL_AC6 == 0) return false;
  return true;
}

/* ============================================================
 *  Temperature (BMP180 datasheet 4.3.1), result in 0.1 C steps
 * ============================================================ */
long bmp180ReadTemp10()
{
  i2cWriteByte(bmpAddr, REG_CTRL, CMD_TEMP);
  delay(5);                                   /* conversion takes 4.5 ms */

  uint16_t ut = i2cRead16(bmpAddr, REG_TEMPDATA);

  long X1 = ((long)ut - (long)CAL_AC6) * (long)CAL_AC5 >> 15;
  long X2 = ((long)CAL_MC << 11) / (X1 + (long)CAL_MD);
  B5 = X1 + X2;
  return (B5 + 8) >> 4;                       /* 0.1 C */
}

/* ============================================================
 *  LCD    (integer maths only - the AVR printf has no float support)
 * ============================================================ */
void updateLCD10(long t10)
{
  char sign = ' ';
  if (t10 < 0) { sign = '-'; t10 = -t10; }

  char line[17];
  snprintf(line, sizeof(line), "TEMP:%c%ld.%ldC", sign, t10 / 10, t10 % 10);

  lcd.setCursor(0, 0);
  lcd.print(F("                "));
  lcd.setCursor(0, 0);
  lcd.print(F("ID:"));
  lcd.print(STUDENT_ID);

  lcd.setCursor(0, 1);
  lcd.print(F("                "));
  lcd.setCursor(0, 1);
  lcd.print(line);
}

/* ============================================================
 *  Motor
 * ============================================================ */
void updateMotor10(long t10)
{
  if (t10 > (long)(TEMP_LIMIT * 10.0f)) {     /* > 30.0 C */
    digitalWrite(MOTOR_PIN, HIGH);
    motorOn = true;
  } else {
    digitalWrite(MOTOR_PIN, LOW);
    motorOn = false;
  }
}

/* ============================================================
 *  setup / loop
 * ============================================================ */
void setup()
{
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);

  Serial.begin(9600);

  lcd.begin(16, 2);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(F("Temperature Sys"));
  lcd.setCursor(0, 1);
  lcd.print(F("Waiting for ID.."));

  Wire.begin();
  delay(100);
  bmp180Init();
  delay(100);
}

void loop()
{
  /* ---------- 1. commands from the PC ---------- */
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxLen > 0) {
        rxBuf[rxLen] = '\0';
        idReceived = true;
        rxLen = 0;
      }
    } else {
      if (rxLen < sizeof(rxBuf) - 1) rxBuf[rxLen++] = c;
    }
  }

  unsigned long now = millis();

  /* ---------- 2. sample, display, drive motor every 200 ms ---------- */
  if (now - lastSample >= 200) {
    lastSample = now;

#ifdef DEBUG_TEMP10
    temp10 = DEBUG_TEMP10;
#else
    temp10 = bmp180ReadTemp10();
#endif
    if (temp10 < -400) temp10 = -400;         /* sensor range -40 .. +85 C */
    if (temp10 >  850) temp10 =  850;

    updateLCD10(temp10);
    updateMotor10(temp10);
  }

  /* ---------- 3. stream temperature to the PC once the ID arrived ---------- */
  if (idReceived && (now - lastReport >= 200)) {
    lastReport = now;
    long t = temp10;
    char sgn = ' ';
    if (t < 0) { sgn = '-'; t = -t; }
    Serial.print(F("TEMP:"));
    if (sgn == '-') Serial.print('-');
    Serial.print(t / 10);
    Serial.print('.');
    Serial.print(t % 10);
    Serial.println(F("C"));
  }
}
