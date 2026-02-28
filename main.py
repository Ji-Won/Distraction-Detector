import sys
import os
import time
import traceback
import math

# --- PYINSTALLER PATH FIX ---
# Check if we are running as a compiled .exe
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- LOGGING SETUP ---
log_path = os.path.join(BASE_DIR, "crash_log.txt")
sys.stdout = open(log_path, "w")
sys.stderr = open(log_path, "w")

def log(msg):
    print(msg)
    sys.stdout.flush()

# --- SAFE IMPORTS ---
try:
    log("Loading Libraries...")
    import cv2
    import mediapipe as mp
    import numpy as np
    import pygame
    import win32gui
    import win32con
except Exception:
    log("CRASH: Could not import libraries.")
    traceback.print_exc()
    sys.exit()

# --- HELPER: WINDOW CONTROL ---
def control_window(window_name, action):
    try:
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            if action == "ATTACK":
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            
            elif action == "RETREAT":
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception as e:
        log(f"Window control error: {e}")

# --- MAIN APP ---
try:
    # 1. Setup Audio
    pygame.mixer.init()
    sound_file = os.path.join(BASE_DIR, "toot.mp3")
    
    if os.path.exists(sound_file):
        toot_sound = pygame.mixer.Sound(sound_file)
    else:
        toot_sound = None

    # 2. Setup GIF
    gif_file = os.path.join(BASE_DIR, "skeleton.gif")
    gif_cap = None
    if os.path.exists(gif_file):
        gif_cap = cv2.VideoCapture(gif_file)

    # 3. Setup Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    # 4. Start Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): raise Exception("Camera failed to open")

    WINDOW_NAME = 'Distraction Detector'
    log("App Running...")
    
    # State Variables
    is_distracted = False
    distraction_direction = "NONE"
    focus_start_time = None 
    
    # --- METRICS COUNTERS ---
    count_left = 0
    count_right = 0
    count_down = 0
    start_time = time.time() # To track total session duration
    
    while cap.isOpened():
        success, image = cap.read()
        if not success: continue

        image = cv2.flip(image, 1)
        h, w, c = image.shape
        image.flags.writeable = False
        results = face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        image.flags.writeable = True

        current_frame_status = "Focused"
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                face_3d = []
                face_2d = []
                for idx, lm in enumerate(face_landmarks.landmark):
                    if idx in [33, 263, 1, 61, 291, 199]:
                        x, y = int(lm.x * w), int(lm.y * h)
                        face_2d.append([x, y])
                        face_3d.append([x, y, lm.z])
                
                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)
                focal_length = 1 * w
                cam_matrix = np.array([[focal_length, 0, h / 2], [0, focal_length, w / 2], [0, 0, 1]])
                dist_matrix = np.zeros((4, 1), dtype=np.float64)
                success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
                rmat, jac = cv2.Rodrigues(rot_vec)
                angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

                x_angle = angles[0] * 360
                y_angle = angles[1] * 360

                if y_angle < -10: 
                    current_frame_status = "Distracted"
                    distraction_direction = "LEFT"
                elif y_angle > 10: 
                    current_frame_status = "Distracted"
                    distraction_direction = "RIGHT"
                elif x_angle < -10: 
                    current_frame_status = "Distracted"
                    distraction_direction = "DOWN"

        # --- LOGIC LOOP ---
        if current_frame_status == "Distracted":
            focus_start_time = None
            if not is_distracted:
                # === NEW DISTRACTION EVENT DETECTED ===
                # This block only runs ONCE per distraction
                
                # 1. Update Tally
                if distraction_direction == "LEFT": count_left += 1
                elif distraction_direction == "RIGHT": count_right += 1
                elif distraction_direction == "DOWN": count_down += 1
                
                # 2. Trigger Punishment
                if toot_sound: toot_sound.play()
                control_window(WINDOW_NAME, "ATTACK")
                is_distracted = True
        else:
            if focus_start_time is None:
                focus_start_time = time.time()
            
            if is_distracted and (time.time() - focus_start_time > 0.35):
                 control_window(WINDOW_NAME, "RETREAT")
                 is_distracted = False
                 distraction_direction = "NONE"

        # --- DRAWING ---
        if is_distracted:
            pulse_alpha = (math.sin(time.time() * 10) + 1) / 2 * 0.6
            overlay = image.copy()
            overlay[:] = (0, 0, 255)
            cv2.addWeighted(overlay, pulse_alpha, image, 1 - pulse_alpha, 0, image)

            if gif_cap and gif_cap.isOpened():
                ret, gif_frame = gif_cap.read()
                if not ret: 
                    gif_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, gif_frame = gif_cap.read()
                
                if ret:
                    scale_size = 200
                    gif_frame = cv2.resize(gif_frame, (scale_size, scale_size))
                    
                    pos_x = w - scale_size - 10
                    pos_y = h - scale_size - 10
                    final_gif = gif_frame

                    if distraction_direction == "LEFT":
                        final_gif = cv2.flip(gif_frame, 1)
                        pos_x = w - scale_size - 20 
                    elif distraction_direction == "RIGHT":
                        final_gif = gif_frame
                        pos_x = 20
                    elif distraction_direction == "DOWN":
                        pos_x = int(w/2 - scale_size/2)
                    
                    rows, cols, channels = final_gif.shape
                    if pos_x >= 0 and pos_y >= 0 and (pos_x + cols) <= w and (pos_y + rows) <= h:
                        roi = image[pos_y:pos_y+rows, pos_x:pos_x+cols]
                        gray_gif = cv2.cvtColor(final_gif, cv2.COLOR_BGR2GRAY)
                        _, mask = cv2.threshold(gray_gif, 10, 255, cv2.THRESH_BINARY)
                        mask_inv = cv2.bitwise_not(mask)
                        img_bg = cv2.bitwise_and(roi, roi, mask=mask_inv)
                        gif_fg = cv2.bitwise_and(final_gif, final_gif, mask=mask)
                        dst = cv2.add(img_bg, gif_fg)
                        image[pos_y:pos_y+rows, pos_x:pos_x+cols] = dst
                    
            cv2.putText(image, "LOOK AT SCREEN!", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        cv2.imshow(WINDOW_NAME, image)

        key = cv2.waitKey(5) & 0xFF
        if key == ord('q'):
            break
        
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
        except: pass

    # --- SESSION ENDED: SHOW REPORT CARD ---
    cap.release()
    
    # Calculate Total Time
    session_minutes = int((time.time() - start_time) / 60)
    session_seconds = int((time.time() - start_time) % 60)
    total_distractions = count_left + count_right + count_down

    # Create a Black Image for the Report
    report_img = np.zeros((400, 600, 3), dtype='uint8')
    
    # Helper to center text
    def put_centered_text(img, text, y_pos, size, color):
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, size, 2)[0]
        text_x = (img.shape[1] - text_size[0]) // 2
        cv2.putText(img, text, (text_x, y_pos), cv2.FONT_HERSHEY_SIMPLEX, size, color, 2)

    # Draw the Report
    put_centered_text(report_img, "SESSION REPORT", 50, 1.0, (255, 255, 255))
    put_centered_text(report_img, f"Time: {session_minutes}m {session_seconds}s", 100, 0.7, (200, 200, 200))
    
    put_centered_text(report_img, f"Total Distractions: {total_distractions}", 160, 0.8, (0, 0, 255))
    
    put_centered_text(report_img, f"Looked Left: {count_left}", 220, 0.6, (100, 255, 100))
    put_centered_text(report_img, f"Looked Right: {count_right}", 260, 0.6, (100, 255, 100))
    put_centered_text(report_img, f"Looked Down: {count_down}", 300, 0.6, (100, 255, 100))
    
    put_centered_text(report_img, "Press 'Q' to Exit", 370, 0.5, (150, 150, 150))

    # Force Report Window to Top so you see it
    control_window(WINDOW_NAME, "ATTACK")
    
    # Show Report Loop
    while True:
        cv2.imshow(WINDOW_NAME, report_img)
        if cv2.waitKey(100) & 0xFF == ord('q'):
            break
        # Also check if window X is clicked
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
        except: break

    cv2.destroyAllWindows()

except Exception:
    log("!!! CRASH DETECTED !!!")
    traceback.print_exc()