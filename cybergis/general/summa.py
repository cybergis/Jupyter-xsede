import logging
import os
from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from string import Template

logger = logging.getLogger("cybergis")


class SummaKeelingSBatchScript(KeelingSBatchScript):
    name = "SummaKeelingSBatchScript"
    SCRIPT_TEMPLATE = '''
    #!/bin/bash
    #SBATCH --job-name=$jobname
    #SBATCH --nodes=$nodes
    #SBATCH -t $walltime

    $exe singularity exec $simg_path $userscript_path'''

    simg_path = "/data/keeling/a/zhiyul/images/pysumma_ensemble.img"
    userscript_path = None

    def __init__(self, walltime, nodes, jobname, userscript_path, *args, **kargs):
        userscript_path = userscript_path + "/run.py"
        _exec = Template(self.EXEC).substitute(simg="/data/keeling/a/zhiyul/images/pysumma_ensemble.img",
                                               userscript=userscript_path)
        super().__init__(walltime, nodes, jobname, _exec, *args, **kargs)

    def parameter_dict(self):
        return dict(

        )


class SummaUserScript(BaseScript):
    name = "SummaUserScript"
    SUMMA_USER_TEMPLATE = '''
import pysumma as ps
import pysumma.hydroshare_utils as utils
from hs_restclient import HydroShare
import shutil, os
import subprocess
from ipyleaflet import Map, GeoJSON
import json

os.chdir("$local_path")
instance = '$instance_name'

file_manager = os.getcwd() + '/' + instance + '/settings/$file_manager_name'
executable = "/code/bin/summa.exe"

S = ps.Simulation(executable, file_manager)


S.run('local', run_suffix='_test')

'''

    local_path = None
    instance_name = None
    file_manager_name = None
    file_name = "run.py"

    def __init__(self, local_path, instance_name, file_manager_name, *args, **kargs):
        self.local_path = local_path
        self.instance_name = instance_name
        self.file_manager_name = file_manager_name



class SummaKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "Summa_"
    sbatch_script_class = SummaKeelingSBatchScript
    user_script_class = SummaUserScript

    def __init__(self, local_workspace_path, connection, sbatch_script,
                 user_script, local_id=None,
                 model_source_folder_path="", move_source=False,
                 *args, **kwargs):

        if local_id is None:
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX)

        super().__init__(local_workspace_path, connection, sbatch_script, user_script, local_id=local_id, *args, **kwargs)
        self.model_source_folder_path = model_source_folder_path
        self.move_source = move_source

    def prepare(self):

        # copy/move model folder to local job folder
        if self.move_source:
            self.move_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        else:
            self.copy_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        # save SBatch script
        self.sbatch_script.generate_script(local_path=self.local_job_folder_path)

        # save User script
        self.user_script.generate_script(local_path=self.local_job_folder_path)

        # connection login remote
        self.connection.login()
        self.connection.remote_user_home
        self.connection.remote_user_name

        self.remote_workspace_path = self.connection.remote_user_home
        self.remote_job_folder_name = self.local_job_folder_name
        self.remote_job_folder_path = os.path.join(self.remote_workspace_path,
                                                   self.remote_job_folder_name)

        # replace local path with remote path
        # XXXXXXXXXXXXXXXX




