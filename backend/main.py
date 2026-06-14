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
            self.values[key] = (
                self.alpha * new_value + (1 - self.alpha) * self.values[key]
            )
        return self.values[key]


def calculate_angle_2d(p1, p2, p3):
    radians = math.atan2(p3["y"] - p2["y"], p3["x"] - p2["x"]) - math.atan2(
        p1["y"] - p2["y"], p1["x"] - p2["x"]
    )
    angle = abs(math.degrees(radians))
    return 360.0 - angle if angle > 180.0 else angle


def calculate_torso_angle_2d(hip, shoulder):
    torso = np.array([shoulder["x"] - hip["x"], shoulder["y"] - hip["y"]])
    up = np.array([0.0, -1.0])
    torso_norm = torso / (np.linalg.norm(torso) + 1e-6)
    return np.degrees(np.arccos(np.clip(np.dot(torso_norm, up), -1.0, 1.0)))


class CyberTrener:
    def __init__(self):
        self.is_calibrated = False
        self.state = "IDLE"
        self.reps = 0
        self.smoother = EMAFilter(alpha=0.3)

        # Bufory do kalibracji
        self.buffer_elbow = deque(maxlen=30)
        self.buffer_back = deque(maxlen=30)
        self.buffer_torso = deque(maxlen=30)
        self.buffer_knee = deque(maxlen=30)

        # Zapisane kąty idealnej postawy użytkownika
        self.base_elbow = 0.0
        self.base_back = 0.0
        self.base_torso = 0.0
        self.base_knee = 0.0

        # Proste liczniki błędów (histereza)
        self.error_counts = {"cat_back": 0, "knees": 0, "torso_up": 0}
        self.error_msgs = {
            "cat_back": "Wyprostuj plecy! (Koci grzbiet)",
            "knees": "Zegnij kolana!",
            "torso_up": "Obniż tułów.",
        }

    def _pobierz_katy(self, landmarks):
        """Wykrywa stronę ciała i zwraca wygładzone kąty."""
        # 1. Wybór dominującej strony
        left_vis = sum(
            [landmarks[i].get("visibility", 0) for i in [7, 11, 13, 15, 23, 25, 27]]
        )
        right_vis = sum(
            [landmarks[i].get("visibility", 0) for i in [8, 12, 14, 16, 24, 26, 28]]
        )
        idx = (
            {"ear": 8, "sh": 12, "el": 14, "wr": 16, "hip": 24, "kn": 26, "ank": 28}
            if right_vis > left_vis
            else {
                "ear": 7,
                "sh": 11,
                "el": 13,
                "wr": 15,
                "hip": 23,
                "kn": 25,
                "ank": 27,
            }
        )

        if landmarks[idx["hip"]].get("visibility", 1.0) < 0.4:
            return None  # Ciało niewidoczne

        # 2. Pobranie punktów
        ear, sh, el, wr = (
            landmarks[idx["ear"]],
            landmarks[idx["sh"]],
            landmarks[idx["el"]],
            landmarks[idx["wr"]],
        )
        hip, kn, ank = (
            landmarks[idx["hip"]],
            landmarks[idx["kn"]],
            landmarks[idx["ank"]],
        )

        # 3. Obliczenia i wygładzanie
        elbow = self.smoother.update("elbow", calculate_angle_2d(sh, el, wr))
        knee = self.smoother.update("knee", calculate_angle_2d(hip, kn, ank))
        torso = self.smoother.update("torso", calculate_torso_angle_2d(hip, sh))
        back = self.smoother.update("back", calculate_angle_2d(ear, sh, hip))

        return elbow, knee, torso, back

    def _kalibruj(self, elbow, knee, torso, back):
        """Zbiera dane o postawie startowej przez około sekundę."""
        if not (40 < torso < 100):
            self.buffer_elbow.clear()
            return ["Pochyl się do pozycji startowej z opuszczonymi rękami."]

        self.buffer_elbow.append(elbow)
        self.buffer_back.append(back)
        self.buffer_torso.append(torso)
        self.buffer_knee.append(knee)

        if len(self.buffer_elbow) == 30:
            if np.std(self.buffer_elbow) < 5.0 and np.std(self.buffer_torso) < 5.0:
                self.base_elbow, self.base_back = np.mean(self.buffer_elbow), np.mean(
                    self.buffer_back
                )
                self.base_torso, self.base_knee = np.mean(self.buffer_torso), np.mean(
                    self.buffer_knee
                )
                self.is_calibrated = True
                return ["Kalibracja udana!"]
            else:
                return ["Zatrzymaj się w pozycji startowej na 1 sekundę..."]

        return ["KALIBRACJA..."]

    def _sprawdz_bledy(self, knee, torso, back):
        """Weryfikuje poprawność postawy i zarządza tolerancją na błędy."""
        active_errors = []

        # Warunki błędów w bieżącej klatce
        conditions = {
            "cat_back": back < (self.base_back - 20),
            "knees": knee > self.base_knee + 8,
            "torso_up": torso < self.base_torso - 20,
        }

        # Aktualizacja liczników i generowanie komunikatów
        for key, is_bad in conditions.items():
            if is_bad:
                self.error_counts[key] += 1
            else:
                self.error_counts[key] = max(0, self.error_counts[key] - 2)

            if self.error_counts[key] >= 7:  # Błąd utrzymuje się > 7 klatek
                self.error_counts[key] = 7
                active_errors.append(self.error_msgs[key])

        return active_errors

    def _licz_powtorzenia(self, elbow):
        """Prosta maszyna stanów do liczenia pełnych ruchów."""
        if self.state == "IDLE" and elbow < self.base_elbow - 10:
            self.state = "CONCENTRIC"
        elif self.state == "CONCENTRIC" and elbow < self.base_elbow - 60:
            self.state = "ECCENTRIC"
        elif self.state == "ECCENTRIC" and elbow > self.base_elbow - 20:
            self.reps += 1
            self.state = "CONCENTRIC"

    # ---------------------------------------------------------
    # GŁÓWNA FUNKCJA KONTROLERA
    # ---------------------------------------------------------
    def process_frame(self, landmarks):
        # Krok 1: Pobranie kątów
        angles = self._pobierz_katy(landmarks)
        if not angles:
            return ["Pokaż całą sylwetkę z boku"], self.reps, self.state

        elbow, knee, torso, back = angles
        print(f"Elbow: {elbow:.1f}; base_elbow: {self.base_elbow:.1f}")
        print(f"Back: {back:.1f}; base_back: {self.base_back:.1f}")
        print(f"Torso: {torso:.1f}; base_torso: {self.base_torso:.1f}")
        print(f"Knee: {knee:.1f}; base_knee: {self.base_knee:.1f}")

        # Krok 2: Faza Kalibracji
        if not self.is_calibrated:
            msg = self._kalibruj(elbow, knee, torso, back)
            return msg, self.reps, "KALIBRACJA"

        # Krok 3: Analiza Błędów Techniki
        errors = self._sprawdz_bledy(knee, torso, back)
        if errors:
            return errors, self.reps, "POPRAW POZYCJĘ"

        # Krok 4: Prawidłowy Ruch (Liczenie powtórzeń)
        self._licz_powtorzenia(elbow)

        # Krok 5: Tłumaczenie stanu dla UI i zwrócenie wyniku
        fazy_pl = {
            "IDLE": "OCZEKIWANIE",
            "CONCENTRIC": "PRZYCIĄGAJ",
            "ECCENTRIC": "OPUSZCZAJ",
        }

        return ["Dobra technika!"], self.reps, fazy_pl.get(self.state, "OCZEKIWANIE")


# --- OBSŁUGA SERWERA ---

analyzer = CyberTrener()


@socketio.on("connect")
def handle_connect():
    global analyzer
    analyzer = CyberTrener()  # Reset przy odświeżeniu
    print("Podłączono klienta. Reset kalibracji.")


@socketio.on("pose_data")
def handle_pose(data):
    landmarks = data.get("landmarks", [])

    if not landmarks or len(landmarks) < 33:
        return

    messages, reps, phase = analyzer.process_frame(landmarks)

    emit("pose_result", {"messages": messages, "reps": reps, "phase": phase})


if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)
