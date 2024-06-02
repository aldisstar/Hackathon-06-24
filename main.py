import re
import cv2
import simplelpr
import matplotlib.colors as mcolors
import pyttsx3
from api import PlateDatabase
import time
import threading

video_stream_id = 0
plateRegex = r'[A-Za-z]{3}\s+[\d]{4}'

PlateDatabase = PlateDatabase()
findPlateState = PlateDatabase.findPlateState
createAlert = PlateDatabase.createAlert

# Engine setup for simplelpr
setupP = simplelpr.EngineSetupParms()
eng = simplelpr.SimpleLPR(setupP)

proc = eng.createProcessor()
proc.plateRegionDetectionEnabled = True
proc.cropToPlateRegionEnabled = True

# Text-to-Speech engine
engine = pyttsx3.init()

# Array to store detected texts
detected_texts = []

def get_color_from_string(color_name):
    # Get the RGB values using matplotlib
    rgb = mcolors.to_rgb(color_name)
    # Convert the RGB values from [0, 1] range to [0, 255] range and to integer
    rgb = tuple(int(c * 255) for c in rgb)
    # OpenCV uses BGR format, so convert the RGB to BGR
    bgr = (rgb[2], rgb[1], rgb[0])
    return bgr

# Function to handle mouse click events
def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        for text, (left, top, width, height) in detected_texts:
            if left < x < left + width and top < y < top + height:
                print(f"Clicked on plate: {text}")
                normalized_code = text.replace(' ', '')
                createAlert(normalized_code)
                global tts_thread_active
                if not tts_thread_active:
                    tts_thread = threading.Thread(target=announce_report)
                    tts_thread.start()
                    tts_thread_active = True

def announce_warning():
    global tts_thread_active
    engine.say("Cuidado con el conductor de delante, este vehículo ha sido reportado como peligroso")
    engine.runAndWait()
    time.sleep(5)
    tts_thread_active = False

def announce_report():
    global tts_thread_active
    engine.say("Reportado a las autoridades")
    engine.runAndWait()
    time.sleep(5)
    tts_thread_active = False


# Global variable to track if the thread is active
tts_thread_active = False


# Function to process each video frame
def process_frame(frame):
    
    # Convert the OpenCV image (BGR) to simplelpr compatible format (RGB)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    cds = proc.analyze(rgb_frame)

    global detected_texts

    # Process detected plates
    for cd in cds:
        for m in cd.matches:
            if re.match(plateRegex, m.text):
                # Get bounding box coordinates
                left = m.boundingBox.left
                top = m.boundingBox.top
                width = m.boundingBox.width
                height = m.boundingBox.height

                normalized_code = m.text.replace(' ', '')

                findResult = findPlateState(normalized_code)
                color = (0, 0, 255)
                comments = ""

                if findResult:
                    comments = findResult['level']
                    color = findResult["color"]
                    # Check if the thread is active before starting
                    global tts_thread_active
                    if color == (0, 0, 255) and not tts_thread_active:
                        tts_thread = threading.Thread(target=announce_warning)
                        tts_thread.start()
                        tts_thread_active = True

                # Overlay a rectangle around the plate
                cv2.rectangle(frame, (left, top), (left + width, top + height), color, 2)

                # Overlay plate text
                cv2.putText(frame, comments, (left, top + height + 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.putText(frame, f"Plate: {m.text} ", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

                # Store the detected text and its bounding box
                detected_texts.append((m.text, (left, top, width, height)))

    # Display the processed frame
    cv2.imshow("Video", frame)
    cv2.waitKey(1)

# Capture video from the notebook camera
cap = cv2.VideoCapture(video_stream_id)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if len(detected_texts) > 10:
        detected_texts = []
    # Process the video frame
    process_frame(frame)

    # Set mouse callback function
    cv2.setMouseCallback("Video", click_event)

    # Exit the loop by pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release video capture and close windows
cap.release()
cv2.destroyAllWindows()