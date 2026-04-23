import serial
import time
from src.config import SERIAL_PORT, SERIAL_BAUD
from src.sorting import sort_card_type

# int hardware connection
# The timeout=1 ensures the script doesn't hang forever if the Arduino is unplugged
ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
time.sleep(2)  # gives Arduino time to reset after the USB handshake

def process_and_sort(card_record):
    """
    Takes a single card, determines its bin, and tells Arduino to move.
    """
    # use from src/sorting.py
    # wrap the card in a list because sort_card_type expects a list
    result_dict = sort_card_type([card_record])
    
    # find which bucket the card landed in ("Creatures")
    # finds the first key that has a non-empty list
    category = next(key for key, val in result_dict.items() if val)

    print(f"Detected: {card_record.name} | Category: {category}")

    # comms w/ Arduino
    # send the category name + newline char
    ser.write(f"{category}\n".encode('utf-8'))

    # wait for Arduino to finish the physical movement
    print("Waiting for physical sort...")
    while True:
        # Use in_waiting to see if there is data in the buffer
        if ser.in_waiting > 0:
            response = ser.readline().decode('utf-8').strip()
            if response == "DONE":
                print("Bin clear! Ready for next card.")
                break

if __name__ == "__main__":
    # trigger the camera/OCR
    print("MTG Sorter Online...")
    # ex:process_and_sort(current_scanned_card)
