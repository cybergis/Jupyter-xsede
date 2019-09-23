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
import fileinput
import sys

# class JobManager(object):
#     # threading to manage multiple jobs
#     pass
#

KEELING_SUMMA_TEMPLATE='''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime
#SBATCH --output=$stdout
#SBATCH -e $stderr

$exe'''


USER_SUMMA_TEMPLATE='''#!/bin/bash
SUMMA_EXE=/code/bin/summa.exe
SUMMA_SETTING=$settingpath

if  [ -z ${SUMMA_EXE} ]
    then
        echo "Can not find the SUMMA executable SUMMA_EXE"
        exit 1
fi

${SUMMA_EXE} -p never -s $casename -m ${SUMMA_SETTING}'''


class CyberGISJob(object):
    name = ""
    local_id = ""
    remote_id = ""
    state = ""

    sbatch_script = ""
    user_script = ""

    remote_data_path = ""
    remote_output_path = ""
    local_data_path = ""
    local_output_path = ""
    ssh_connection = None

    def upload(self):
        # organize run_script and local data
        # upload to HPC
        # no remote_id
        self.ssh_connection.upload(self.local_data_path,
                                   self.remote_data_path)
        pass

    def submit(self):
        # submit job to HPC scheduler
        self.ssh_connection.runCommand(self.sbatch_script)
        self.remote_id = ""


    def download(self):
        # download job from HPC to local
        self.ssh_connection.download(self.remote_output_path, self.local_output_path)
        pass


class SummaJob(CyberGISJob):


    pass


class AbstractScript(object):
    def generarte_script(self):
        pass


class SBatchScript(AbstractScript):
    curr_machine = None
    walltime = int(100)
    node = int(1)
    jobname = None
    stdout = None ## Path to output 
    stderr = None ## Path to error


class SummaSBatchScript(UserScript):
    def __init__(walltime, node, jobname, stdout, stderr, curr_machine = "keeling"):
        self.curr_machine=curr_machine
        self.node=node
        self.jobname=jobname
        self.stdout=stdout
        self.stderr=stderr
        self.curr_machine=curr_machine
    def generarte_script():
        if (curr_machine=="keeling"):
            sbscript = KEELING_SUMMA_TEMPLATE.substitute(
                jobname = self.jobname,
                n_nodes = self. node,
                walltime = self.walltime,
                stdout = self.stdout,
                stderr = self.stderr,
                exe = "singularity exec summa.simg ./runSummaTest.sh"
                )
            return sbscript
        else:
            logger.warn("Unknown Machine")

class UserScript(AbstractScript):
    curr_machine = None


class SummaUserScript(UserScript):
    userscriptname = None
    settingpath = None
    casename = None
    def __init__(settingpath, casename, userscriptname="runSummaTest.sh", curr_machine= "keeling"):
        self.settingpath=settingpath
        self.casename=casename
        self.userscriptname=userscriptname
        self.curr_machine=curr_machine
    def getscriptname:
        return self.userscriptname
    def generarte_script():
        if (curr_machine=="keeling"):
            uscript = USER_SUMMA_TEMPLATE.substitute(
                settingpath = self.settingpath,
                casename = self.casename
                )
            return uscript
        else:
            logger.warn("Unknown Machine")



class SSHConnection(object):

    jobDir = None
    host = None

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
        if 'exists' not in self.__runCommand("if [ -d " + HPC_PRJ + " ]; then echo 'exists'; fi"):
            self.__runCommand("mkdir "+ HPC_PRJ)
  
        moduleList = self.__runCommand("module avail 2>&1 | grep -v '/sw' | tr ' ' '\n' | sed '/^$/d' | sort") 

        self.module_avail = {_:_  for _ in moduleList.replace('(default)','').split() if _.count('-') < 3}
        self.m = self.module_avail
        self.modules = set()    


