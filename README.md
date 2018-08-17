PythonVLM is a simple command-line python implementation of Litchi Virtual Mission https://mavicpilots.com/threads/virtual-litchi-mission.31109/

Code was based on reverse engineering original VLM. Currently it only converts litchi mission CSV file to google-aerth KML file contating virtual tour.

Dependencies:
 - python2.7 | python3.X
 - geocoder
 - geographiclib
 - pykml

Example usage:
 - pip install geocoder geographiclib pykml
 - ./vlm.py /path/to/mymission.csv
 - google-earth-pro /path/to/mymission.kml
 - Click mission name under "Temporary places" and double-click "Virtual mission"

Notes:
 - Code is compatible with python3, but pykml is not python3 ready, so you'll have to fix a couple of lines in pykml in order to make it work

