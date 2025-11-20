from flask import Flask, request, jsonify
import config
import requests
import urllib.parse as _up

app = Flask(__name__)


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
        data = influx_query(q)
        results = data.get('results', [])
        rows = []
        if results and 'series' in results[0]:
            for row in results[0]['series']:
                cols = row.get('columns', [])
                for vals in row.get('values', []):
                    rows.append(dict(zip(cols, vals)))
        return jsonify({'points': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('Starting Influx API on 0.0.0.0:4000')
    app.run(host='0.0.0.0', port=4000)
