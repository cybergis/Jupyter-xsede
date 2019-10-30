#!/usr/bin/env python
from string import Template
from IPython.display import IFrame
from xml.dom import minidom
import json
import numpy as np

class Floret(object):
    '''CyberGIS Mapping tool based on Leaflet'''

    def __init__(self, title, name):
        self.name=name
        self.title=title
        self.extraheader=''
        self.layers = []
        self.bottom = -90
        self.left = -180
        self.top = 90
        self.right = 180
        self.center = [0,0]
        self.zoom_start = 1

    def getTMSBbox(self, path):
        xmldoc = minidom.parse('%s/tilemapresource.xml'%path)
        itemlist = xmldoc.getElementsByTagName('BoundingBox')
        bottom=float(itemlist[0].attributes['miny'].value)
        left=float(itemlist[0].attributes['minx'].value)
        top=float(itemlist[0].attributes['maxy'].value)
        right=float(itemlist[0].attributes['maxx'].value)
        return [bottom, left, top, right]

    def getGeoJsonBbox(self, path):
        m=json.load(open(path))
        coords = [i['geometry']['coordinates'] for i in m['features']]
        while type(coords[0][0]) == list:
            coords = [j for i in coords for j in i]
        right, top = np.max(coords,0)[:2]
        left, bottom = np.min(coords,0)[:2]
        return [bottom, left, top, right]

    def getWMSBbox(self, path):
         return [0, 0, 30, 30]

    def addTMSLayer(self, name, path, opacity=0.7):
        self.layers.append(('TMS',name,path,opacity, self.getTMSBbox(path)))
        return self

    def addWMSLayer(self, name, path, layername):
        self.layers.append(('WMS', name, path, layername, self.getWMSBbox(path)))
        return self

    def addGeoJson(self, name, path):
        new_path = path+'.floret'
        self.extraheader += '<script src="%s"></script>\n'%new_path
        var_name = path.split('/')[-1].split('.')[0].replace('-','_')
        self.layers.append(('GeoJson', name, var_name, self.getGeoJsonBbox(path)))
        with open(new_path,'w') as output:
            output.write('var %s = %s;'%(var_name,open(path).read()))
        return self

    def __fitBounds(self):
        if len(self.layers) > 0:
            bounds=zip(*[_[-1] for _ in self.layers])
            self.bottom=min(bounds[0])
            self.left=min(bounds[1])
            self.top=max(bounds[2])
            self.right=max(bounds[3])

    def __layerDef(self, layer):
        if layer[0]=='TMS':
            return "L.tileLayer('%s/{z}/{x}/{y}.png', {tms: true, opacity: %f})"%(layer[2], layer[3])
        elif layer[0]=='WMS':
            return "L.tileLayer.wms('%s?', {layers: '%s', format: 'image/png',transparent: true})"%(layer[2],layer[3])
        else:
            return "L.geoJSON(%s)"%(layer[2].split('.')[0])

    def __render(self):
        with open('/opt/cybergis/leaflet_template.html') as input:
            temp=Template(input.read())

        self.__fitBounds()
        self.html=temp.substitute(
            extraheader=self.extraheader,
            center=str(self.center),
            zoom_start=self.zoom_start,
            title=self.title,
            overlayLayers_dict='{'+','.join('"%s":layer%d'%(l[1],i) for i,l in enumerate(self.layers))+'}',
            overlayLayers_def='\n'.join('var layer%d=%s;layer%d.addTo(map)'%(i,self.__layerDef(l),i) for i,l in enumerate(self.layers)),
            bottom=str(self.bottom),
            right=str(self.right),
            top=str(self.top),
            left=str(self.left)
        )
        with open('%s.html'%self.name, 'w') as output:
            output.write(self.html)

    def display(self, width=1000, height=600):
        self.__render()
        return IFrame('%s.html'%self.name, width=width, height=height)
