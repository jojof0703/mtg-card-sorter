#include <AccelStepper.h>
#include <Servo.h>

// ── Hardware ──────────────────────────────────────────────────────────────────
AccelStepper myStepper(AccelStepper::FULL4WIRE, 8, 9, 10, 11);
Servo s1, s2, s3, s4;

// ── Servo positions ───────────────────────────────────────────────────────────
const int LEFT_REST    = 30;
const int LEFT_PUSHED  = 200;
const int RIGHT_REST   = 150;
const int RIGHT_PUSHED = 0;

int pos1 = LEFT_REST,  pos2 = LEFT_REST;
int pos3 = RIGHT_REST, pos4 = RIGHT_REST;

  // Time gap so servos can only be moved every 10ms
unsigned long lastServoTime[4] = {0, 0, 0, 0};

// ── Travel / motor timing ─────────────────────────────────────────────────────
const unsigned long TRAVEL_CREATURES  = 4350;
const unsigned long TRAVEL_LANDS      = 9500;
const unsigned long TRAVEL_PERMANENTS = 9500;
const unsigned long TRAVEL_SPELLS     = 4350;

// ── Sort job globals ──────────────────────────────────────────────────────────
int targetUpA, restA, targetUpB, restB;
int idxA, idxB;

// ── State machine ─────────────────────────────────────────────────────────────
// Note: Had to google how to use a State Machine
// This site was quite helpful! 
// https://www.norwegiancreations.com/2017/03/state-machines-and-arduino-implementation/

enum State {
  IDLE,
  BELT_RUN,
  SERVO_A_UP,
  SERVO_B_UP,
  SERVOS_DOWN,
  DONE_WAIT
};

State currentState = IDLE;
unsigned long phaseStart  = 0;
unsigned long travelDelay = 0;

// ── Helpers ───────────────────────────────────────────────────────────────────
Servo& getServo(int idx) {
  switch (idx) {
    case 0: return s1;
    case 1: return s2;
    case 2: return s3;
    default: return s4;
  }
}

int& getPos(int idx) {
  switch (idx) {
    case 0: return pos1;
    case 1: return pos2;
    case 2: return pos3;
    default: return pos4;
  }
}

bool moveServo(int idx, int target, int speed) {
  // Called every loop 
  // Moves servo one speed variable towards target
  //  as long as 10ms have passed since last servo movement

  unsigned long &lastTime = lastServoTime[idx];
  int &pos = getPos(idx);
  if (millis() - lastTime >= 10) {
    if      (pos < target) pos = min(pos + speed, target); 
    else if (pos > target) pos = max(pos - speed, target); 
    getServo(idx).write(pos);
    lastTime = millis();
    return (pos == target);
  }
  return false;
}

void runMotor() {
  // -600 or else it spins backwards :).
  // Higher numbers were tried but it wouldn't work
  myStepper.setSpeed(-600); 
  myStepper.runSpeed();
}

void scheduleSort(int a, int upA, int downA,
                  int b, int upB, int downB,
                  unsigned long travel) {
  // Loads the sort into global variables
  // Enables motor
  // Starts state machine
  idxA = a;  targetUpA = upA;  restA = downA;
  idxB = b;  targetUpB = upB;  restB = downB;
  travelDelay = travel;
  phaseStart  = millis();
  myStepper.enableOutputs();
  currentState = BELT_RUN;
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  myStepper.setMaxSpeed(1000.0); // Needed for AccelStepper
  myStepper.disableOutputs(); 
  // Ensures motor starts as off since 5v isn't enough for both motor and servos
  s1.attach(2); s2.attach(3); s3.attach(4); s4.attach(5);
  s1.write(LEFT_REST);  s2.write(LEFT_REST);
  s3.write(RIGHT_REST); s4.write(RIGHT_REST);
}

// ── Main loop ─────────────────────────────────────────────────────────────────
void loop() {

  // Get input from python code
  // Only listens for commands when idle
  if (currentState == IDLE && Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "Creatures") {
      scheduleSort(0, LEFT_PUSHED,  LEFT_REST,
                   3, RIGHT_PUSHED, RIGHT_REST,
                   TRAVEL_CREATURES);
    }
    else if (cmd == "Lands") {
      scheduleSort(1, LEFT_PUSHED,  LEFT_REST,
                   2, RIGHT_PUSHED, RIGHT_REST,
                   TRAVEL_LANDS);
    }
    else if (cmd == "Permanents") {
      scheduleSort(2, RIGHT_PUSHED, RIGHT_REST,
                   1, LEFT_PUSHED,  LEFT_REST,
                   TRAVEL_PERMANENTS);
    }
    else if (cmd == "Spells") {
      scheduleSort(3, RIGHT_PUSHED, RIGHT_REST,
                   0, LEFT_PUSHED,  LEFT_REST,
                   TRAVEL_SPELLS);
    }
    else {
      Serial.println("DONE");
    }
  }

  switch (currentState) {
    // Handles state machine
    // State keeps running until its exit condition is met
    case IDLE:
      myStepper.disableOutputs();
      break;

    case BELT_RUN:
      runMotor();
      if (millis() - phaseStart >= travelDelay) {
        myStepper.disableOutputs();
        currentState = SERVO_A_UP;
      }
      break;

    case SERVO_A_UP:
      if (moveServo(idxA, targetUpA, 1))
        currentState = SERVO_B_UP;
      break;

    case SERVO_B_UP:
      if (moveServo(idxB, targetUpB, 1))
        currentState = SERVOS_DOWN;
      break;

    case SERVOS_DOWN: {
      bool dA = moveServo(idxA, restA, 1);
      bool dB = moveServo(idxB, restB, 1);
      if (dA && dB)
        currentState = DONE_WAIT;
      break;
    }

    case DONE_WAIT:
      Serial.println("DONE");
      currentState = IDLE;
      break;
  }
}