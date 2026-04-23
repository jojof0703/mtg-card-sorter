#include <Servo.h>//to send signals to motors

//current .ino turns  arduino into a slave device that waits for orders from the python master script

Servo pusherServo;//create Servo object to control motor
const int PUSHER_PIN = 9;//tells arduino the signal wire pusher is plugged into Digital Pin 9
const int BELT_MOTOR_PIN = 10;//digital pin 10 to control belt movement

//angles for pushers
const int POS_RETRACTED = 0;  //for cards to pass
const int POS_PUSH      = 90; //extended for push

// timing (How long does it take for a card to get from the sensor to the bin)
// change the time based on measurements not sure what they exactly are so they need to be adjusted post testing
const int TRAVEL_TIME_CREATURES = 1500; //measured milliseconds
const int TRAVEL_TIME_LANDS     = 1500; 
const int TRAVEL_TIME_PERMANENTS= 3500;
const int TRAVEL_TIME_SPELLS    = 3500;

// Create 4 Servo objects
Servo pusher1, pusher2, pusher3, pusher4;

void setup() {//setup and attach each pusher and make them retracted
  Serial.begin(9600);
  
  //attach servos to pins 2, 3, 4, and 5
  pusher1.attach(2);
  pusher2.attach(3);
  pusher3.attach(4);
  pusher4.attach(5);

  //go to retracted position
  pusher1.write(POS_RETRACTED);
  pusher2.write(POS_RETRACTED);
  pusher3.write(POS_RETRACTED);
  pusher4.write(POS_RETRACTED);
}

void loop() {
  if (Serial.available() > 0) {//if cards available then if not loop nothing until then
    String binName = Serial.readStringUntil('\n');//grabs the text and stops once it sees the newline character that python sends at the end of the line
    binName.trim();//cleans up text removing any hidden spaces

    if (binName == "Creatures") {//if creatures
      delay(TRAVEL_TIME_CREATURES);
      triggerPusher(pusher1);
    } 
    else if (binName == "Lands") {//if lands
      delay(TRAVEL_TIME_LANDS);
      triggerPusher(pusher2);
    }
    else if (binName == "Permanents") {//if permanents
      delay(TRAVEL_TIME_PERMANENTS);
      triggerPusher(pusher3);
    }
    else if (binName == "Spells") {//if spells
      delay(TRAVEL_TIME_SPELLS);
      triggerPusher(pusher4);
    }
    else { // Everything else goes to the last bucket which is at the very end
    }

    Serial.println("DONE");
  }
}

void triggerPusher(Servo &s) {//helper function to fire a specific servo
  s.write(POS_PUSH);//tells the motor which one to swing out to the pushing position based on s
  delay(400);//delay 0.4 sec
  s.write(POS_RETRACTED);//retract
  delay(200);//delay 0.2 sec
}