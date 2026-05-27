import os
import math
from collections import deque
import numpy as np
import statistics
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

ratio_buffer = deque(maxlen=15)
knee_buffer = deque(maxlen=7)

workout_state = {
    'phase': 'DOWN',
    'reps': 0,
    'last_valid_knee': 150,
}

def calculate_distance_3d(p1, p2):
    return math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2 + (p2['z'] - p1['z'])**2)

def calculate_angle_3d(p1, p2, p3):
    v1 = np.array([p1['x'] - p2['x'], p1['y'] - p2['y'], p1['z'] - p2['z']])
    v2 = np.array([p3['x'] - p2['x'], p3['y'] - p2['y'], p3['z'] - p2['z']])
    
    v1_norm = v1 / np.linalg.norm(v1)
    v2_norm = v2 / np.linalg.norm(v2)
    
    dot_product = np.dot(v1_norm, v2_norm)
    
    dot_product = np.clip(dot_product, -1.0, 1.0)
    
    angle = np.degrees(np.arccos(dot_product))
    return angle

def calculate_horizontal_angle(p1, p2):
    dy = abs(p2['y'] - p1['y'])
    dx = abs(p2['x'] - p1['x'])
    return math.degrees(math.atan2(dy, dx))

def analyse_posture(landmarks, world_landmarks):
    global workout_state
    errors = []
    
    if landmarks[11].get('visibility', 1.0) < 0.5 or landmarks[23].get('visibility', 1.0) < 0.5:
        return ["Punkty zasłonięte"], workout_state['reps']
    
    left_ear = world_landmarks[7]
    left_shoulder = world_landmarks[11]
    left_elbow = world_landmarks[13]
    left_wrist = world_landmarks[15]
    left_hip = world_landmarks[23]
    left_knee = world_landmarks[25]
    left_ankle = world_landmarks[27]
    
    elbow_angle = calculate_angle_3d(left_shoulder, left_elbow, left_wrist)
    back_angle_ear = calculate_angle_3d(left_hip, left_shoulder, left_ear)

    current_knee_angle = calculate_angle_3d(left_hip, left_knee, left_ankle)
    
    torso_length = calculate_distance_3d(left_hip, left_shoulder)
    thigh_length = calculate_distance_3d(left_hip, left_knee)
    
    current_ratio = torso_length / thigh_length
    ratio_buffer.append(current_ratio)

    posture_angle = calculate_angle_3d(left_knee, left_hip, left_shoulder)
    
    if posture_angle > 160:
        return ["Zacznij wykonywać ćwiczenie"], workout_state['reps']
    
    if len(ratio_buffer) > 5:
        avg_ratio = sum(ratio_buffer) / len(ratio_buffer)
        is_cat_back = False

        if avg_ratio < 1.2:
            is_cat_back = True

        elif elbow_angle > 122 and back_angle_ear < 154:
            is_cat_back = True

        if is_cat_back:
            errors.append("Wyprostuj plecy! (Koci grzbiet)")

        #print(f"ratio: {avg_ratio:.3f} elbow: {elbow_angle:.3f} | back: {back_angle_ear:.3f} | {is_cat_back}")

    torso_angle = calculate_horizontal_angle(left_hip, left_shoulder)
    if torso_angle > 40:
        errors.append("Pochyl sie do przodu")

    if abs(current_knee_angle - workout_state['last_valid_knee']) < 15:
        workout_state['last_valid_knee'] = current_knee_angle
        knee_buffer.append(current_knee_angle)

    if len(knee_buffer) > 5:
        smoothed_knee = statistics.median(knee_buffer)
        if smoothed_knee > 160:
            errors.append("Ugnij kolana")

    if elbow_angle < 100 and workout_state['phase'] == 'DOWN':
        workout_state['phase'] = 'UP'
        
    elif elbow_angle > 120 and workout_state['phase'] == 'UP':
        workout_state['phase'] = 'DOWN'
        workout_state['reps'] += 1

    if not errors:
        return ["Poprawna technika"], workout_state['reps']
    
    return errors, workout_state['reps']

@socketio.on('connect')
def handle_connect():
    print('Połączono')

@socketio.on('pose_data')
def handle_pose(data):
    landmarks = data.get('landmarks', [])
    world_landmarks = data.get('world_landmarks', [])

    if not landmarks or len(landmarks) < 33 or not world_landmarks:
        return

    detected_errors, current_reps = analyse_posture(landmarks, world_landmarks)
    main_message = detected_errors[0]

    emit('pose_result', {
        'status': 'success',
        'messages': detected_errors,
        'reps': current_reps,
        'phase': workout_state['phase']
    })

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)