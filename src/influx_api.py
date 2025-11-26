from flask import Flask, request, jsonify
import config
import requests
import urllib.parse as _up
from datetime import datetime

app = Flask(__name__)

def timestamp_to_dateTime(t):
    try:
        s = str(t)
        if s.endswith('Z'):
            s = s[:-1]
        # drop fractional seconds for parsing
        if '.' in s:
            s = s.split('.', 1)[0]
        dt = datetime.fromisoformat(s)
        time_str = dt.strftime('%H:%M:%S')
        date_str = dt.strftime('%Y-%m-%d')
    except Exception:
        # fall back to raw value
        time_str = ''
        date_str = ''
    return time_str, date_str

@app.after_request
def _add_cors_headers(response):
    # Allow frontend to call this API from other origins during development.
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    return response


def influx_query(q: str):
    url = config.INFLUX_URL.rstrip('/') + '/query'
    params = {'q': q, 'db': config.INFLUX_DB}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


@app.route('/api/measurements', methods=['GET', 'OPTIONS'])
def measurements():
    # Handle preflight
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = influx_query('SHOW MEASUREMENTS')
        results = data.get('results', [])
        measurements = []
        if results and 'series' in results[0]:
            for row in results[0]['series']:
                measurements.extend(row.get('values', []))
        # values are lists like [["measurement1"], ...]
        measurements = [m[0] for m in measurements]
        return jsonify({'measurements': measurements})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/points', methods=['GET', 'OPTIONS'])
def points():
    # Handle preflight
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    meas = request.args.get('measurement')
    limit = int(request.args.get('limit', 100))
    if not meas:
        return jsonify({'error': 'measurement required'}), 400
    # protect simple injection by quoting measurement
    m = '"' + meas.replace('"', '') + '"'
    q = f'SELECT * FROM {m} ORDER BY time DESC LIMIT {limit}'
    try:
        # For daily_counters we fetch a larger window and aggregate by date
        # server-side so the frontend receives one row per date with summed counts.
        fetch_limit = max(limit, 500)
        # Query using a higher limit to ensure we capture all intermediate writes
        data = influx_query(f'SELECT * FROM {m} ORDER BY time DESC LIMIT {max(500, fetch_limit)}')
        results = data.get('results', [])
        rows = []
        if results and 'series' in results[0]:
            for row in results[0]['series']:
                cols = row.get('columns', [])
                for vals in row.get('values', []):
                    rows.append(dict(zip(cols, vals)))

        if meas == 'daily_counters':
            # Aggregate rows by `date`, summing the two counters. Coerce values to numbers.
            agg = {}
            def to_num(v):
                try:
                    if v is None:
                        return 0
                    # Influx may return numbers or strings; handle both
                    return int(float(v))
                except Exception:
                    return 0

            for r in rows:
                date = r.get('date') or r.get('Date') or None
                if not date:
                    continue
                success = to_num(r.get('command_success_count'))
                treat = to_num(r.get('treat_count'))
                if date not in agg:
                    agg[date] = {'date': date, 'command_success_count': success, 'treat_count': treat}
                else:
                    agg[date]['command_success_count'] += success
                    agg[date]['treat_count'] += treat

            # Convert to array sorted by date desc and apply requested limit
            merged = sorted(list(agg.values()), key=lambda x: x['date'], reverse=True)
            merged = merged[:limit]
            return jsonify({'points': merged})

        # For dog activity measurements, return a simplified view containing
        # only posture, time (HH:MM:SS) and date. 
        if meas == 'dog_activity':
            simplified = []
            for r in rows:
                posture = r.get('posture') or None

                time_str = ''
                date_str = ''
                t = r.get('time') or None
                if t:
                    time_str, date_str = timestamp_to_dateTime(t)

                simplified.append({'posture': posture, 'time': time_str, 'date': date_str})

            return jsonify({'points': simplified})

        # For command_success measurement, return only the minimal view
        # containing target_pose, time (HH:MM:SS) and date.
        if meas == 'command_success':
            simplified = []
            for r in rows:
                target = r.get('target_pose') or None

                time_str = ''
                date_str = ''
                t = r.get('time') or None
                if t:
                    time_str, date_str = timestamp_to_dateTime(t)

                simplified.append({'target_pose': target, 'time': time_str, 'date': date_str})

            return jsonify({'points': simplified})
        
        if meas == 'pose_transition':
            simplified = []
            for r in rows:
                from_pose = r.get('from') or None
                to_pose = r.get('to') or None

                time_str = ''
                date_str = ''
                t = r.get('time') or None
                if t:
                    time_str, date_str = timestamp_to_dateTime(t)

                simplified.append({'from': from_pose, 'to': to_pose, 'time': time_str, 'date': date_str})
            
            return jsonify({'points': simplified})
        
        if meas == 'audio_playback':
            simplified = []
            for r in rows:
                text = r.get('text') or None
                wl = r.get('length') or None

                time_str = ''
                date_str = ''
                t = r.get('time') or None
                if t:
                    time_str, date_str = timestamp_to_dateTime(t)

                if text is not None:
                    simplified.append({'text': text, 'length': wl, 'time': time_str, 'date': date_str})

            return jsonify({'points': simplified})

        return jsonify({'points': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('Starting Influx API on 0.0.0.0:4000')
    app.run(host='0.0.0.0', port=4000)
