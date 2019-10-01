import logging
import os
import time
from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript

logger = logging.getLogger("cybergis")


class SummaKeelingSBatchScript(KeelingSBatchScript):

    name = "SummaKeelingSBatchScript"
    SCRIPT_TEMPLATE = \
'''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$nodes
#SBATCH --time=$walltime

sbatch singularity exec $simg_path python $userscript_path'''

    simg_path = "/data/keeling/a/zhiyul/images/pysumma_ensemble.img"
    userscript_path = None

    def __init__(self, walltime, nodes, jobname,
                 userscript_path=None, *args, **kargs):
        exe = None
        super().__init__(walltime, nodes, jobname, exe, *args, **kargs)
        self.userscript_path = userscript_path
        self.simg_path = self.simg_path


class SummaUserScript(BaseScript):
    name = "SummaUserScript"
    SCRIPT_TEMPLATE = \
'''import pysumma as ps
import pysumma.hydroshare_utils as utils
from hs_restclient import HydroShare
import shutil, os
import subprocess
from ipyleaflet import Map, GeoJSON
import json

os.chdir("$singularity_job_folder_path")  # /home/USER/Summa_XXXXXXX
instance = '$model_folder_name' # aspen

file_manager = os.path.join(os.getcwd(), instance, 'settings/$file_manager_name')
executable = "/code/bin/summa.exe"

S = ps.Simulation(executable, file_manager)


S.run('local', run_suffix='_test')

'''

    singularity_job_folder_path = None
    model_folder_name = None
    file_manager_name = None
    file_name = "run.py"

    def __init__(self, singularity_job_folder_path, model_folder_name,
                 file_manager_name, *args, **kargs):
        self.singularity_job_folder_path = singularity_job_folder_path
        self.model_folder_name = model_folder_name
        self.file_manager_name = file_manager_name


class SummaKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "Summa_"
    sbatch_script_class = SummaKeelingSBatchScript
    user_script_class = SummaUserScript

    def __init__(self, local_workspace_path, connection, sbatch_script,
                 model_source_folder_path, model_source_file_manager_rel_path,
                 local_id=None,
                 move_source=False,
                 *args, **kwargs):

        if local_id is None:
            t = str(int(time.time()))
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX + "{}_".format(t))

        super().__init__(local_workspace_path, connection, sbatch_script, local_id=local_id, *args, **kwargs)

        # Directory: "/Workspace/Job/Model/"
        model_source_folder_path = self._check_abs_path(model_source_folder_path)
        self.model_source_folder_path = model_source_folder_path
        self.model_folder_name = os.path.basename(self.model_source_folder_path)

        self.model_source_file_manager_rel_path = model_source_file_manager_rel_path
        self.model_file_manager_name = os.path.basename(self.model_source_file_manager_rel_path)
        self.model_source_file_manager_path = os.path.join(model_source_folder_path,
                                                           self.model_source_file_manager_rel_path)

        self.move_source = move_source

    def prepare(self):
        # Directory: "/Workspace/Job/Model/"

        # copy/move model folder to local job folder
        if self.move_source:
            self.move_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        else:
            self.copy_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        self.local_model_folder_path = os.path.join(self.local_job_folder_path,
                                                    self.model_folder_name)
        self.local_model_file_manager_path = os.path.join(self.local_model_folder_path,
                                                          self.model_source_file_manager_rel_path)
        # connection login remote
        self.connection.login()

        self.singularity_home_folder_path = "/home/{}".format(self.connection.remote_user_name)
        self.singularity_workspace_path = self.singularity_home_folder_path
        self.singularity_job_folder_path = os.path.join(self.singularity_workspace_path, self.local_job_folder_name)
        self.singularity_model_folder_path = os.path.join(self.singularity_job_folder_path, self.model_folder_name)

        self.remote_workspace_path = self.connection.remote_user_home
        self.remote_job_folder_name = self.local_job_folder_name
        self.remote_job_folder_path = os.path.join(self.remote_workspace_path,
                                                   self.remote_job_folder_name)
        self.remote_model_folder_path = os.path.join(self.remote_job_folder_path,
                                                     self.model_folder_name)

        user_script = SummaUserScript(self.singularity_job_folder_path,
                                      self.model_folder_name,
                                      self.model_file_manager_name)
        self.sbatch_script.userscript_path = user_script

        # save SBatch script
        self.sbatch_script.generate_script(local_folder_path=self.local_model_folder_path)
        self.sbatch_script.remote_folder_path = self.remote_model_folder_path

        # replace local path with remote path
        # sbatch.sh: change userscript path to path in singularity
        # local workspace path -> singularity workspace path (singularity home directory)
        self.replace_text_in_file(self.sbatch_script.local_path,
                                  [(self.local_workspace_path, self.singularity_workspace_path)])

        # summa file_manager:
        # file manager uses model_source_folder_path
        # change to singularity_model_folder_path
        self.replace_text_in_file(self.local_model_file_manager_path,
                                  [(self.model_source_folder_path, self.singularity_model_folder_path)])

    def go(self):
        self.prepare()
        self.upload()
        self.submit()

    def download(self):
        self.connection.download(os.path.join(self.remote_model_folder_path, "output"),
                                 self.local_job_folder_path, remote_is_folder=True)
        self.connection.download(self.remote_slurm_out_file_path, self.local_job_folder_path)
