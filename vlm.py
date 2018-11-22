#!/usr/bin/python

from __future__ import division
import csv
import os
import math
import copy
import argparse
import requests
import simplejson
import logging
from geographiclib.geodesic import Geodesic
from pykml.factory import KML_ElementMaker as KML
from pykml.factory import GX_ElementMaker as GX
from lxml import etree

class Elevation(object):
    GOOGLEAPI = 'https://maps.googleapis.com/maps/api/elevation/json'
    OPENAPI = 'https://api.open-elevation.com/api/v1/lookup'
    MAXPERREQ = 100

    def __init__(self, key=''):
        self.key = key

    def singlerequest(self, latlons):
        try:
            if self.key:
                data = { 'locations': '|'.join(['{0},{1}'.format(*i[:2]) for i in latlons]), 'key': self.key }
                r = requests.get(self.GOOGLEAPI, data, timeout=30)
            else:
                data = { 'locations': [ {'latitude': i[0], 'longitude': i[1]} for i in latlons ] }
                r = requests.post(self.OPENAPI, json=data, timeout=120)
            j = r.json()
            e = [float(i.get('elevation', 0)) for i in j['results']]
            assert len(e) == len(latlons)
        except (requests.exceptions.Timeout, simplejson.errors.JSONDecodeError, KeyError, TypeError, ValueError, AssertionError):
            logging.error('Elevation API error, assuming zero ground elevation')
            return [0]*len(latlons)
        return e

    def request(self, latlons):
        res = []
        for k in range(0, (len(latlons)+self.MAXPERREQ-1)//self.MAXPERREQ):
            res += self.singlerequest(latlons[k*self.MAXPERREQ:k*self.MAXPERREQ+self.MAXPERREQ])
        return res

class Point(object):
    attrs = ['Latitude', 'Longitude', 'Altitude', 'AltMode', 'GroundAlt']
    def __init__(self, **kv):
        for i in self.attrs:
            if i in kv.keys():
                setattr(self, i, kv[i])
            else:
                setattr(self, i, 0)

    @classmethod
    def fromtuple(self, k):
        return self(Latitude = k[0], Longitude = k[1], Altitude = k[2], AltMode = k[3])

    def attrdict(self):
        return { key: self.__dict__[key] for key in self.__dict__.keys() if key in self.attrs }

    def __eq__(self, other):
        return not ( other is None or self.attrdict() != other.attrdict() )

    def __repr__(self):
        return repr(self.attrdict())

    def latlonalt(self):
        return (self.Latitude, self.Longitude, self.Altitude)

    def bearingto(self, to):
        return WayPoint.to360(Geodesic.WGS84.Inverse(self.Latitude, self.Longitude, to.Latitude, to.Longitude)['azi1'])

    def distanceto(self, to):
        return Geodesic.WGS84.Inverse(self.Latitude, self.Longitude, to.Latitude, to.Longitude)['s12']

    def distance3d(self, to):
        return math.sqrt(self.distanceto(to)**2 + (self.Altitude - to.Altitude)**2)

    def tiltto(self, to):
        return math.degrees(math.asin( (to.Altitude - self.Altitude) / self.distance3d(to) )) + 90.0

    def altcorrect(self, takeoffalt, groundalt):
        self.GroundAlt = groundalt
        if self.AltMode == 1 or takeoffalt is None:
            self.Altitude += self.GroundAlt
        else:
            self.Altitude += takeoffalt

    @staticmethod
    def to360(x):
        return (x + 360.0) % 360.0

class WayPoint(Point):
    attrs = Point.attrs + ['Heading', 'CurveSize', 'RotationDir', 'GimbalMode', 'GimbalTilt', 'Speed', 'Distance', 'LegTime', 'Bearing', 'Num', 'ActionType', 'ActionParam', 'Poi']
    def __init__(self, **kv):
        super(WayPoint, self).__init__(**kv)
        if self.ActionType == 0:
            self.ActionType, self.ActionParam = [], []
        if self.Poi == 0:
            self.Poi = None

    @classmethod
    def fromcsvline(self, line):
        wp = self()
        wp.Latitude, wp.Longitude, wp.Altitude, wp.Heading, wp.CurveSize, wp.RotationDir, _, wp.GimbalTilt = [float(i) for i in line[:8]]
        wp.GimbalMode = int(line[6])
        if len(line) > 37:
            wp.ActionType = [int(i) for i in line[8:38:2] if int(i)!=-1]
            wp.ActionParam = [int(i) for i in line[9:38:2]][:len(wp.ActionType)]
        if len(line) > 38:
            wp.AltMode = int(line[38])
        if len(line) > 39:
            wp.Speed = float(line[39])
        if len(line) > 43 and [float(i) for i in line[40:42]] != [0.0, 0.0]:
            wp.Poi = Point.fromtuple([float(i) for i in line[40:43]] + [int(line[43])])
        return wp

    def copy(self, full=False):
        new = copy.deepcopy(self)
        if not full:
            new.ActionType, new.ActionParam, new.Num = [], [], None
        return new

class Convert(object):
    def __init__(self, googlekey, speed=10.0, fov=85.0, takeoffalt=None, mincurve=5.0, nbezier=5, infilldist=1000.0):
        self.googlekey = googlekey
        self.takeoffalt = takeoffalt
        self.defspeed = speed
        self.hfov = Convert.HFOV(fov)
        self.mincurve = mincurve
        self.nbezier = nbezier
        self.infilldist = infilldist
        self.metric = True
        self.waypoints = []
        self.pois = []
        self.smoothed = []

    @staticmethod
    def HFOV(dfov):
        return 2.0 * math.degrees(math.atan( 18.0 * math.tan(math.radians(dfov) / 2.0) * 2.0 / 43.3 ))

    def readcsv(self, source, mission='mission'):
        self.mission = mission
        self.waypoints = []
        reader = csv.reader(source, delimiter=',', quotechar='"')
        header = self.checkheader(next(reader))
        for line in reader:
            if len(line)<8:
                continue
            wp = WayPoint.fromcsvline(line)
            if not self.metric:
                wp.Altitude /= 3.28084
                wp.CurveSize /= 3.28084
                if wp.Poi:
                    wp.Poi.Altitude /= 3.28084
            if wp.Speed == 0:
                wp.Speed = self.defspeed
            if self.waypoints:
                wp.Distance = wp.distanceto(self.waypoints[-1])
                wp.Bearing = self.waypoints[-1].bearingto(wp)
            wp.GimbalTilt += 90.0
            if self.waypoints and wp.GimbalMode == 0:
                wp.GimbalTilt = self.waypoints[-1].GimbalTilt
            if wp.Poi and wp.Poi not in self.pois:
                self.pois.append(wp.Poi)
            elif wp.Poi:
                wp.Poi = self.pois[self.pois.index(wp.Poi)]
            wp.Num = len(self.waypoints)+1
            self.waypoints.append(wp)
        elevations = Elevation(key=self.googlekey).request([i.latlonalt() for i in self.waypoints + self.pois])
        self.takeoffalt = self.takeoffalt or elevations[0]
        for p in self.waypoints + self.pois:
            p.altcorrect(self.takeoffalt, elevations.pop(0))

    def checkheader(self, header):
        if header[0] != 'latitude' or header[5] != 'rotationdir':
            raise ValueError('Mismatching CSV header')
        if header[2] == 'altitude(m)':
            self.metric = True
        elif header[2] == 'altitude(ft)':
            self.metric = False
        else:
            raise ValueError('Mismatching CSV header')
        return header

    def appendsmoothed(self, wp):
        wp.Distance = wp.distance3d(self.smoothed[-1])
        wp.LegTime = wp.Distance / self.smoothed[-1].Speed
        self.smoothed.append(wp)

    def fillto(self, wp):
        pp = self.smoothed[-1]
        d = math.ceil(pp.distance3d(wp)/self.infilldist)
        for j in range(1, int(d)):
            sp = pp.copy()
            sp.Latitude = pp.Latitude + j * (wp.Latitude - pp.Latitude) / d
            sp.Longitude = pp.Longitude + j * (wp.Longitude - pp.Longitude) / d
            sp.Altitude = pp.Altitude + j * (wp.Altitude - pp.Altitude) / d
            self.appendsmoothed(sp)
        self.appendsmoothed(wp)

    @staticmethod
    def bezier(a, t):
        return (a[0] - 2.0 * a[1] + a[2]) * t * t + 2.0 * (a[1] - a[0]) * t + a[0]

    def addbezier(self, sp, bz, s):
        sp.Latitude, sp.Longitude, sp.Altitude = self.bezier(bz[0], s), self.bezier(bz[1], s), self.bezier(bz[2], s)
        self.fillto(sp)

    def smooth(self):
        self.smoothed = [self.waypoints[0].copy(full=True)]
        for wi in range(1, len(self.waypoints)-1):
            pp, wp, np = self.waypoints[wi-1:wi+2]
            if wp.CurveSize < self.mincurve:
                self.fillto(wp.copy(full=True))
                continue
            bz = [
                    [ wp.latlonalt()[i] - (wp.CurveSize / wp.Distance) * (wp.latlonalt()[i] - pp.latlonalt()[i]),
                      wp.latlonalt()[i],
                      wp.latlonalt()[i] + (wp.CurveSize / np.Distance) * (np.latlonalt()[i] - wp.latlonalt()[i]),
                    ] for i in range(0, 3)
                 ]
            for b in range(0, self.nbezier):
                s = b / (self.nbezier - 1.0)
                if s != 0.5 or self.nbezier % 2 == 0:
                    self.addbezier(wp.copy(), bz, s)
                if b == (self.nbezier - 1)//2:
                    self.addbezier(wp.copy(full=True), bz, 0.5)
        if len(self.waypoints)>1:
            self.fillto(self.waypoints[-1].copy(full=True))

        numbered = [i for i in range(0, len(self.smoothed)) if not self.smoothed[i].Num is None]
        for wi in range(0, len(numbered)-1):
            wp, np = self.smoothed[numbered[wi]], self.smoothed[numbered[wi+1]]
            diffhead = np.Heading - wp.Heading
            if diffhead > 180.0:
                diffhead -= 360.0
            elif diffhead < -180:
                diffhead += 360.0
            difftilt = np.GimbalTilt - wp.GimbalTilt
            for si in range(numbered[wi], numbered[wi+1]):
                sp = self.smoothed[si]
                wd = sp.distance3d(wp)
                nd = sp.distance3d(np)
                if wp.Poi and wp.Poi == np.Poi:
                    sp.Heading = sp.bearingto(wp.Poi)
                else:
                    sp.Heading = WayPoint.to360(wp.Heading + diffhead * wd / (wd+nd))
                if wp.Poi and wp.Poi == np.Poi and wp.GimbalMode == 1 and np.GimbalMode == 1:
                    sp.GimbalTilt = sp.tiltto(wp.Poi)
                else:
                    sp.GimbalTilt = wp.GimbalTilt + difftilt * wd / (wd+nd)

    def getkml(self):
        avgalt = sum([i.Altitude for i in self.waypoints]) / float(len(self.waypoints))
        minlat = min([i.Latitude for i in self.waypoints])
        minlon = min([i.Longitude for i in self.waypoints])
        maxlon = max([i.Longitude for i in self.waypoints])
        maxang = max([i.Latitude + (i.Altitude-avgalt) / (111120.0 * math.cos(math.radians(-20))) for i in self.waypoints])
        if abs(maxlon - minlon) > abs(maxang - minlat):
            rang = abs(maxlon - minlon) * 60.0 * 1852.0 / (2.0 * math.sin(math.radians(self.hfov) / 2.0)) * 1.2
        else:
            rang = abs(maxang - minlat) * 60.0 * 1852.0 / (2.0 * math.sin(math.radians(self.hfov) / 2.0)) * 16.0 / 9.0
        txtwaypoints = ' '.join(['%f,%f,%f' % (i.Longitude, i.Latitude, i.Altitude) for i in self.waypoints])
        txtsmoothed = ' '.join(['%f,%f,%f' % (i.Longitude, i.Latitude, i.Altitude) for i in self.smoothed])

        wfolder = KML.Folder( KML.name('WayPoint Markers'), KML.visibility(1),)
        pfolder = KML.Folder( KML.name('POI Markers'), KML.visibility(1),)
        vfolder = KML.Folder( KML.name('WayPoint Views'), KML.visibility(0),)
        playlist = GX.Playlist()

        #TODO: CDATA
        virtmission = KML.kml(
                KML.Document(
                    KML.name(self.mission),
                    KML.LookAt(
                        KML.latitude( (minlat+maxang)/2.0 ),
                        KML.longitude( (minlon+maxlon)/2.0 ),
                        KML.altitude(avgalt),
                        KML.heading(0),
                        KML.tilt(70),
                        KML.range(rang),
                        KML.altitudeMode("absolute"),
                        GX.horizFov(self.hfov),
                        ),
                    GX.Tour(
                        KML.name('Virtual Mission'),
                        playlist,
                        ),
                    KML.Style(
                        KML.LineStyle( KML.color('FF00FFFF'), KML.width(2),),
                        KML.PolyStyle( KML.color('4C00FFFF'),),
                        id='wpstyle',
                        ),
                    KML.Style(
                        KML.LineStyle( KML.color('FFFF00FF'), KML.width(2),),
                        KML.PolyStyle( KML.color('4CFF00FF'),),
                        id='smoothstyle',
                        ),
                    KML.Style(
                        KML.IconStyle( KML.Icon(KML.href('http://maps.google.com/mapfiles/kml/paddle/wht-blank.png'),),),
                        KML.BalloonStyle( KML.text('\n<h3>WayPoint $[Waypoint]</h3>\n<table border="0" width="200">\n<tr><td>Altitude (msl) <td>$[Altitude_Abs] m\n<tr><td>Altitude (rtg) <td>$[Altitude_Gnd] m\n<tr><td>Heading<td>$[Heading] degrees\n<tr><td>Gimbal Tilt<td> $[Gimbal] degrees\n</tr></table>\n'), KML.bgColor('ffffffbb'),),
                        id='wpmarkers',
                        ),
                    KML.Style(
                        KML.IconStyle( KML.Icon(KML.href('http://maps.google.com/mapfiles/kml/paddle/red-stars.png'),),),
                        KML.BalloonStyle( KML.text('\n<h3>POI $[POI]</h3>\n <table border="0" width="200">\n <tr><td>Altitude (msl) <td>$[Altitude_Abs] m\n <tr><td>Altitude (rtg) <td>$[Altitude_Gnd] m\n </tr></table>\n'), KML.bgColor('ffffffbb'),),
                        id='poimarkers',
                        ),
                    KML.Folder(
                        KML.name('Diagnostics'),
                        KML.Placemark(
                            KML.name('WayPoint Path'),
                            KML.visibility(0),
                            KML.styleUrl('#wpstyle'),
                            KML.LineString(
                                KML.extrude(1),
                                KML.tessellate(1),
                                KML.altitudeMode('absolute'),
                                KML.coordinates(txtwaypoints),
                                ),
                            ),
                        wfolder,
                        pfolder,
                        vfolder,
                        KML.Placemark(
                            KML.name('Smooth Flight Path'),
                            KML.visibility(1),
                            KML.styleUrl('#smoothstyle'),
                            KML.LineString(
                                KML.extrude(1),
                                KML.tessellate(1),
                                KML.altitudeMode('absolute'),
                                KML.coordinates(txtsmoothed),
                                ),
                            ),
                        ),
                    )
                )

        for wp in self.smoothed:
            playlist.append(
                    GX.FlyTo(
                        GX.duration(wp.LegTime),
                        GX.flyToMode('smooth'),
                        KML.Camera(
                            KML.latitude(wp.Latitude),
                            KML.longitude(wp.Longitude),
                            KML.altitude(wp.Altitude),
                            KML.heading(wp.Heading),
                            KML.tilt(wp.GimbalTilt),
                            KML.roll(0),
                            KML.altitudeMode("absolute"),
                            GX.horizFov(self.hfov),
                            ),
                        ),
                    )
            playlist.append(
                    GX.Wait(
                        GX.duration(0),
                        ),
                    )

        for wp in self.waypoints:
            wfolder.append(
                    KML.Placemark(
                        KML.name('WP%02d' % (wp.Num)),
                        KML.visibility(1),
                        KML.styleUrl('#wpmarkers'),
                        KML.ExtendedData(
                            KML.Data(KML.value(wp.Num), name='Waypoint'),
                            KML.Data(KML.value(round(wp.Altitude, 0)), name='Altitude_Abs'),
                            KML.Data(KML.value(round(wp.Altitude-wp.GroundAlt, 0)), name='Altitude_Gnd'),
                            KML.Data(KML.value(round(wp.Heading, 0)), name='Heading'),
                            KML.Data(KML.value(round(wp.GimbalTilt-90.0, 0)), name='Gimbal'),
                            ),
                        KML.Point(
                            KML.altitudeMode("absolute"),
                            KML.extrude(1),
                            KML.coordinates('%f,%f,%f' % (wp.Longitude,wp.Latitude,wp.Altitude)),
                            ),
                        ),
                    )

        for poi in self.pois:
            num = self.pois.index(poi)+1
            pfolder.append(
                    KML.Placemark(
                        KML.name('POI%02d' % num),
                        KML.visibility(1),
                        KML.styleUrl('#poimarkers'),
                        KML.ExtendedData(
                            KML.Data(KML.value(num), name='POI'),
                            KML.Data(KML.value(round(poi.Altitude, 0)), name='Altitude_Abs'),
                            KML.Data(KML.value(round(poi.Altitude-poi.GroundAlt, 0)), name='Altitude_Gnd'),
                            ),
                        KML.Point(
                            KML.altitudeMode("absolute"),
                            KML.extrude(1),
                            KML.coordinates('%f,%f,%f' % (poi.Longitude,poi.Latitude,poi.Altitude)),
                            ),
                        ),
                    )

        for wp in self.smoothed:
            if wp.Num is None:
                continue
            vfolder.append(
                    KML.Document(
                        KML.name('WP%03d' % (wp.Num)),
                        KML.visibility(0),
                        GX.Camera(
                            KML.latitude(wp.Latitude),
                            KML.longitude(wp.Longitude),
                            KML.altitude(wp.Altitude),
                            KML.heading(wp.Heading),
                            KML.tilt(wp.GimbalTilt),
                            KML.roll(0),
                            KML.altitudeMode("absolute"),
                            GX.horizFov(self.hfov),
                            ),
                        ),
                    )

        return etree.tostring(virtmission, pretty_print=True)

    def run(self, cname, kname):
        mission = os.path.basename(cname).rsplit('.', 1)[0]
        self.readcsv(open(cname), mission)
        self.smooth()
        open(kname, 'wb').write(self.getkml())

class MyHelpFormatter(argparse.HelpFormatter):
    def __init__(self, *kc, **kv):
        kv['width'] = 1000
        kv['max_help_position'] = 1000
        super(MyHelpFormatter, self).__init__(*kc, **kv)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=MyHelpFormatter)
    parser.add_argument('csvfile', help='litchi hub csv exported mission')
    parser.add_argument('kmlfile', help='write virtual mission to this file', default=None, nargs='?')
    parser.add_argument('-s', '--speed', help='Default speed in m/s', type=float, default=10.0)
    parser.add_argument('-f', '--fov', help='FOV angle', type=float, default=85.0)
    parser.add_argument('-g', '--ground', help='Takeoff point altitude', type=float, default=None)
    parser.add_argument('-b', '--bezier', help='Number of points to fill curves with bezier interpolation', type=int, default=5)
    parser.add_argument('-i', '--interval', help='Divide interval between points if exceeds this value in meters', type=float, default=1000.0)
    parser.add_argument('-m', '--mincurve', help='Minimal curve radius', type=float, default=5.0)
    parser.add_argument('-k', '--googlekey', help='Google maps elevation API key', default='')
    args = parser.parse_args()

    if not args.kmlfile:
        args.kmlfile = args.csvfile.rsplit('.', 1)[0]+'.kml'

    logging.basicConfig()

    c = Convert(args.googlekey, speed=args.speed, fov=args.fov, takeoffalt=args.ground, mincurve=args.mincurve, nbezier=args.bezier, infilldist=args.interval)
    c.run(args.csvfile, args.kmlfile)

