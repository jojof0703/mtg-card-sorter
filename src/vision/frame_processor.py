sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import cv2
import time
from src.services import ScryfallClient
from src.pipeline import process_image

import numpy as np
import sys
import os


def frame_diff(a, b):
    if a is None or b is None:
        return 999

    a_gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    b_gray = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(a_gray, b_gray)
    return np.mean(diff)

class Camera:
    def __init__(self, index=1):
        self.cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
        self.cap.set(cv2.CAP_PROP_FOURCC,
                     cv2.VideoWriter_fourcc(*'MJPG'))

    def get_frame(self):
        ret, frame = self.cap.read()
        return frame if ret else None

    def release(self):
        self.cap.release()


def process_frame(frame, scryfall):
    return process_image(frame, scryfall)


def main():
    cam = Camera()
    scryfall = ScryfallClient()

    prev_frame = None
    threshold = 2.0

    stable = False
    stable_start = 0
    cooldown = 2
    last_ocr_time = 0

    last_result = None

    while True:
        frame = cam.get_frame()
        if frame is None:
            continue

        diff = frame_diff(frame, prev_frame)
        now = time.time()

        if diff < threshold:
            if not stable:
                stable = True
                stable_start = now

            if stable and (now - stable_start > 0.5):
                if now - last_ocr_time > cooldown:
                    record, err = process_frame(frame, scryfall)
                    last_ocr_time = now

                    if record:
                        last_result = record
                        print("CARD:", getattr(record, "name", record))
        else:
            stable = False
            stable_start = 0

        prev_frame = frame

        if last_result:
            cv2.putText(
                frame,
                getattr(last_result, "name", str(last_result)),
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

        cv2.imshow("camera", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()