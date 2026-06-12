import math
import numpy as np
from collections import deque
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


class EMAFilter:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.values = {}

    def update(self, key, new_value):
        if key not in self.values:
            self.values[key] = new_value
        else:
            self.values[key] = self.alpha * new_value + (1 - self.alpha) * self.values[key]
        return self.values[key]

def calculate_angle_2d(p1, p2, p3):
    radians = math.atan2(p3['y'] - p2['y'], p3['x'] - p2['x']) - \
              math.atan2(p1['y'] - p2['y'], p1['x'] - p2['x'])
    angle = abs(math.degrees(radians))
    if angle > 180.0:
        angle = 360.0 - angle
    return angle

def calculate_torso_angle_2d(hip, shoulder):
    v_torso = np.array([shoulder['x'] - hip['x'], shoulder['y'] - hip['y']])
    v_up = np.array([0.0, -1.0])
    v_torso_norm = v_torso / (np.linalg.norm(v_torso) + 1e-6)
    return np.degrees(np.arccos(np.clip(np.dot(v_torso_norm, v_up), -1.0, 1.0)))


class CyberTrener:
    def __init__(self):
        self.state = 'CALIBRATING'
        self.reps = 0
        self.errors = []
        self.smoother = EMAFilter(alpha=0.3)
        
        self.calib_frames = 30
        self.buffer_elbow = deque(maxlen=self.calib_frames)
        self.buffer_back_angle = deque(maxlen=self.calib_frames)
        self.buffer_torso_angle = deque(maxlen=self.calib_frames)
        self.buffer_knee = deque(maxlen=self.calib_frames)
        
        self.base_elbow = 0.0
        self.base_back_angle = 0.0
        self.base_torso_angle = 0.0
        self.base_knee = 0.0

        self.frames_to_trigger = 7 
        self.error_trackers = {
            'cat_back': {'count': 0, 'active': False, 'msg': "Wyprostuj plecy! (Koci grzbiet)"},
            'knees': {'count': 0, 'active': False, 'msg': "Utrzymaj ugięte kolana!"},
            'torso_up': {'count': 0, 'active': False, 'msg': "Nie podnoś tułowia! Pracuj rękami."}
        }

    def get_dominant_side(self, landmarks):
        """Wybiera widoczny profil (lewy lub prawy)."""
        left_vis = sum([landmarks[i].get('visibility', 0) for i in [7, 11, 13, 15, 23, 25, 27]])
        right_vis = sum([landmarks[i].get('visibility', 0) for i in [8, 12, 14, 16, 24, 26, 28]])
        if right_vis > left_vis:
            return {'ear': 8, 'sh': 12, 'el': 14, 'wr': 16, 'hip': 24, 'kn': 26, 'ank': 28}
        return {'ear': 7, 'sh': 11, 'el': 13, 'wr': 15, 'hip': 23, 'kn': 25, 'ank': 27}

    def _update_error_state(self, key, is_bad):
        """Mechanizm histerezy: filtruje chwilowe szumy i stabilizuje błędy."""
        tracker = self.error_trackers[key]
        
        if is_bad:
            tracker['count'] += 1
        else:
            tracker['count'] = max(0, tracker['count'] - 2) 

        if tracker['count'] >= self.frames_to_trigger:
            tracker['active'] = True
            tracker['count'] = self.frames_to_trigger
        elif tracker['count'] == 0:
            tracker['active'] = False
            
        return tracker['active']

    def process_frame(self, landmarks, world_landmarks):
        self.errors = []
        idx = self.get_dominant_side(landmarks)

        if landmarks[idx['hip']].get('visibility', 1.0) < 0.4:
            return ["Pokaż całą sylwetkę z boku"], self.reps, self.state

        ear = landmarks[idx['ear']]
        sh, el, wr = landmarks[idx['sh']], landmarks[idx['el']], landmarks[idx['wr']]
        hip, kn, ank = landmarks[idx['hip']], landmarks[idx['kn']], landmarks[idx['ank']]

        raw_elbow = calculate_angle_2d(sh, el, wr)
        raw_knee = calculate_angle_2d(hip, kn, ank)
        raw_torso = calculate_torso_angle_2d(hip, sh)
        raw_back = calculate_angle_2d(ear, sh, hip)

        current_elbow = self.smoother.update('elbow', raw_elbow)
        current_knee = self.smoother.update('knee', raw_knee)
        current_torso_angle = self.smoother.update('torso', raw_torso)
        current_back_angle = self.smoother.update('back', raw_back)

        if self.state == 'CALIBRATING':
            if 40 < current_torso_angle < 100:
                self.buffer_elbow.append(current_elbow)
                self.buffer_back_angle.append(current_back_angle)
                self.buffer_torso_angle.append(current_torso_angle)
                self.buffer_knee.append(current_knee)
                
                if len(self.buffer_elbow) == self.calib_frames:
                    std_elbow = np.std(self.buffer_elbow)
                    std_torso = np.std(self.buffer_torso_angle)
                    
                    if std_elbow < 5.0 and std_torso < 5.0:
                        self.base_elbow = np.mean(self.buffer_elbow)
                        self.base_back_angle = np.mean(self.buffer_back_angle)
                        self.base_torso_angle = np.mean(self.buffer_torso_angle)
                        self.base_knee = np.mean(self.buffer_knee)
                        
                        self.state = 'IDLE'
                        self.errors.append("Kalibracja udana!")
                    else:
                        self.errors.append("Zatrzymaj się w pozycji startowej na 1 sekundę...")
            else:
                self.buffer_elbow.clear()
                self.buffer_back_angle.clear()
                self.errors.append("Pochyl się do pozycji startowej z opuszczonymi rękami.")
                
            return self.errors, self.reps, "KALIBRACJA"

        cond_cat_back = current_back_angle < (self.base_back_angle - 12)
        cond_knees = current_knee > self.base_knee + 15
        cond_torso = current_torso_angle < self.base_torso_angle - 20

        is_cat_back = self._update_error_state('cat_back', cond_cat_back)
        is_bad_knees = self._update_error_state('knees', cond_knees)
        is_torso_up = self._update_error_state('torso_up', cond_torso)

        if is_cat_back: self.errors.append(self.error_trackers['cat_back']['msg'])
        if is_bad_knees: self.errors.append(self.error_trackers['knees']['msg'])
        if is_torso_up: self.errors.append(self.error_trackers['torso_up']['msg'])

        bad_posture = len(self.errors) > 0

        if bad_posture:
            return self.errors, self.reps, "POPRAW POZYCJĘ"


        if self.state == 'IDLE':
            if current_elbow < self.base_elbow - 20:
                self.state = 'CONCENTRIC'

        elif self.state == 'CONCENTRIC':
            if current_elbow < 90: 
                self.state = 'ECCENTRIC'

        elif self.state == 'ECCENTRIC':
            if current_elbow > self.base_elbow - 15:
                self.reps += 1
                self.state = 'IDLE'

        if not self.errors:
            self.errors.append("Dobra technika!")

        state_pl = "OCZEKIWANIE"
        if self.state == 'CONCENTRIC': state_pl = "PRZYCIĄGAJ"
        elif self.state == 'ECCENTRIC': state_pl = "OPUSZCZAJ"

        return self.errors, self.reps, state_pl

analyzer = CyberTrener()

@socketio.on('connect')
def handle_connect():
    global analyzer
    analyzer = CyberTrener()
    print("Podłączono klienta. Reset kalibracji.")

@socketio.on('pose_data')
def handle_pose(data):
    landmarks = data.get('landmarks', [])
    world_landmarks = data.get('world_landmarks', [])

    if not landmarks or len(landmarks) < 33 or not world_landmarks:
        return

    messages, reps, phase = analyzer.process_frame(landmarks, world_landmarks)

    emit('pose_result', {
        'messages': messages,
        'reps': reps,
        'phase': phase
    })

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)