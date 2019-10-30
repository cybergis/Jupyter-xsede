from getpass import getpass
import json
import requests
import warnings
import getpass
import pandas as pd
warnings.filterwarnings("ignore")

class TopoLens(object):
    def __init__(self, admin=False):
        """
        Initialize TopoLens service with user authentication
        """
        self.endpoint = "http://141.142.170.7:63830/rest/v1/"
        if admin:
            self.endpoint += "admin/"
        self.user = raw_input('User name ')
        self.token=requests.post('https://sandbox.cigi.illinois.edu/rest/token',
                            data = {'username':self.user,'password':getpass.getpass('Password')},
                            verify=False).json()['result']['token']
        self.headers={'x-user-name' :self.user,
                     'x-auth-token':self.token,
                     'Content-Type':'text/plain;charset=utf-8'}


    def getDataproducts(self,did=None,product=None):
        """
        List all existing data products
        """
        appendix=''
        if did:
            appendix += did +'/'
            if product:
                appendix += product
        query='dataproducts/'+appendix
        a=requests.get(self.endpoint+query,headers=self.headers,).json()['data']
        if did:
            a=[a]
        return pd.DataFrame.from_records(a)


    def getProjections(self,pid=None):
        """
        Get projections
        """
        query='projections/'+(pid if pid else '')
        a=requests.get(self.endpoint+query,headers=self.headers,).json()['data']
        if pid:
            a=[a]
        return pd.DataFrame.from_records(a)

    def getBoundaries(self,bid=None):
        """
        Get boundaries
        """
        query='boundaries/'+(bid if bid else '')
        a=requests.get(self.endpoint+query,headers=self.headers,).json()['data']
        if bid:
            a=[a]
        return pd.DataFrame.from_records(a)

    def addProjection(self, projection_file):
        pass

    def addBoundary(self, json):
        r=requests.post(self.endpoint+"boundaries",headers=self.headers,data=json)
        return r.json()

    def addDataproduct(self, title="Untitled", public=False, source="USGS_NED_DATA",
                       boundary='fJP6Svh4pyuvqM9dm', projection="proj_3857", resolution=[20,20],
                       slope=False, hillshade=False, pitremove=False,
                       resamplingMethod = "bilinear", fileFormat = "GTiff"):

        form={'title':title,
              'public':public,
              'input':{
                      'source':source,
                      'boundary':boundary,
                      'projection':projection,
                      'resolution':resolution,
                      'products':{
                                  'slope':slope,
                                  'hillshade':hillshade,
                                  'pitremove':pitremove
                                  },
                      'resamplingMethod': resamplingMethod,
                      'fileFormat': fileFormat
                      }
              }

        r=requests.post(self.endpoint+'dataproducts',
                        headers=self.headers,
                        data=json.dumps(form))
        return r.json()

    def preview(self, did, product="DEM"):
        p=self.getDataproducts(did,product)
        url=p['visualizationInfo'][0]['uri']
        layer=p['visualizationInfo'][0]['layer']
        return [product,url,'topolens:'+layer]

    def download(self, did, filename, product="DEM"):
        r=requests.get(self.endpoint+"dataproducts/"+did+'/'+product+'/download',headers=self.headers)
        with open(filename,'w') as output:
            output.write(r.content)