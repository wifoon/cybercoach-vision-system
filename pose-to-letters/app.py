import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose()

cap = cv2.VideoCapture(0)

def get_letter(landmarks):
    tolerance = 0.1

    #left
    ls = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    le = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW]
    lw = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
    #right
    rs = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    re = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW]
    rw = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]

    # T
    if abs(lw.y - ls.y) < tolerance and abs(le.y - ls.y) < tolerance and abs(rw.y - rs.y) < tolerance and abs(re.y - rs.y) < tolerance and abs(ls.y - rs.y) < tolerance:
        return "T"
    
    # Y
    if abs(lw.y - rw.y) < tolerance and abs(le.y - re.y) < tolerance and lw.y < le.y < ls.y and rw.y < re.y < rs.y:
        return "Y"
    
    # I
    if lw.y > le.y > ls.y and rw.y > re.y > rs.y:
        if abs(lw.x - le.x) < tolerance and abs(rw.x - re.x) < tolerance:
            return "I"
        
    # L
    if lw.y < le.y < ls.y and abs(lw.x - ls.x) < tolerance:
        if abs(rs.y - re.y) < tolerance and abs(re.y - rw.y) < tolerance:
            return "L"

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(frame_rgb)

    detected_letter = ""

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        landmarks = results.pose_landmarks.landmark

        detected_letter = get_letter(landmarks)

        if detected_letter:
            cv2.putText(frame, f"{detected_letter}", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 255), 3)

    cv2.imshow("Pose-to-letters", frame)

    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
