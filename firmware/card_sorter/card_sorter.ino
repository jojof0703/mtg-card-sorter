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
unsigned long lastServoTime[4] = {0, 0, 0, 0};

// ── Travel / motor timing ─────────────────────────────────────────────────────
const unsigned long TRAVEL_CREATURES  = 4350;
const unsigned long TRAVEL_LANDS      = 9500;
const unsigned long TRAVEL_PERMANENTS = 9500;
const unsigned long TRAVEL_SPELLS     = 4350;

// ── State machine ─────────────────────────────────────────────────────────────
enum State {
  IDLE,
  BELT_RUN,     // motor runs for full travel duration, then stops
  SERVO_A_UP,   // raise first servo
  SERVO_B_UP,   // raise second servo
  SERVOS_DOWN,  // lower both servos
  DONE_WAIT     // brief pause then send DONE
};

State currentState = IDLE;

int    *pPosA = nullptr; Servo *pServoA = nullptr; int targetUpA = 0;
int    *pPosB = nullptr; Servo *pServoB = nullptr; int targetUpB = 0;
int    restA  = 0, restB = 0;
unsigned long *pTimeA = nullptr, *pTimeB = nullptr;

unsigned long phaseStart  = 0;
unsigned long travelDelay = 0;

// ── Helpers ───────────────────────────────────────────────────────────────────
bool moveServo(int *pos, Servo &s, int target, int speed, unsigned long &lastTime) {
  if (millis() - lastTime >= 10) {
    if      (*pos < target) *pos = min(*pos + speed, target);
    else if (*pos > target) *pos = max(*pos - speed, target);
    s.write(*pos);
    lastTime = millis();
    return (*pos == target);
  }
  return false;
}

void runMotor() {
  myStepper.setSpeed(-600);
  myStepper.runSpeed(); 
}

void scheduleSort(int *posA, Servo &sA, int upA, int downA, unsigned long &tA,
                  int *posB, Servo &sB, int upB, int downB, unsigned long &tB,
                  unsigned long travel) {
  pPosA = posA;  pServoA = &sA;  targetUpA = upA;  restA = downA;  pTimeA = &tA;
  pPosB = posB;  pServoB = &sB;  targetUpB = upB;  restB = downB;  pTimeB = &tB;
  travelDelay  = travel;
  phaseStart   = millis();
  myStepper.enableOutputs();
  currentState = BELT_RUN;
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  myStepper.setMaxSpeed(1000.0);

  myStepper.disableOutputs();
  s1.attach(2); s2.attach(3); s3.attach(4); s4.attach(5);
  s1.write(LEFT_REST);  s2.write(LEFT_REST);
  s3.write(RIGHT_REST); s4.write(RIGHT_REST);
}

// ── Main loop ─────────────────────────────────────────────────────────────────
void loop() {

  // Only accept new commands when idle
  if (currentState == IDLE && Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "Creatures") {
      scheduleSort(&pos1, s1, LEFT_PUSHED,  LEFT_REST,  lastServoTime[0],
                   &pos4, s4, RIGHT_PUSHED, RIGHT_REST, lastServoTime[3],
                   TRAVEL_CREATURES);
    }
    else if (cmd == "Lands") {
      scheduleSort(&pos2, s2, LEFT_PUSHED,  LEFT_REST,  lastServoTime[1],
                   &pos3, s3, RIGHT_PUSHED, RIGHT_REST, lastServoTime[2],
                   TRAVEL_LANDS);
    }
    else if (cmd == "Permanents") {
      scheduleSort(&pos3, s3, RIGHT_PUSHED, RIGHT_REST, lastServoTime[2],
                   &pos2, s2, LEFT_PUSHED,  LEFT_REST,  lastServoTime[1],
                   TRAVEL_PERMANENTS);
    }
    else if (cmd == "Spells") {
      scheduleSort(&pos4, s4, RIGHT_PUSHED, RIGHT_REST, lastServoTime[3],
                   &pos1, s1, LEFT_PUSHED,  LEFT_REST,  lastServoTime[0],
                   TRAVEL_SPELLS);
    }
    else {
      // Default bin — card rides to the end on its own
      Serial.println("DONE");
    }
  }

  // ── State machine ────────────────────────────────────────────────────────
  switch (currentState) {

    case IDLE:
      myStepper.disableOutputs();
      break;

    // Belt runs for the full travel duration, then stops
    case BELT_RUN:
      runMotor();
      if (millis() - phaseStart >= travelDelay) {
        myStepper.disableOutputs();   // belt stops here
        currentState = SERVO_A_UP;
      }
      break;

    // Raise first servo, motor stays off
    case SERVO_A_UP:
      if (moveServo(pPosA, *pServoA, targetUpA, 1, *pTimeA))
        currentState = SERVO_B_UP;
      break;

    // Raise second servo, motor stays off
    case SERVO_B_UP:
      if (moveServo(pPosB, *pServoB, targetUpB, 1, *pTimeB))
        currentState = SERVOS_DOWN;
      break;

    // Lower both servos back to rest, motor stays off
    case SERVOS_DOWN: {
      bool dA = moveServo(pPosA, *pServoA, restA, 1, *pTimeA);
      bool dB = moveServo(pPosB, *pServoB, restB, 1, *pTimeB);
      if (dA && dB)
        currentState = DONE_WAIT;
      break;
    }

    // Small pause to let servos fully settle, then signal completion
    case DONE_WAIT:
      Serial.println("DONE");
      currentState = IDLE;
      break;
  }
}