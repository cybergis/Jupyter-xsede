import os
import time
import datetime
from string import Template

from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from .utils import get_logger

logger = get_logger()


class WRFHydroKeelingSBatchScript(KeelingSBatchScript):

    name = "WRFHydroKeelingSBatchScript"
    file_name = "wrfhydro.sbatch"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

srun --mpi=pmi2 singularity exec \
   /data/keeling/a/cigi-gisolve/simages/wrfhydro.img \
   $userscript_path 
'''

    def __init__(self, walltime, ntasks, jobname,
                 simg_path=None,
                 userscript_path=None,
                 *args, **kargs):

        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        self.userscript_path = userscript_path
        self.simg_path = simg_path


class WRFHydroUserScript(BaseScript):
    name = "WRFHydroUserScript"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash
cd /home/cigi-gisolve/$singularity_job_folder_path
./wrf_hydro.exe

'''

    singularity_job_folder_path = None

    def __init__(self, singularity_job_folder_path, *args, **kargs):
        super().__init__()
        self.singularity_job_folder_path = singularity_job_folder_path


class WRFHydroKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "WRFHydro_"
    sbatch_script_class = WRFHydroKeelingSBatchScript
    user_script_class = WRFHydroUserScript
    localID = None

    def __init__(self, local_workspace_path, connection, sbatch_script,
                 model_source_folder_path,
                 local_id=None,
                 move_source=False,
                 *args, **kwargs):

        if local_id is None:
            t = str(int(time.time()))
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX + "{}_".format(t))
            self.localID=local_id

        super().__init__(local_workspace_path, connection, sbatch_script, local_id=local_id, *args, **kwargs)

        # fix symbolic here
        # https://www.thetopsites.net/article/52124943.shtml
        # rsync symdir/ symdir_output/ -a --copy-links -v

        # Directory: "/Workspace/Job/Model/"
        model_source_folder_path = self._check_abs_path(model_source_folder_path)
        self.model_source_folder_path = model_source_folder_path
        self.model_folder_name = os.path.basename(self.model_source_folder_path)
        self.move_source = move_source

    def getlocalid(self):
        return self.localID

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

        self.logger.info(self.local_model_folder_path)

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

        self.logger.info(self.remote_job_folder_name)
        self.logger.info(self.model_folder_name)


        user_script = WRFHydroUserScript(os.path.join(self.remote_job_folder_name,
                                                      self.model_folder_name))
        self.sbatch_script.userscript_path = os.path.join("./home",
                                                          self.connection.remote_user_name,
                                                          self.remote_job_folder_name,
                                                          "simulation_interactive",
                                                          "script.sh")
        #self.sbatch_script.userscript_path = user_script
        user_script.generate_script(local_folder_path=self.local_model_folder_path)


        # save SBatch script
        self.sbatch_script.generate_script(local_folder_path=self.local_model_folder_path)
        self.sbatch_script.remote_folder_path = self.remote_model_folder_path
        return
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
        self.post_submission()

    def download(self):
        self.connection.download(self.remote_model_folder_path,
                                 self.local_job_folder_path, remote_is_folder=True)
        self.connection.download(self.remote_slurm_out_file_path, self.local_job_folder_path)

    def submit(self):
        # submit job to HPC scheduler

        self.remote_run_sbatch_folder_path = self.sbatch_script.remote_folder_path
        self.logger.info("Submitting Job {} to queue".format(self.sbatch_script.file_name))
        cmd = "cd {} && sbatch {}".format(self.remote_run_sbatch_folder_path,
                                          self.sbatch_script.file_name)

        out = self.connection.run_command(cmd)
        remote_id = self._save_remote_id(out)
        self.logger.info("Remote Job ID assigned: {}".format(remote_id))
        self.slurm_out_file_name = "slurm-{}.out".format(remote_id)
        self.remote_slurm_out_file_path = os.path.join(self.remote_run_sbatch_folder_path,
                                                       self.slurm_out_file_name)
import time
from .connection import SSHConnection
def WRFHydroSubmission(workspace, mode_path, nodes, wtime, hpc):

    keeling_con = SSHConnection("keeling.earth.illinois.edu",
                                user_name="cigi-gisolve",
                                key_path="/wrf_hydro_py/keeling_test_20200804.key")

    wrfhydro_sbatch = WRFHydroKeelingSBatchScript(wtime, nodes, "wrfhydro")

    #local_workspace_path = "/wrf_hydro_py/tmp"
    local_workspace_path = workspace
    #model_source_folder_path = "/wrf_hydro_py/tmp/wrfhydropy_end-to-end_example/simulation_interactive"
    model_source_folder_path = mode_path
    job = WRFHydroKeelingJob(local_workspace_path, keeling_con, wrfhydro_sbatch, model_source_folder_path,
                             name="WRFHydro")
    job.prepare()
    job.upload()
    job.submit()

    job_local_id = job.local_id
    job_remote_id = job.remote_id
    for i in range(600):
        time.sleep(3)
        status = job.job_status()
        if status == "ERROR":
            logger.info("Job status ERROR")
            break
        elif status == "C":
            logger.info("Job completed: {}; {}".format(job.local_id, job.remote_id))
            job.download()
            break
        else:
            logger.info(status)
    logger.info("Done")
    return job.local_job_folder_path
