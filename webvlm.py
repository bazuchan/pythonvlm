#!/usr/bin/python3

from flask import Flask
from flask import request
import json
import os
import vlm

app = Flask(__name__)
#app.config['PROPAGATE_EXCEPTIONS'] = True

googlekey = os.getenv('GOOGLEKEY', '')
if not googlekey:
    d = os.path.dirname(os.path.abspath(__file__))
    conf = os.path.join(d, 'config.py')
    if os.access(conf, os.R_OK):
        try:
            from config import googlekey
        except NameError:
            googlekey = ''

conv = vlm.Convert(googlekey=googlekey)

@app.route('/convert', methods=['POST'])
def api():
    j = request.get_json()
    if not j or not '0' in j.keys() or not '1' in j.keys():
        return 'Bad request\n', 400, {'Content-Type': 'text/plain; charset=utf-8'}
    try:
        mission = j['1'].rsplit('.', 1)[0]
        csv = j['0'].split('\n')
        conv.readcsv(csv, mission)
    except:
        return 'Bad request data\n', 400, {'Content-Type': 'text/plain; charset=utf-8'}
    conv.smooth()
    kml = conv.getkml()
    resp = json.dumps({'kml':kml.decode('utf-8'), 'mission':mission})
    return resp, 200, {'Content-Type': 'application/json; charset=utf-8'}

if __name__ == '__main__':
    app.run()

