#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);


int pinA = 12; 
int pinB = 11;
int pinC = 10;

const int DHT_Pin = 13;       
const int DHT_Type = DHT11;
const int B_Buz = 8;  

int melody[] = {
  1000, 500, 1000, 500, 1000, 500,   
  500, 1000, 500, 1000, 1500, 500, 
  1000, 500, 1000, 500, 1000         
};


int noteDuration = 300;  

DHT dht(DHT_Pin, DHT_Type);


void setup() {
    Serial.begin(9600);  
    dht.begin();

    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
      Serial.println("Помилка ініціалізації дисплея!");
      while (true);
    }

    display.clearDisplay();
    display.setTextSize(2);
    display.setTextColor(SSD1306_WHITE);

    display.setCursor(5,5);
    display.println("Begin");

    display.display();
    
    delay(2000);

    pinMode(pinA,OUTPUT);
    pinMode(pinB,OUTPUT);
    pinMode(pinC,OUTPUT);
    pinMode(B_Buz,OUTPUT);
}


void loop() {
  float Temperature = dht.readTemperature();
  float Humidity = dht.readHumidity();

  if (Serial.available()) {  // Перевіряємо, чи є команда
      String command = Serial.readStringUntil('\n');  // Зчитуємо команду
      command.trim();  // Прибираємо зайві пробіли

      if (command == "GET") {
          if (isnan(Temperature) || isnan(Humidity)) {
              Serial.println("ERROR");  
          } else {
              Serial.print(Temperature);
              Serial.print(" ");
              Serial.println(Humidity);
          }
      }
  }

  display.clearDisplay();
  display.setCursor(5,0);
 
    if (isnan(Temperature) || isnan(Humidity)) {
        display.println("Eror!");
    } else {
        display.fillRect(5, 16, SCREEN_WIDTH - 10, SCREEN_HEIGHT - 16, SSD1306_BLACK);
        display.println("Temp:");
        display.print(Temperature);
        display.println(" C");
        display.print("Humidity: ");
        display.print(Humidity);
        display.println(" %");
        
    }
    if(Temperature <18 || Humidity > 70 ){
      digitalWrite(pinC,HIGH);
      digitalWrite(pinA,LOW);
      digitalWrite(pinB,LOW);
      
    }
    else if(Temperature > 30 || Humidity < 35)
    {
      digitalWrite(pinA,HIGH);
      digitalWrite(pinB,LOW);
      digitalWrite(pinC,LOW);
      for (int i = 0; i < sizeof(melody) / sizeof(melody[0]); i++)
      {
       tone(B_Buz,melody[i]);
       delay(noteDuration);      
       noTone(B_Buz);                              
     }
 
      
    }
    else{
      digitalWrite(pinB,HIGH);
      digitalWrite(pinC,LOW);
      digitalWrite(pinA,LOW);
     
    }    
    display.display();
    delay(2000);
}
  