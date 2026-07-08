/*  ChipID.ino  --  make the screen IDENTIFY ITSELF over Serial.
 *
 *  Hand-clocks SPI slowly (mode 0). Sends a minimal init + SOLID RED, then
 *  reads back the controller's chip ID (RDDID 0x04) and prints it.
 *  This is the decisive test: the ID number tells us alive / clone / dead.
 *
 *  Pins: SCK=12 SDA=11 A0/DC=5 RESET=4 CS=10.  Serial @ 115200.
 */
#define CS 10
#define DC 5
#define RST 4
#define SCK 12
#define SDA 11

void wr8(uint8_t b){ for(int i=7;i>=0;i--){ digitalWrite(SCK,LOW); digitalWrite(SDA,(b>>i)&1); delayMicroseconds(5); digitalWrite(SCK,HIGH); delayMicroseconds(5);} }
void cmd(uint8_t c){ digitalWrite(DC,LOW);  digitalWrite(CS,LOW); wr8(c); digitalWrite(CS,HIGH); }
void dat(uint8_t d){ digitalWrite(DC,HIGH); digitalWrite(CS,LOW); wr8(d); digitalWrite(CS,HIGH); }

void readID(const char* label){
  digitalWrite(DC,LOW); digitalWrite(CS,LOW); wr8(0x04);   // RDDID command
  digitalWrite(DC,HIGH); pinMode(SDA, INPUT);              // release SDA, read back
  uint8_t id[4];
  for(int n=0;n<4;n++){ uint8_t v=0; for(int i=7;i>=0;i--){ digitalWrite(SCK,LOW); delayMicroseconds(5); digitalWrite(SCK,HIGH); delayMicroseconds(5); v=(v<<1)|digitalRead(SDA);} id[n]=v; }
  digitalWrite(CS,HIGH); pinMode(SDA, OUTPUT);
  Serial.printf(">>> %s RDID = %02X %02X %02X %02X\n", label, id[0],id[1],id[2],id[3]);
}

void setup(){
  Serial.begin(115200); delay(600); Serial.println();
  Serial.println("===== SCREEN CHIP-ID TEST =====");
  pinMode(CS,OUTPUT);pinMode(DC,OUTPUT);pinMode(RST,OUTPUT);pinMode(SCK,OUTPUT);pinMode(SDA,OUTPUT);
  digitalWrite(CS,HIGH); digitalWrite(SCK,LOW);
  digitalWrite(RST,HIGH); delay(80); digitalWrite(RST,LOW); delay(250); digitalWrite(RST,HIGH); delay(300);

  readID("after-reset (pre-init)");          // read ID before any init

  cmd(0x01); delay(150);            // SWRESET
  cmd(0x11); delay(255);            // SLPOUT
  cmd(0x3A); dat(0x05);             // COLMOD 16-bit 565
  cmd(0x36); dat(0xC0);             // MADCTL RGB
  cmd(0x20);                        // INVOFF
  cmd(0x29); delay(120);            // DISPON
  cmd(0x2A); dat(0x00);dat(0x00); dat(0x00);dat(0x7F);  // CASET 0..127
  cmd(0x2B); dat(0x00);dat(0x00); dat(0x00);dat(0x9F);  // RASET 0..159
  cmd(0x2C);                        // RAMWR
  digitalWrite(DC,HIGH); digitalWrite(CS,LOW);
  for(long i=0;i<128L*160L;i++){ wr8(0xF8); wr8(0x00); }  // SOLID RED
  digitalWrite(CS,HIGH);
  Serial.println(">>> Sent SOLID RED to the glass.");

  readID("after-init");                       // read ID again after init

  Serial.println("===== DONE. Send me the two RDID lines + what the screen shows. =====");
}
void loop(){}
