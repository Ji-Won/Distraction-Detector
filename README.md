# Distraction-Detector 💀🎺
A Python app that detects when you look away from your screen and shames you with a skeleton.

## Features
* **Real-time Head Tracking:** Uses Google's MediaPipe Face Mesh to calculate 3D head rotation.
* **Aggressive Interruption:** Uses Windows API to force itself to the top of your screen.
* **Smart Audio:** Only triggers once per distraction, with a focus-buffer to prevent glitching.
* **Session Report:** Tracks exactly how many times you looked away (left, right, or down).

## How to Run it Yourself
1. Clone or download this repository.
2. Install the required libraries:
   `pip install opencv-python mediapipe numpy pygame pywin32`
3. Run the script:
   `python main.py`
