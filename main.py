import os
import random
import string
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
import json
import time
import uuid

# Flask app setup
app = Flask(__name__)
CORS(app)  # Allow cross-origin requests
app.config['SECRET_KEY'] = 'mysecret'
USER_DATA_DIR = 'user_data'
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

socketio = SocketIO(app, cors_allowed_origins="*")
GAMES = {}
API_KEY = 'secure_game_api_key'

def generate_random_letters(size=9):
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(size))

def load_user_data(username):
    user_file = os.path.join(USER_DATA_DIR, f"{username}.json")
    if os.path.exists(user_file):
        with open(user_file, 'r') as f:
            return json.load(f)
    return None

def save_user_data(username, data):
    user_file = os.path.join(USER_DATA_DIR, f"{username}.json")
    with open(user_file, 'w') as f:
        json.dump(data, f)

def calculate_score(word):
    return len(word) * 10

def validate_word(word):
    # Placeholder: Replace with actual word validation logic using a dictionary or API
    return word.isalpha()

@app.route('/api', methods=['POST'])
def api():
    if request.headers.get('API-KEY') != API_KEY:
        return jsonify({'status': 'error', 'message': 'Invalid API Key'}), 403

    action = request.json.get('action')
    if action == 'get_user':
        username = request.json.get('username')
        data = load_user_data(username)
        return jsonify({'status': 'success', 'data': data}) if data else jsonify({'status': 'error', 'message': 'User not found'})

    if action == 'create_user':
        username = request.json.get('username')
        password = request.json.get('password')
        if not password.isdigit() or len(password) != 4:
            return jsonify({'status': 'error', 'message': 'Password must be a 4-digit number'}), 400
        if load_user_data(username):
            return jsonify({'status': 'error', 'message': 'Username already exists'}), 409
        user_data = {'username': username, 'password': password, 'score': 0, 'money_earned': 0}
        save_user_data(username, user_data)
        return jsonify({'status': 'success', 'message': 'User created successfully'})

    if action == 'update_score':
        username = request.json.get('username')
        score = request.json.get('score', 0)
        user_data = load_user_data(username)
        if not user_data:
            return jsonify({'status': 'error', 'message': 'User not found'})
        user_data['score'] += score
        user_data['money_earned'] += score * 0.1  # Example: 10% of score as money
        save_user_data(username, user_data)
        return jsonify({'status': 'success', 'message': 'Score updated successfully', 'data': user_data})

    if action == 'get_game':
        game_id = request.json.get('game_id')
        game = GAMES.get(game_id)
        return jsonify({'status': 'success', 'game': game}) if game else jsonify({'status': 'error', 'message': 'Game not found'})

    return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

@socketio.on('connect')
def handle_connect():
    emit('server_message', {'message': 'Connected to the server'})

@socketio.on('join_game')
def handle_join_game(data):
    username = data.get('username')
    user_data = load_user_data(username)
    if not user_data:
        emit('error', {'message': 'User not found'})
        return

    game_id = None
    for gid, game in GAMES.items():
        if game['player2'] is None:
            game['player2'] = username
            game['start_time'] = time.time()
            game_id = gid
            break

    if not game_id:
        game_id = str(uuid.uuid4())
        GAMES[game_id] = {
            'player1': username, 'player2': None,
            'player1_score': 0, 'player2_score': 0,
            'start_time': None
        }

    join_room(game_id)
    emit('game_joined', {'game_id': game_id, 'player1': GAMES[game_id]['player1'], 'player2': GAMES[game_id]['player2']}, room=game_id)

@socketio.on('submit_word')
def handle_submit_word(data):
    game_id = data.get('game_id')
    username = data.get('username')
    word = data.get('word')

    if game_id not in GAMES:
        emit('error', {'message': 'Game not found'})
        return

    if not validate_word(word):
        emit('error', {'message': 'Invalid word'})
        return

    game = GAMES[game_id]
    score = calculate_score(word)

    if username == game['player1']:
        game['player1_score'] += score
    elif username == game['player2']:
        game['player2_score'] += score
    else:
        emit('error', {'message': 'User not in game'})
        return

    emit('score_update', {
        'player1_score': game['player1_score'],
        'player2_score': game['player2_score']
    }, room=game_id)

@socketio.on('get_timer')
def handle_timer_request(data):
    game_id = data.get('game_id')
    if game_id not in GAMES or 'start_time' not in GAMES[game_id] or GAMES[game_id]['start_time'] is None:
        emit('error', {'message': 'Timer unavailable'})
        return
    elapsed_time = time.time() - GAMES[game_id]['start_time']
    emit('timer_update', {'elapsed_time': elapsed_time})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5005)
