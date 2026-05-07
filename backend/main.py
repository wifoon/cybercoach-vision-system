import os
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('connect')
def handle_connect():
    print('Połączono')

@socketio.on('pose_data')
def handle_pose(data):
    landmarks = data.get('landmarks', [])
    print(f"Otrzymano dane. Ilość punktów: {len(landmarks)}")

    test = landmarks[0]

    emit('pose_result', {
        'status': 'success',
        'message': 'Dane przetworzone przez Pythona',
        'points': {
            'test': test
        }
    })

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)