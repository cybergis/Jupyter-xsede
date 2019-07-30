#!/usr/bin/env python
from __future__ import print_function
import warnings

import ipywidgets as widgets

warnings.filterwarnings("ignore", message="numpy.dtype size changed")
from ipywidgets import *
from IPython.display import display
from getpass import getpass
import glob
import os
import stat
import paramiko
from string import Template
from os.path import expanduser
from pkg_resources import resource_string
from IPython.core.magic import (register_line_magic, register_cell_magic,register_line_cell_magic)
import hashlib
from itertools import cycle
from IPython.display import IFrame
from threading import Thread
import time
import logging
from sys import exit
import shutil
import re 
from .summaVis import summaVis
import random
import fileinput
import sys
import math
import netCDF4 as nc
import numpy as np
from datetime import datetime
import uuid
from .comm import SSHComm
import queue
import zipfile
import json
import pandas as pd
pd.set_option('display.max_colwidth', -1)

#from FileBrowser import FileBrowser
# logger configuration 

SUMMA_TEMPLATE='''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime
#SBATCH --output=$stdout
#SBATCH -e $stderr
#SBATCH -A $allocation
#SBATCH --partition=shared
#SBATCH --ntasks-per-node=1

$modules

$exe'''

KEELING_SUMMA_TEMPLATE='''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime
#SBATCH --output=$stdout
#SBATCH -e $stderr

$exe'''

logger_format = '%(asctime)-15s %(message)s'
logging.basicConfig(format = logger_format)
logger = logging.getLogger('cybergis')
logger.setLevel(logging.DEBUG)


USERNAME = os.environ['USER']
CONF_DIR = '.hpc_conf'
CONF_MOD = int('700', 8) # exclusive access
#ROGER_PRJ='/projects/class/jhub/users'
#JUPYTER_HOME='/mnt/jhub/users'
ROGER_PRJ = '/projects/jupyter'

HPC_PRJ = '~/projects/jupyter'
JUPYTER_HOME = os.path.expanduser('~')

#password security
def encrypt(plaintext):
    ciphertext = ''.join(chr(ord(x) ^ ord(y)) for (x,y) in zip(plaintext, cycle(hashlib.sha256(USERNAME).hexdigest())))
    return ciphertext.encode('base64')

def decrypt(ciphertext):
    ciphertext = ciphertext.decode('base64')
    return ''.join(chr(ord(x) ^ ord(y)) for (x,y) in zip(ciphertext, cycle(hashlib.sha256(USERNAME).hexdigest())))


def Labeled(label, widget):
    width='130px'
    return (Box([HTML(value='<p align="right" style="width:%s">%s&nbsp&nbsp</p>'%(width,label)),widget],
                layout=Layout(display='flex',align_items='center',flex_flow='row')))

def Title():
    return (Box([HTML(value='<h1>Welcome to SUMMA HTC</h1>')],
        layout=Layout(display='flex',align_items='center',flex_flow='row')
        ))

def listExeutables(folder='.'):
    executable = stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    return [filename for filename in os.listdir(folder)
        if os.path.isfile(filename)]# and (os.stat(filename).st_mode & executable)]



def listSummaOutput(folder='./output/'):
    executable = stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    return [filename for filename in os.listdir(folder + taskName)
             if os.path.isfile(filename)]


def tilemap(tif, name, overwrite=False, overlay=None,tilelvl=[9, 13]):
    id=hashlib.sha1(name).hexdigest()[:10]
    if overwrite:
        os.system('rm -rf %s'%id)
    os.system('gdal2tiles.py -e -z %d-%d -a 0,0,0 -s epsg:4326 -r bilinear -t "%s" %s -z 8-14 %s'%(tilelvl[0], tilelvl[1], name,tif,id))
    with open('%s/leaflet.html'%id) as input:
        s=input.read()
    s=s.replace('http://cdn.leafletjs.com','https://cdn.leafletjs.com')
    s=s.replace('http://{s}.tile.osm.org','https://{s}.tile.openstreetmap.org')
    addLayer='map.addLayer(lyr);'
    if overlay:
        os.system("wget 'https://raw.githubusercontent.com/calvinmetcalf/leaflet-ajax/master/dist/leaflet.ajax.min.js' -O %s/leaflet.ajax.min.js"%id)
        s=s.replace('leaflet.js"></script>','leaflet.js"></script>\n<script src="leaflet.ajax.min.js"></script>')

        vectorNewLayers = []
        vectorOverlay = []
        vectorAdd = []
        for vecFile,vecName in overlay:
            vecId=hashlib.sha1(vecName).hexdigest()[:10]
            os.system('ogr2ogr -f "geojson" %s/%s.json %s'%(id,vecId,vecFile))
            vectorNewLayers.append('var vecLayer%s = new L.GeoJSON.AJAX("%s.json");'%(vecId,vecId))
            vectorOverlay.append('"%s":vecLayer%s'%(vecName, vecId))
            vectorAdd.append('map.addLayer(vecLayer%s);'%vecId)

        s=s.replace('// Map','\n'.join(vectorNewLayers)+'\n // Map')
        s=s.replace('{"Layer": lyr}','{'+','.join(vectorOverlay)+', "Layer": lyr}')
        addLayer+='\n'.join(vectorAdd)

    s=s.replace(').addTo(map);',').addTo(map); '+addLayer)
    with open('%s/leaflet.html'%id,'w') as output:
        output.write(s)
    return IFrame('%s/leaflet.html'%id, width='1000',height='600')


class SummaHTC():

    def __init__(self, HOST_NAME="localhost", user_name="", task_name="",
                 workspace="./workspace", summafolder="./summatest",
                 jobName='sHTC', nTimes=10, nNodes=1, ppn=1, isGPU=False, walltime=10,
                 exe='date',snow_freeze_scale=50.0000, tempRangeTimestep=2.000, rootDistExp1=0.0, rootDistExp2=1.0,
                 k_soil1=1.0, k_soil2=100, qSurfScale1=1.0, qSurfScale2=100.0, summerLAI1=0.1,
                 summerLAI2=10.0, step1=1, step2=1, step3=1, step4=1, summaoption="simpleResistance"):
            
        if (HOST_NAME=="comet" or HOST_NAME=="Comet"):
            HOST_NAME = 'comet.sdsc.xsede.org'
        elif HOST_NAME.lower() == 'keeling':
            HOST_NAME = 'keeling.earth.illinois.edu'
        self.__client = paramiko.SSHClient()
        self.host = HOST_NAME
        self.host_userName = user_name or 'cigi-gisolve'  
        try:
            self.__client = paramiko.SSHClient()
            self.__client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        except Exception as e:
            logger.warn("error when create paramiko connection, caused by " + str(e))
            exit() 
        self.homeDir = workspace
        self.jobDir = self.homeDir + '/.jobs'
        self.jobName = jobName
        self.nNodes = nNodes
        self.nTimes = nTimes
        self.ppn = ppn
        self.isGPU = isGPU
        self.walltime = walltime
        self.userName = USERNAME
        self.jobStatus = None
        self.hpcRoot = HPC_PRJ
        self.hpcJobDir = self.hpcRoot + '/.jobs'
        self.relPath = os.path.relpath(os.getcwd(), self.homeDir)
        self.editMode = True


        self.num_times_exe = 1
        self.snow_freeze_scale = snow_freeze_scale
        self.tempRangeTimestep = tempRangeTimestep
        self.exe = 'for i in `seq '+ str(self.nTimes) + str(self.num_times_exe) + '`\ndo\nsingularity exec summa.simg ./runSummaTest.sh $i\ndone'

        self.jobId = None
        self.remoteSummaDir = None #"/home/%s/"%self.host_userName
    #self.summaFolder = "/home/%s/summatest"%self.host_userName
        #with open('/etc/jupyterhub/hub/Jupyter-xsede.summa.template') as input:
        #    self.job_template=Template(input.read())
        self.job_template=Template(SUMMA_TEMPLATE if self.host.startswith('comet') else KEELING_SUMMA_TEMPLATE)
        self.login()
        self.outputPath = os.path.abspath(os.path.join(workspace, "output"))
        self.summatestPath = os.path.abspath(summafolder)
        self.outputFiles = {}
        if not os.path.exists(self.outputPath):
            os.makedirs(self.outputPath)


    def login(self):
        if not os.path.exists(self.jobDir):
            os.makedirs(self.jobDir)
        login_success = False
        if (self.host_userName=='cigi-gisolve'):
            try:
                self.__client.connect(self.host, username=self.host_userName, key_filename='/opt/cybergis/.gisolve.key')
                self.__sftp=self.__client.open_sftp()
            except Exception as e:
                logger.warn("can not connect to server " + self.host + ", caused by " + str(e))
                exit()
            else:
                logger.info('Successfully logged in as %s'%self.host_userName)        
                login_success = True
                self.pw = None

        else:
            while not login_success:
                pw=getpass(prompt='Password')
                try:
                    self.__client.connect(self.host, username=self.host_userName, password=pw)
                    self.__sftp=self.__client.open_sftp()
                except Exception as e:
                    logger.warn("can not connect to server " + self.host + ", caused by " + str(e))
                    exit()
                else:
                    logger.info('Successfully logged in as %s'%self.host_userName)        
                    login_success = True
                    self.pw = pw
        #pw = ""
    
        # create projects folder in HPC
        #if 'exists' not in self.__runCommand("if [ -d ~/projects ]; then echo 'exists'; fi"):
        #    logger.warn("Please link projects folder in HPC " + self.host 
    #       +" to your home folder so that to ensure the parallel computation")
        #    exit()
        if 'exists' not in self.__runCommand("if [ -d " + HPC_PRJ + " ]; then echo 'exists'; fi"):
            self.__runCommand("mkdir "+ HPC_PRJ)
  
        moduleList = self.__runCommand("module avail 2>&1 | grep -v '/sw' | tr ' ' '\n' | sed '/^$/d' | sort") 

        self.module_avail = {_:_  for _ in moduleList.replace('(default)','').split() if _.count('-') < 3}
        self.m = self.module_avail
        self.modules = set()    
    # end of login

    def find_module(self, key):
        return [m for m in self.module_avail if key in m]
    
    def execute(self, cmd):
        self.exe=cmd
        return self
        
    def load_modules(self, *modules):
        for m in modules:
            if m not in self.module_avail:
                logger.warn('No such module %s in the host'%m)
                return
        self.modules.update(set(modules))
        return self
        
    def submit(self, preview=True, monitor=True):
        res = self.__submitUI(preview, monitor)
        return self
        #if (not preview) and (not monitor):
        #    return res

    def __runCommand(self, command):
        try:
            stdin,stdout,stderr = self.__client.exec_command(command)
        except Exception as e: 
            logger.warn("error when run command "+command + " caused by " + str(e))
            exit()
        return ''.join(stdout.readlines())+''.join(stderr.readlines())
    
    def __runCommandBlock(self, command):
        ans = ""
        try:
            stdin,stdout,stderr = self.__client.exec_command(command)
            while (not stdout.channel.exit_status_ready()):
                ans += stdout.read(1000).decode('utf-8')
        except Exception as e:
            logger.warn("error when run command " + command + " in blocking model, caused by " + str(e))
            exit()
        return ans
 
    def __submitUI(self, preview=True, monitor=True):
        fileList=listExeutables()
        arr = self.__runCommand("show_accounts | grep '%s' | awk '{print $2}' "%self.host_userName)
        locationList = []
        word = ""
        for char in arr:
            if (char=='\n'):
                locationList.append(word)
                word = ""
            else:
                word = word + char
        #locationList.append(word)


        if len(fileList) == 0:
            with open('test.sh','w') as output:
                output.write('#!/bin/bash\n\necho test')


        jobName=Text(value=self.jobName)
    #summaFolder = Text(value = self.summaFolder)
        entrance=Dropdown(
            options=fileList,
            value=fileList[0],
            layout=Layout()
        )

        location = Dropdown(
            options = locationList,
            value = locationList[0],
        )

        nTimes=BoundedIntText(
            value=self.nTimes,
            min=1,
            max=1000,
            step=1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='d',
            slider_color='white'
        )

        nNodes=IntSlider(
            value=self.nNodes,
            min=1,
            max=10,
            step=1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='d',
            slider_color='white'
        )
        ppn=IntSlider(
            value=self.ppn,
            min=1,
            max=20,
            step=1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='d',
            slider_color='white'
        )
        isGPU=Text(value = 'No GPU')
        num_times_exe = Text(value = str(self.num_times_exe))
        walltime=FloatSlider(
            value=float(self.walltime),
            min=1.0,
            max=48.0,
            step=1.0,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )
        Parameter = Text(value='')
        sfc=FloatSlider(
            value=float(self.snow_freeze_scale),
            min=50.0,
            max=500.0,
            step=10.0,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )

        trt=FloatSlider(
            value=float(self.tempRangeTimestep),
            min=2.0,
            max=10.0,
            step=1.0,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )

        rde=FloatRangeSlider(
            value=[0.1, 0.3],
            min=0.1,
            max=1.0,
            step=0.1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )

        s1=FloatSlider(
            value=0.1,
            min=0.1,
            max=1.0,
            step=0.1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )

        ks=FloatRangeSlider(
            value=[1.0, 3.0],
            min=1.0,
            max=100.0,
            step=1.0,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )

        s2=IntSlider(
            value=1.0,
            min=1.0,
            max=20.0,
            step=1.0,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='d',
            slider_color='white'
        )


        summa_option = widgets.Dropdown(
            options=['BallBerry',
                     'Jarvis',
                     'simpleResistance'],
            value='simpleResistance',
            disabled=False,
        )

        stomResist_cb_dict = {}
        for option in ['BallBerry', 'Jarvis', 'simpleResistance']:
            stomResist_cb_dict[option] = widgets.Checkbox(value=True, description=option, disabled=False)


        preview=Button(
            description='Preview Job script',
            button_style='', # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Preview Job'
        )

        jobview=Textarea(

            layout=Layout(width='500px',height='225px',max_width='1000px', max_height='1000px')
        #layout=Layout(width='0px',height='0px',max_width='0px', max_height='0px')

        )
        confirm=Button(
            description='Submit Job',
            button_style='', # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Submit job'
        )
        status=HTML(
            layout=Layout(width='850px',height='200px',max_width='1000px', min_height='200px', max_height='1000px')
        )
        refresh=Button(
            description='Refresh Status',
            disabled=True
        )
        cancel=Button(
            description='Cancel Job',
            disabled=True
        )
        newJob=Button(
            description='New Job',
            disabled=True
        )
        jobEdits = [jobName,entrance,nTimes,nNodes,ppn,isGPU,walltime, num_times_exe, confirm, location]

        postSubmission = [refresh, cancel]

        def switchMode():
            if not self.editMode:
                status.value = ''

            for w in jobEdits:
                w.disabled = self.editMode
            jobview.disabled = self.editMode

            self.editMode = not self.editMode
            for w in postSubmission:
                w.disabled = self.editMode

        def gen_summa_dir_name_old():

            #if self.remoteSummaDir is None:
            stdout = "Found\n"
            ans = "nothing"
            while (stdout == "Found\n"):
                ans = ("/home/" if self.host.startswith('comet') else '/data/keeling/a/')+ self.host_userName + "/summatest_" + str(random.randint(1,10000))
                stdout = self.__runCommandBlock("[ -d " + ans + " ] && echo 'Found'")
            self.remoteSummaDir = ans

            return self.remoteSummaDir

        def gen_summa_dir_name(job_id):

            # if self.remoteSummaDir is None:
            stdout = "Found\n"
            ans = "nothing"
            while (stdout == "Found\n"):
                ans = ("/home/" if self.host.startswith(
                    'comet') else '/data/keeling/a/') + self.host_userName + "/summatest_" + str(
                    random.randint(1, 10000))
                stdout = self.__runCommandBlock("[ -d " + ans + " ] && echo 'Found'")
            self.remoteSummaDir = ans

            return self.remoteSummaDir

        def upload_task(job_name, job_id, case_id=None):
            #gen_summa_dir_name()
            ans = "/home/" if self.host.startswith('comet') else '/data/keeling/a/'
            ans = os.path.join(ans, self.host_userName, "{}_{}".format(job_name, job_id))
            self.__runCommandBlock('mkdir -p ' + ans)
            if case_id is not None:
                ans = os.path.join(ans, str(case_id))
            self.remoteSummaDir = ans
            #self.exe = 'for i in `seq 1 ' + str(nTimes.value) +'`\ndo\nsingularity exec summa.simg bash -c "'+ ('' if self.host.startswith('comet') else 'cd %s && '%(self.remoteSummaDir.replace('/data/keeling/a/','/home/'))) + './installSummaTest.sh %d && ./runSummaTest.sh $i" &\ndone\n\nwait'%nTimes.value

            self.exe = 'singularity exec summa.simg bash -c "' + \
                        'cd %s && ' % (self.remoteSummaDir.replace('/data/keeling/a/', '/home/')) + \
                        './installSummaTest.sh %d"\n' % nTimes.value+ \
                       'for i in `seq 1 {}`\n'.format(str(nTimes.value)) + \
                        'do\n' +  \
                       'singularity exec summa.simg bash -c "cd %s &&' % (self.remoteSummaDir.replace('/data/keeling/a/', '/home/')) + \
                       './runSummaTest.sh $i"\n'.format(str(nTimes.value)) + \
                        'done\n' + \
                       'wait'

    # 'singularity exec summa.simg bash -c "' + \
    # 'cd %s && ' % (self.remoteSummaDir.replace('/data/keeling/a/', '/home/')) + \
    # 'for i in `seq 1 {}`\ndo\n./runSummaTest.sh $i\ndone"'.format(str(nTimes.value)) + \

            print (self.exe)


            output.value+='<br>Currently uploading the task</font>'
            output.value+=self.remoteSummaDir
            assert self.remoteSummaDir is not None
            ans = self.remoteSummaDir
            summaTestDirPath = self.summatestPath
            basename = os.path.basename(summaTestDirPath)
            basezip = shutil.make_archive(basename, 'zip', summaTestDirPath)
            output.value+='<br>Try to upload {} ==> {}</font>'.format(basezip, ans+'.zip')
            self.__sftp.put(basezip, ans+'.zip')

            output.value+='<br>Uploading the folder already</font>'

            self.__runCommandBlock('unzip ' + ans + '.zip -d ' + ans)
            self.__runCommandBlock('cp  /data/keeling/a/zhiyul/images/summa.simg ' + ans + '/summa.simg')
            self.__runCommandBlock('rm '+ ans + '.zip')
            output.value +='<br>Successfully uploading the task\n</font>'

        def click_preview(b):
            self.jobName = jobName.value
        #self.summaFolder = summaFolder.value
            self.nNodes = int(nNodes.value)
            self.isGPU = isGPU.value.lower().replace(' ','')=='gpu'
            self.ppn = int(ppn.value)
            self.walltime = int(float(walltime.value))
            self.num_times_exe = int(float(num_times_exe.value)) if num_times_exe.value.isdigit() else ''
            #gen_summa_dir_name()
            self.exe = 'for i in `seq 1 ' + str(nTimes.value) +'`\ndo\nsingularity exec summa.simg bash -c "'+ ('' if self.host.startswith('comet') else 'cd %s && '%(self.remoteSummaDir.replace('/data/keeling/a/','/home/'))) + './installSummaTest.sh %d && ./runSummaTest.sh $i" &\ndone\n\nwait'%nTimes.value
            self.Allocation = location.value

            jobview.value=self.job_template.substitute(
                  allocation = location.value,
                  jobname  = jobName.value,
                  n_times  = nTimes.value,
                  n_nodes  = int(nTimes.value/20+1),
                  is_gpu   = isGPU.value.lower().replace(' ',''),
                  ppn      = 20,
                  walltime = '00:%02d:00'%int(float(walltime.value)),
                  username = self.userName,
                  stdout   = '/home/'+self.host_userName+'/summatest/'+jobName.value+'.stdout',
                  stderr   = '/home/'+self.host_userName+'/summatest/'+jobName.value+'.stderr',
                  hpcPath  = self.hpcRoot,
                  modules  = 'module load singularity',#+' '.join(list(self.modules)),
                  exe      = self.exe

           )
        #click_preview(1)
        #preview.on_click(click_preview)
        output=widgets.HTML(value="<p style='font-family:Courier'><font color='blue'>")

        for w in jobEdits:
            w.observe(click_preview, names='value')

        def refreshStatus(b, jobstatus, jobId):
            if jobId is None:
             #   status.value='<pre><font size=2>%s</font></pre>'%('\n'*8)
                return

            result = self.__runCommand('date; qstat -a %s | sed 1,3d '%jobId)
            self.startTime = 0

            if 'Unknown Job Id Error' in result:
                result = 'Job %s finished'%jobId
                est_time= '\n'*7

            else:
                currentStatus=result[-8]
                if jobStatus == 'queuing' and currentStatus == 'R':
                    jobStatus = 'running'
                    startTime = time.time()
                    queueTime = self.startTime - self.submissionTime
                    #output.value+='<br>Job %s started after queuing for %.1fs'%(self.jobId,self.queueTime)
                    output.value+='<br>Job Running'
                if currentStatus == 'C':
                    jobStatus = 'finished'
                    result = 'Job %s finished'%self.jobId
                    est_time= '\n'*7
                    #self.endTime=time.time()
                    #self.runTime=(self.endTime-self.startTime) if self.startTime > 0 else 0
                    #output.value+='<br>Job %s finished after running for %.1fs.'%(self.jobId, self.runTime)
                    #output.value+='<br>Total walltime spent: %.1fs</font>'%(self.queueTime+self.runTime)
                    output.value+='<br>Preparing for the result:</font>'
                    output.value+='<br>Loading: </font>'

            status.value='<pre><font size=2>%s\n</font></pre>'%(result)

        #refreshStatus(1, jobstatus)
        #refresh.on_click(refreshStatus)

        def downloadFile(localPath, remotePath, filename):
            output.value+="Downloading File"
            output.value+=filename
            if not os.path.exists(localPath):
                os.makedirs(localPath)
                self.__sftp.get(remotePath, localPath+filename)#, lambda a,b : print(a,b) )

        def recursive_download(localPath, remotePath):
            fs= self.__runCommandBlock("ls " + remotePath)

            for f in fs.split('\n'):
                f.strip('\n')
                if not f:
                    continue
                nextRemotePath = remotePath + '/' + f
                nextLocalPath = localPath + '/' + f
                if 'file!' in self.__runCommandBlock("if [ -f " + nextRemotePath + " ]; then echo 'file!'; fi"):
                    output.value+='#'#'<br>Going to download the file %s</font>'%(remotePath)
                    downloadFile(nextLocalPath, nextRemotePath, f)
                    continue;
                else:
                    if os.path.exists(nextLocalPath):
                        shutil.rmtree(nextLocalPath)
                    os.makedirs(nextLocalPath)
                    recursive_download(nextLocalPath, nextRemotePath)

        q = queue.Queue()
        def update_remote_jobs_status(host, user, pw, param_trail_LofD):
            comm_obj = SSHComm(host, user, pw)
            while True:
                jobId_remote_list = []
                for item in param_trail_LofD:
                    if "id_remote" in item:
                        jobId_remote_list.append(str(item['id_remote']))
                jobIds_str = ' '.join(jobId_remote_list)
                if jobIds_str:
                    result = comm_obj.runCommand('date; qstat -a %s | sed 1,3d ' % jobIds_str)
                    status.value = '<pre><font size=2>%s\n</font></pre>' % (result)
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                else:
                    q.task_done()
                    break
                time.sleep(1)

        def monitorDeamon(host, user, pw, jobStatus,
                          jobId_remote, jobId_local, jobId_htc,
                          outputPath, jobName, remoteSummaDir, interval=1):

            comm_obj = SSHComm(host, user, pw)
            while jobStatus != 'finished':
                time.sleep(interval)

                result = comm_obj.runCommand('date; qstat -a %s | sed 1,3d ' % jobId_remote)
                self.startTime = 0

                if 'Unknown Job Id Error' in result:
                    result = 'Job %s finished' % jobId_remote
                    est_time = '\n' * 7
                else:
                    currentStatus = result[-8]
                    if jobStatus == 'queuing' and currentStatus == 'R':
                        jobStatus = 'running'
                        startTime = time.time()
                        queueTime = self.startTime - self.submissionTime
                        # output.value+='<br>Job %s started after queuing for %.1fs'%(self.jobId,self.queueTime)
                        output.value += '<br>Job Running'
                    if currentStatus == 'C':
                        jobStatus = 'finished'
                        result = 'Job %s finished' % jobId_remote
                        est_time = '\n' * 7
                        # self.endTime=time.time()
                        # self.runTime=(self.endTime-self.startTime) if self.startTime > 0 else 0
                        # output.value+='<br>Job %s finished after running for %.1fs.'%(self.jobId, self.runTime)
                        # output.value+='<br>Total walltime spent: %.1fs</font>'%(self.queueTime+self.runTime)
                        output.value += '<br>Preparing for the result:</font>'
                        output.value += '<br>Loading: </font>'

                #status.value = '<pre><font size=2>%s\n</font></pre>' % (result)

            # sleep for 5s to wait I/O flushing
            time.sleep(5)
            output_files = os.path.join(outputPath, "{}_{}".format(jobName, jobId_htc), "{}_{}".format(jobId_local, jobId_remote))
            #if os.path.exists(output_files):
            #    shutil.rmtree(output_files)
            os.makedirs(output_files)
            output.value += '<br>Downloading outputs from %s to %s</br>' % (remoteSummaDir, output_files)

            ## got strange "Premission Denied" issue on err file
            #comm_obj.downloadFile(output_files, "/{}.stderr".format(jobName), remoteSummaDir, "out.stderr",)
            #comm_obj.downloadFolder(output_files, remoteSummaDir + "/summaTestCases/output")

            #zip up remote folder
            remote_zip_target_folder_path = os.path.join(remoteSummaDir, "summaTestCases/output/output1")
            remote_zip_f_path = "{}_{}.zip".format(remoteSummaDir, jobId_remote)
            local_zip_f_path = output_files+".zip"
            comm_obj.runCommandBlock('cd {}; zip -r {} ./'.format(remote_zip_target_folder_path, remote_zip_f_path))
            comm_obj.sftp.get(remote_zip_f_path, local_zip_f_path)

            with zipfile.ZipFile(output_files+".zip", "r") as zip_ref:
                zip_ref.extractall(output_files)

            comm_obj.sftp.get(remoteSummaDir + "/{}.stdout".format(jobName), output_files + "/out.stdout")
            os.remove(local_zip_f_path)
            comm_obj.runCommandBlock('rm -rf {}'.format(remote_zip_f_path))

            output.value += '<br>The output should be in your Jupyter <a href="output/">login folder</a></font>'
            #   filesSelector = FileBrowser(output_files)
            #   display(filesSelector.widget())
            #   out_file_path = filesSelector.getPath()
            #   while(os.path.isdir(out_file_path)):
            #      out_file_path = filesSelector.getPath()

            #    logger.info(out_file_path)
            # test = summaVis("output/"+ self.jobName+ "/ouput1/syntheticTestCases/colbeck1976/colbeck1976-exp1_1990-01-01-00_spinup_testSumma_1.nccolbeck1976-exp1_1990-01-01-00_spinup_testSumma_1.nc")
            # test = summaVis("output/Test/ouput1/syntheticTestCases/colbeck1976/colbeck1976-exp1_1990-01-01-00_spinup_testSumma_1.nccolbeck1976-exp1_1990-01-01-00_spinup_testSumma_1.nc")
            # test.attrPlot('scalarRainPlusMelt')
            # self.__client.exec_command("rm -r " + remoteSummaDir)
            switchMode()

        def replaceAll(file, searchExp, replaceExp):
            for line in fileinput.input(file, inplace=1):
                if searchExp in line:
                    line = replaceExp
                sys.stdout.write(line)

        def replaceFlagInTextFile(file, searchExp, replaceExp):
            for line in fileinput.input(file, inplace=1):
                if searchExp in line:
                    line = replaceExp
                sys.stdout.write(line)

        def generate_param_trail_LofD_from_UI():
            # param_trail_list_of_dict

            def __get_numeric_range(min, max, step, factor=1, to_list=True):
                r = np.arange(min, max, step)
                if max not in r:
                    r = np.append(r, max)
                return r * factor if not to_list else (r * factor).tolist()

            def __combination_of_parameters(parameter_trail_dict, add_id=True):
                """
                See: https://codereview.stackexchange.com/questions/171173/list-all-possible-permutations-from-a-python-dictionary-of-lists
                :param parameter_trail_dict: {"param_A": [1, 2],
                                              "param_B": ["B1", "B2", "B3"],
                                              "param_C": [10.0, 10.1]
                                             }
                :return:[{'param_A': 1, 'param_B': 'B1', 'param_C': 10.0}
                        {'param_A': 1, 'param_B': 'B1', 'param_C': 10.1}
                        {'param_A': 1, 'param_B': 'B2', 'param_C': 10.0}
                        {'param_A': 1, 'param_B': 'B2', 'param_C': 10.1}
                        {'param_A': 1, 'param_B': 'B3', 'param_C': 10.0}
                        {'param_A': 1, 'param_B': 'B3', 'param_C': 10.1}
                        {'param_A': 2, 'param_B': 'B1', 'param_C': 10.0}
                        {'param_A': 2, 'param_B': 'B1', 'param_C': 10.1}
                        {'param_A': 2, 'param_B': 'B2', 'param_C': 10.0}
                        {'param_A': 2, 'param_B': 'B2', 'param_C': 10.1}
                        {'param_A': 2, 'param_B': 'B3', 'param_C': 10.0}
                        {'param_A': 2, 'param_B': 'B3', 'param_C': 10.1}]
                """
                from itertools import product
                experiments = [dict(zip(parameter_trail_dict.keys(), value)) for value in
                               product(*parameter_trail_dict.values())]
                if add_id:
                    for i in range(len(experiments)):
                        experiments[i]['id'] = i
                return experiments

            parameter_trail_dict = {}
            # rootDistExp
            min_para = min(rde.value[0], rde.value[1])
            max_para = max(rde.value[0], rde.value[1])
            delta = s1.value
            parameter_trail_dict["rootDistExp"] = __get_numeric_range(min_para, max_para, delta)
            print(parameter_trail_dict["rootDistExp"])

            # k_soil
            min_para_2 = min(ks.value[0], ks.value[1])
            max_para_2 = max(ks.value[0], ks.value[1])
            delta_2 = s2.value
            parameter_trail_dict["k_soil"] = __get_numeric_range(min_para_2, max_para_2, delta_2, factor=0.01)
            print(parameter_trail_dict["k_soil"])

            # stomResist
            #parameter_trail_dict.append({"stomResist": ["simpleResistance", "Jarvis", "BallBerry"]})
            #parameter_trail_dict["stomResist"] = [summa_option.value]
            parameter_trail_dict["stomResist"] = []
            for k,v in stomResist_cb_dict.items():
                if v.value:
                    parameter_trail_dict["stomResist"].append(v.description)
            print(parameter_trail_dict["stomResist"])

            # combination
            param_trail_LofD = __combination_of_parameters(parameter_trail_dict)

            return param_trail_LofD

        def write_single_testcase(_param_dict):
            # Param_Trial.nc
            filepath = './summatest/summaTestCases/settings_org/wrrPaperTestCases/figure07/summa_zParamTrial_riparianAspen.nc'
            with nc.Dataset(filepath, 'r+') as Param_Trial:
                for k in ['rootDistExp', 'k_soil']:
                    Param_Trial.variables[k][:] = _param_dict[k]

            # Decision file
            summaoptionfilename = os.path.join(self.summatestPath,
                                               'summaTestCases/settings_org/wrrPaperTestCases/figure07/summa_zDecisions_riparianAspenSimpleResistance.txt')
            stomResist_value = _param_dict['stomResist']
            # simpleResistance, BallBerry, Jarvis
            stomResist_flag_template = "stomResist"
            stomResist_flag_value = "stomResist                      {stomResist}       ! (06) choice of function for stomatal resistance\n".format(stomResist=stomResist_value)
            replaceFlagInTextFile(summaoptionfilename, stomResist_flag_template, stomResist_flag_value)
            pass

        param_trail_LofD = []

        def submit(b):
            uuid4_str = str(uuid.uuid4())[:8]
            now_utc = datetime.utcnow()
            #jobid_htc = "{}_{}_{}".format(now_utc.strftime("utc%Y%m%d-%H%M%S"), str(int(now_utc.timestamp())), uuid4_str)
            jobid_htc = str(int(now_utc.timestamp()))

            global param_trail_LofD
            param_trail_LofD = generate_param_trail_LofD_from_UI()

            for item in param_trail_LofD:
                item["id_htc"] = jobid_htc
                print(item)

            t_update_remote_jobs_status = Thread(target=update_remote_jobs_status,
                                                 args=(self.host, self.host_userName, self.pw, param_trail_LofD))
            t_update_remote_jobs_status.start()
            monitorDeamon_thread_pool = []

            for param_trail_D in param_trail_LofD:
                write_single_testcase(param_trail_D)
                upload_task(self.jobName, jobid_htc, case_id=param_trail_D["id"])
                jobview.value = self.job_template.substitute(
                    allocation=location.value,
                    jobname="{}_{}_{}".format(jobName.value, jobid_htc, str(param_trail_D["id"])),
                    n_times=nTimes.value,
                    n_nodes=int(nTimes.value / 20 + 1),
                    is_gpu=isGPU.value.lower().replace(' ', ''),
                    ppn=20,
                    walltime='00:%02d:00' % int(float(walltime.value)),
                    username=self.userName,
                    stdout=self.remoteSummaDir + "/" + jobName.value + '.stdout',
                    stderr=self.remoteSummaDir + "/" + jobName.value + '.stderr',
                    hpcPath=self.hpcRoot,
                    modules='module load singularity',  # +' '.join(list(self.modules)),
                    exe=self.exe
                )
                filename = '%s.sh' % jobName.value
                with open(self.jobDir + '/' + filename, 'w') as out:
                    out.write(jobview.value)
                self.pbs = self.jobDir + '/' + filename
                self.__sftp.put(self.pbs, self.remoteSummaDir + '/run.qsub')
                self.jobId = self.__runCommand('cd ' + self.remoteSummaDir + ' && ' + (
                    'qsub' if self.host.startswith('comet') else 'sbatch') + ' run.qsub').strip().split(' ')[-1]
                param_trail_D['id_remote'] = self.jobId
                if ('ERROR' in self.jobId or 'WARN' in self.jobId):
                    output.value += '<br>Error submitting the task\n</font>'
                    logger.warn('submit job error: %s' % self.jobId)
                    exit()

                self.submissionTime = time.time()
                self.jobStatus = 'queuing'
                switchMode()
                t = Thread(target=monitorDeamon, args=(self.host, self.host_userName, self.pw, 'queuing',
                                                       param_trail_D['id_remote'], param_trail_D['id'], jobid_htc,
                                                       self.outputPath, self.jobName, self.remoteSummaDir))
                t.start()
                monitorDeamon_thread_pool.append(t)

            for item in param_trail_LofD:
                print(item)
            for t in monitorDeamon_thread_pool:
                t.join()
            q.put(1)
            t_update_remote_jobs_status.join()
            with open('./jobs_info.json', 'w') as outfile:
                json.dump(param_trail_LofD, outfile)
            print("HTC run done; Jobs info saved to ./jobs_info.json")
            pass

        def submit_old(b):

            summaoptionfilename=os.path.join(self.summatestPath,
                                            'summaTestCases/settings_org/wrrPaperTestCases/figure07/summa_zDecisions_riparianAspenSimpleResistance.txt')
            curr_opt = summa_option.value
            # 1: BallBerry 2: Jarvis 3:simpleResistance

            summasearchEXP = "stomResist"

            firstexp = "stomResist                      BallBerry       ! (06) choice of function for stomatal resistance\n"
            secondexp = "stomResist                      Jarvis          ! (06) choice of function for stomatal resistance\n"
            thirdexp = "stomResist                      simpleResistance ! (06) choice of function for stomatal resistance\n"

            print("My option is")
            print(curr_opt)
            if curr_opt==1:
                print("I am BallBerry")
                replaceAll(summaoptionfilename, summasearchEXP, firstexp)
            if curr_opt==2:
                print("I am Jarvis")
                replaceAll(summaoptionfilename, summasearchEXP, secondexp)
            if curr_opt==3:
                print("I am simpleResistance")
                replaceAll(summaoptionfilename, summasearchEXP, thirdexp)

            #temp = trt.value
            #snow_freeze_scale = sfc.value
            #tempRangeTimestepmid = str(temp)+"000"
            #tempRangeTimestepmin = str(-0.0625*temp+0.625)+"000"
            #tempRangeTimestepmax = str(11.875*temp-18.75)+"000"
            #target_str = "tempRangeTimestep         |       "+str(tempRangeTimestepmid)+" |       "+str(tempRangeTimestepmin)+" |    "+str(tempRangeTimestepmax)+"\n"

            #replaceAll("/opt/cybergis/summatest/summaTestCases/settings_org/syntheticTestCases/colbeck1976/summa_zLocalParamInfo.txt", "snowfrz_scale", "snowfrz_scale             |      "+str(snow_freeze_scale)+"000 |      10.0000 |    1000.0000\n")
            #replaceAll("/opt/cybergis/summatest/summaTestCases/settings_org/syntheticTestCases/colbeck1976/summa_zLocalParamInfo.txt", "tempRangeTimestep", "tempRangeTimestep         |       "+str(tempRangeTimestepmid)+" |       "+str(tempRangeTimestepmin)+" |    "+str(tempRangeTimestepmax)+"\n")


            #output.value += '<br>What we got here is '+str(rde.value[0])+' '+str(rde.value[1])+'\n</font>'

            #x1 = math.floor(abs(rde.value[0]-rde.value[1])/s1.value)+1
            #x2 = math.floor(abs(ks.value[0]-ks.value[1])/s2.value)+1
            #x3 = math.floor(abs(qss.value[0]-qss.value[1])/s3.value)+1
            #x4 = math.floor(abs(sla.value[0]-sla.value[1])/s4.value)+1

            #output.value += '<br>Number of Task is '+str(int(x1*x2*x3*x4))+'\n</font>'

            output.value += '<br>Hello ya\n</font>'
            filepath='./summatest/summaTestCases/settings_org/wrrPaperTestCases/figure07/summa_zParamTrial_riparianAspen.nc'
            Param_Trial = nc.Dataset(filepath,'r+')
            output.value += '<br>Hello ya ya\n</font>'
            name_value = Param_Trial.variables['rootDistExp'][:]
            name_value_2=Param_Trial.variables['k_soil'][:]
            #Param_Trial
            min_para = min(rde.value[0],rde.value[1])
            max_para = max(rde.value[0],rde.value[1])
            delta = s1.value

            min_para_2= min(ks.value[0],ks.value[1])
            max_para_2= max(ks.value[0],ks.value[1])
            delta_2 = s2.value

            for i in np.arange(min_para, max_para+delta, delta):
                for j in np.arange(min_para_2, max_para_2+delta_2, delta_2):

                    name_value[0]=i
                    name_value_2[0]=j*0.0000001
                    if i > max_para:
                        i = max_para
                    if j > max_para_2:
                        j = max_para_2*0.0000001
                    Param_Trial = nc.Dataset(filepath,'r+')
                    Param_Trial.variables['rootDistExp'][:] = name_value
                    Param_Trial.variables['k_soil'][:] = name_value_2

                    output.value += '<br>Finish tuning the parameter & Uploading the task\n</font>'
                #output.value += '<br>Waiting in the queue\n</font>'
                    upload_task()
                    filename = '%s.sh'%jobName.value

                    jobview.value=self.job_template.substitute(
                        allocation = location.value,
                        jobname  = jobName.value,
                        n_times  = nTimes.value,
                        n_nodes  = int(nTimes.value/20+1),
                        is_gpu   = isGPU.value.lower().replace(' ',''),
                        ppn      = 20,
                        walltime = '00:%02d:00'%int(float(walltime.value)),
                        username = self.userName,
                        stdout   = self.remoteSummaDir + "/" + jobName.value + '.stdout',
                        stderr   = self.remoteSummaDir + "/" + jobName.value + '.stderr',
                        hpcPath  = self.hpcRoot,
                        modules  = 'module load singularity',#+' '.join(list(self.modules)),
                        exe      = self.exe
                    )

                    #self.nTimes=int(x1*x2*x3*x4)
                    output.value += '<br>Installing the task\n</font>'
                    output.value += '<br>'
                    #for loop in range(0, int(x1*x2*x3*x4)):
                    #    output.value+='*'

                    with open(self.jobDir + '/' + filename,'w') as out:
                        out.write(jobview.value)
                    self.pbs = self.jobDir + '/' + filename
                    self.__sftp.put(self.pbs, self.remoteSummaDir + '/run.qsub')
                    output.value += '<br>the current folder is</font>'
                    output.value += self.remoteSummaDir
                    #print(self.__runCommandBlock('cd ' + self.remoteSummaDir + ' && bash ./installSummaTest.sh '+ str(nTimes.value)))
                    self.jobId = self.__runCommand('cd '+ self.remoteSummaDir + ' && '+ ('qsub' if self.host.startswith('comet') else 'sbatch') + ' run.qsub').strip().split(' ')[-1]
                    if ('ERROR' in self.jobId or 'WARN' in self.jobId):
                        output.value += '<br>Error submitting the task\n</font>'
                        logger.warn('submit job error: %s'%self.jobId)
                        exit()
                    output.value += '<br>I am here</font>'
                    self.submissionTime=time.time()
                    self.jobStatus = 'queuing'
                    #output.value+='<br>Job %s submitted at %s \n</font>'%(self.jobId,time.ctime())
                    switchMode()

                    t = Thread(target=monitorDeamon, args=(self.host, self.host_userName, self.pw,
                                                          self.jobStatus, self.jobId, self.outputPath,
                                                          self.jobName, self.remoteSummaDir))
                    t.start()


                #monitorDeamon()

        confirm.on_click(submit)

        def click_cancel(b):
            if self.jobId:
                self.__runCommand('qdel %s'%self.jobId)
            switchMode()

        cancel.on_click(click_cancel)

        def click_newJob(b):
            switchMode()

        newJob.on_click(click_newJob)
        submitForm=VBox([
            Title(),
            #Labeled('Allocation', location),
                #Labeled('Job name', jobName),
            #Labeled('No. Times', nTimes),
                #Labeled('Executable', entrance),
                #Labeled('No. nodes', nNodes),
                #Labeled('Cores per node', ppn),
                #Labeled('GPU needed', isGPU),
            Labeled('Walltime (min)', walltime),
            Labeled('rootDistExp',rde),
            Labeled('step',s1),
            Labeled('k_soil, *e-7',ks),
            Labeled('step, *e-7',s2),
            #Labeled('SUMMA options',summa_option),
            Labeled('stomResist Options', VBox([v for k,v in stomResist_cb_dict.items()])),
            #Labeled('step',s3),
            #Labeled('summerLAI',sla),
            #Labeled('step',s4),
            #Labeled('Snow freeze scale', sfc),
            #Labeled('Temperture Range Timestep', trt),
        #Labeled('Times to execute', num_times_exe),
                #Labeled('Job script', jobview),
            Labeled('', confirm)
        ])
        statusTab=VBox([
                Labeled('Job Status', status),
                Labeled('', HBox([refresh,cancel])),
        ])

        if not preview:
            submit(1)

        #display(Tab([submitForm, statusTab], _titles={0: 'Submit New Job', 1: 'Check Job Status'}))
        if not preview:
            if monitor:
                display(VBox([
                    Labeled('Job script', jobview),
                    VBox([
                        Labeled('Job Status', status),
                        Labeled('', HBox([refresh,cancel])),
                    ])
                ]))
        else:
            display(VBox([submitForm, statusTab]))

        display(output)
            
    def listRunning(self, user=USERNAME, hideUI=False):
        header=HTML(
            layout=Layout(width='800px',max_width='1000px', 
                          min_width='50px', max_height='1000px')
        )
        status=SelectMultiple(
            layout=Layout(width='850px',height='125px',max_width='1000px', 
                          min_width='800px', min_height='125px', max_height='1000px')
        )
        refresh=Button(
            description='Refresh Status',
            disabled=False
        )
        cancel=Button(
            description='Cancel Job',
            disabled=False
        )        
        
        def refreshStatus(b):
            #status.value='<pre>'+self.__runCommand('date; qstat  | awk \'NR < 3 || /%s/\''%(self.username))+'</pre>'
            result = self.__runCommand("qstat | sed -n '1,2p;/%s/p'" % user)
            header.value='<pre>%s</pre>'%result
            self.runningIds = [_.split()[0] for _ in result.strip().split('\n')[2:]]
            #status.options = [_.split()[0] for _ in result.strip().split('\n')[2:]]
            
        refreshStatus(1)
        refresh.on_click(refreshStatus)
        
        def click_cancel(b):
            output.value = ''
            #self.__runCommand('qdel %s'%status.value[0].split()[0])
        
        cancel.on_click(click_cancel)
        
        if not hideUI:
            display(
                VBox([
                    header,
                    #HBox([status,header]),
                    #status,
                    HBox([refresh, cancel])
                ])
            )
        else:
            return self.runningIds
        
    def cancel(self, jobIds):
        if isinstance(jobIds, str):
            self.__runCommand('qdel %s'%jobIds)
        elif isinstance(jobIds, list):
            self.__runCommand('qdel %s'%' '.join(jobIds))
    
    #def showDetail(self, jobId): # Not handling large output
    #    print(self.__runCommand('qstat -f %s'%jobId))


class JobsInfo(object):

    def __init__(self, jobs_info_json_path, workspace_path):
        self._df = self._parse_jobs_json(jobs_info_json_path)
        self._workspace_path = os.path.abspath(workspace_path)
        self._df.insert(len(self._df.columns), 'folder', '')
        for index, row in self._df.iterrows():
            self._df.loc[index, 'folder'] = os.path.join(self._workspace_path,
                                                         "output",
                                                         "sHTC_{}".format(row.id_htc),
                                                         "{}_{}".format(row.id, row.id_remote))

    def _parse_jobs_json(self, jobs_info_json_path):
        df = pd.read_json(jobs_info_json_path)
        return df

    def query_job(self, query_dict):

        query_str_list = []
        for k, v in query_dict.items():
            if type(v) is str:
                query_str_list.append(f'{k}=="{v}"')
            else:
                query_str_list.append(f'{k}=={v}')
        query_str = ' & '.join(query_str_list)
        print(query_str)
        return self._df.query(query_str)

    def get_nc_path(self, _df, nc_rpath):
        #"wrrPaperTestCases/figure07/vegImpactsTranspire_output_simpleResistance_timestep.nc"
        nc_list = []
        for index, row in _df.iterrows():
            p = os.path.join(row.folder,
                             nc_rpath)

            nc_list.append(p)
        return nc_list

    def get_nc_path_by_query(self, query_dict, nc_rpath):
        return self.get_nc_path(self.query_job(query_dict), nc_rpath)

