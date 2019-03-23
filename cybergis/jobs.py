#!/usr/bin/env python
from __future__ import print_function
import warnings
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

#from FileBrowser import FileBrowser
# logger configuration 

logger_format = '%(asctime)-15s %(message)s'
logging.basicConfig(format = logger_format)
logger = logging.getLogger('cybergis')
logger.setLevel(logging.DEBUG)


USERNAME = os.environ['USER']
CONF_DIR='.hpc_conf'
CONF_MOD=int('700', 8) # exclusive access
#ROGER_PRJ='/projects/class/jhub/users'
#JUPYTER_HOME='/mnt/jhub/users'
ROGER_PRJ='/projects/jupyter'

HPC_PRJ = '~/projects/jupyter'
JUPYTER_HOME=os.path.expanduser('~')

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

def listExeutables(folder='.'):
    executable = stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    return [filename for filename in os.listdir(folder)
        if os.path.isfile(filename)]# and (os.stat(filename).st_mode & executable)]


def listSummaOutput(folder='./output/'):
    executable = stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    return [filename for filename in os.listdir(folder + taskName)
             if os.path.isfile(filename)]


def tilemap(tif, name, overwrite=False, overlay=None,tilelvl=[9,13]):
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

class Job():
    def __init__(self,HOST_NAME="localhost", user_name = USERNAME, task_path="" ,jobName='Test',nTimes=1,
        nNodes=1,ppn=1,isGPU=False,walltime=1,exe='date'):
        self.__client = paramiko.SSHClient()
        self.host = HOST_NAME
        self.host_userName = user_name
        try:
            self.__client = paramiko.SSHClient()
            self.__client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        except Exception as e:
            logger.warn("error when create paramiko connection, caused by " + e.message)
            exit() 
        self.homeDir = JUPYTER_HOME
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
        self.ext = 'for i in `seq '+ str(self.nTimes)  + str(self.num_times_exe) + '`\ndo\nsingularity exec summa.simg ./runSummaTest.sh $i\ndone'

        self.jobId = None
        self.remoteSummaDir = "/home/%s/"%self.host_userName
        #self.summaFolder = "/home/%s/summatest"%self.host_userName
        with open('/etc/jupyterhub/hub/Jupyter-xsede.summa.template') as input:
            self.job_template=Template(input.read())
        self.login()
        self.outputPath="./output"
        self.outputFiles = {}
        if not os.path.exists(self.outputPath):
            os.makedirs(self.outputPath)

    def login(self):
        if not os.path.exists(self.jobDir):
            os.makedirs(self.jobDir)
        
        login_success = False
        while not login_success:
            pw=getpass(prompt='Password')
            try:
                self.__client.connect(self.host, username=self.host_userName, password=pw)
                self.__sftp=self.__client.open_sftp()
            except Exception as e:
                logger.warn("can not connect to server " + self.host + ", caused by " + e.message)
                exit()
            else:
                logger.info('Successfully logged in as %s'%self.host_userName)        
                login_success = True
        pw = ""
    
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
        
    def submit(self,preview=True, monitor=True):
        res=self.__submitUI(preview,monitor)
        return self
        #if (not preview) and (not monitor):
        #    return res

    def __runCommand(self, command):
        try:
            stdin,stdout,stderr = self.__client.exec_command(command)
        except Exception as e: 
            logger.warn("error when run command "+command + " caused by " + e.message)
            exit()
        return ''.join(stdout.readlines())+''.join(stderr.readlines())
    
    def __runCommandBlock(self, command):
        ans = ""
        try:
            stdin,stdout,stderr = self.__client.exec_command(command)
            while (not stdout.channel.exit_status_ready()):
                ans += stdout.read(1000)
        except Exception as e:
            logger.warn("error when run command " + command + " in blocking model, caused by " + e.message)
            exit()
        return ans
 
    def __submitUI(self, preview=True, monitor=True):
        fileList=listExeutables()
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
        isGPU=RadioButtons(
            options=['No GPU','GPU'],
            value = 'GPU' if self.isGPU else 'No GPU'
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
        jobEdits = [jobName,entrance,nTimes,nNodes,ppn,isGPU,walltime, num_times_exe, confirm]

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
                            
        
        def click_preview(b):
            self.jobName = jobName.value
            #self.summaFolder = summaFolder.value
            self.nNodes = int(nNodes.value)
            self.isGPU = isGPU.value.lower().replace(' ','')=='gpu'
            self.ppn = int(ppn.value)
            self.walltime = int(float(walltime.value))
            self.num_times_exe = int(float(num_times_exe.value)) if num_times_exe.value.isdigit() else '' 
            self.exe = 'for i in `seq 1 ' + str(nTimes.value) +'`\ndo\nsingularity exec summa.simg ./runSummaTest.sh $i &\ndone\n wait'
            
            jobview.value=self.job_template.substitute(

                  jobname  = jobName.value, 
                  n_nodes  = nNodes.value, 
                  is_gpu   = isGPU.value.lower().replace(' ',''),
                  ppn      = ppn.value,
                  walltime = '%d:00:00'%int(float(walltime.value)), 
                  username = self.userName, 
                  stdout   = '/home/'+self.host_userName+'/summatest/'+jobName.value+'.stdout',
                  stderr   = '/home/'+self.host_userName+'/summatest/'+jobName.value+'.stderr',
                  hpcPath  = self.hpcRoot,
                  modules  = 'module load singularity',#+' '.join(list(self.modules)),
                  exe      = self.exe
         
            )
        click_preview(1)
        preview.on_click(click_preview)    
        output=widgets.HTML(value="<p style='font-family:Courier'><font color='blue'>")
        
        for w in jobEdits:
            w.observe(click_preview, names='value')
  
        def refreshStatus(b):
            if self.jobId is None:
             #   status.value='<pre><font size=2>%s</font></pre>'%('\n'*8)
                return
            
            result = self.__runCommand('date; qstat -a %s | sed 1,3d '%self.jobId)                
            
            if 'Unknown Job Id Error' in result:
                result = 'Job %s is finished'%self.jobId
                est_time= '\n'*7
                
            else:
                currentStatus=result[-8]
                if self.jobStatus == 'queuing' and currentStatus == 'R':
                    self.jobStatus = 'running'
                    self.startTime = time.time()
                    self.queueTime = self.startTime - self.submissionTime
                    output.value+='<br>Job %s started after queuing for %.1fs'%(self.jobId,self.queueTime)
                if currentStatus == 'U':
                    self.jobStatus = 'finished'
                    result = 'Job %s is finished'%self.jobId
                    est_time= '\n'*7
                    self.endTime=time.time()
                    self.runTime=self.endTime-self.startTime
                    output.value+='<br>Job %s finished after running for %.1fs.'%(self.jobId, self.runTime)
                    output.value+='<br>Total walltime spent: %.1fs</font>'%(self.queueTime+self.runTime)
            
            status.value='<pre><font size=2>%s\n</font></pre>'%(result)
            
        refreshStatus(1)
        refresh.on_click(refreshStatus)
        
        def downloadFile(localPath, remotePath, filename):
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
                    output.value+='<br>Going to download the file %s</font>'%(remotePath)
                    downloadFile(nextLocalPath, nextRemotePath, f)
                    continue;
                else:
                    if os.path.exists(nextLocalPath):
                        shutil.rmtree(nextLocalPath)
                    os.makedirs(nextLocalPath)
                    recursive_download(nextLocalPath, nextRemotePath)
               
        def monitorDeamon(interval=1):
            while self.jobStatus!='finished':
                time.sleep(interval)
                refreshStatus(1)
            
            output_files = self.outputPath+"/" + self.jobName
            if os.path.exists(output_files):
                shutil.rmtree(output_files)
            os.makedirs(output_files)
            self.__sftp.get(self.remoteSummaDir + "/Test.stdout", output_files+"/out.stdout")
            recursive_download (output_files, self.remoteSummaDir + "/summaTestCases/output")
            output.value+='<br>The output should be in your Jupyter login folder</font>' 
         #   filesSelector = FileBrowser(output_files)
         #   display(filesSelector.widget())
     #   out_file_path = filesSelector.getPath()
         #   while(os.path.isdir(out_file_path)):
          #      out_file_path = filesSelector.getPath()

        #    logger.info(out_file_path)
            test = summaVis("output/"+ self.jobName+ "/ouput1/syntheticTestCases/colbeck1976/colbeck1976-exp1_1990-01-01-00_spinup_testSumma_1.nccolbeck1976-exp1_1990-01-01-00_spinup_testSumma_1.nc")
            test.attrPlot('scalarRainPlusMelt')
            self.__client.exec_command("rm -r " + self.remoteSummaDir)
            switchMode()
        
        def summa_dir_name():
            stdout = "Found\n"
            ans = "nothing"
            summaTestDirPath = "/Users/CarnivalBug/Desktop/Jupyter-xsede/summatest"
            while (stdout == "Found\n"):
                ans = "/home/" + self.host_userName + "/summatest_" + str(random.randint(1,10000))
                stdout = self.__runCommandBlock("[ -d " + ans + " ] && echo 'Found'")
        
            basename = os.path.basename(summaTestDirPath)
            basezip = shutil.make_archive(basename, 'zip', summaTestDirPath)
            self.__sftp.put(basezip, ans+'.zip')

            self.__runCommandBlock('unzip ' + ans + '.zip -d ' + ans)
            self.__runCommandBlock('rm '+ ans + '.zip')
            
            return ans

        def submit(b):
            output.value += '<br>Uploading the task\n</font>'
            self.remoteSummaDir = summa_dir_name()
            filename = '%s.sh'%jobName.value
            
            jobview.value=self.job_template.substitute(
                  jobname  = jobName.value, 
                  n_times  = nTimes.value,
                  n_nodes  = nNodes.value, 
                  is_gpu   = isGPU.value.lower().replace(' ',''),
                  ppn      = ppn.value,
                  walltime = '%d:00:00'%int(float(walltime.value)), 
                  username = self.userName, 
                  stdout   = self.remoteSummaDir + "/" + jobName.value + '.stdout',
                  stderr   = self.remoteSummaDir + "/" + jobName.value + '.stderr',
                  hpcPath  = self.hpcRoot,
                  modules  = 'module load singularity',#+' '.join(list(self.modules)),
                  exe      = self.exe
            )

            with open(self.jobDir + '/' + filename,'w') as out:
                out.write(jobview.value)
            self.pbs = self.jobDir + '/' + filename
            self.__sftp.put(self.pbs, self.remoteSummaDir + '/run.qsub')
            output.value += '<br>Installing the task\n</font>'
            self.__runCommandBlock('cd ' + self.remoteSummaDir + ' && bash ./installSummaTest.sh '+ str(self.num_times_exe))
            self.jobId = self.__runCommand('cd '+ self.remoteSummaDir + ' && qsub run.qsub').strip()
            if ('ERROR' in self.jobId or 'WARN' in self.jobId):
                logger.warn('submit job error: %s'%self.jobId)
                exit()
            self.submissionTime=time.time()
            self.jobStatus = 'queuing'
            output.value+='<br>Job %s submitted at %s \n</font>'%(self.jobId,time.ctime())
            switchMode()
            t=Thread(target=monitorDeamon)
            t.start()
        
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
                Labeled('Job name', jobName),
                Labeled('No. times', nTimes),
                Labeled('Executable', entrance),
                Labeled('No. nodes', nNodes),
                Labeled('Cores per node', ppn),
                Labeled('GPU needed', isGPU),
                Labeled('Walltime (h)', walltime),
                Labeled('Times to execute', num_times_exe),
                Labeled('Job script', jobview),
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
            result = self.__runCommand("qstat | sed -n '1,2p;/%s/p'"%user)
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
