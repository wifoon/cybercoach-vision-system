import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose()

cap = cv2.VideoCapture(0)

while cap.isOpened():
    _ , frame = cap.read()
    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(frame_rgb)

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        landmarks = results.pose_landmarks.landmark
        ramie_lewe = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]

    cv2.imshow("test", frame)

    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
