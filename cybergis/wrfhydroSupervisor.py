import os
import time

from .base import *
from .connection import *
from .keeling import *
from .wrfhydro import *
from .utils import *
from .job import *


class wrfhydro_base:
    username = ""
    machine = "keeling"
    model_source_folder_path = ""  ## the path to the summa testcase folder
    file_manager_path = ""  ## the path to the filemanager folder
    jobname = "wrfhydro"  ## the name of the job
    wt = 1
    node = 1
    keeling_con = None
    workspace_path = None
    localID = None
    job_local_id = None
    job_remote_id = None
    private_key_path = None
    user_pw = None
    model_name = None


class WRFHydroSupervisorToHPC(wrfhydro_base):
    def __init__(
        self,
        parameters,
        username="cigi-gisolve",
        private_key_path="/opt/cybergis/.gisolve.key",
        user_pw=None,
    ):
        self.username = username
        try:
            self.model_name = parameters["model"]
        except:
            pass
        try:
            self.machine = parameters["machine"]
        except:
            pass
        try:
            self.model_source_folder_path = parameters["model_source_folder_path"]
        except:
            pass
        try:
            self.workspace_path = parameters["workspace_dir"]
        except:
            pass
        try:
            self.node = parameters["node"]
        except:
            pass
        try:
            self.wt = parameters["walltime"]
        except:
            pass
        self.private_key_path = private_key_path
        self.user_pw = user_pw

    def submit(self, params={}):
        try:
            self.node = params["node"]
        except:
            pass
        try:
            self.wt = params["walltime"]
        except:
            pass

        model_source_folder_path = self.model_source_folder_path

        if self.machine == "keeling":


            wrfhydro_sbatch = WRFHydroKeelingSBatchScript(
                int(self.wt), self.node, self.jobname
            )

            job = WRFHydroKeelingJob(
                self.workspace_path,
                self.connection,
                wrfhydro_sbatch,
                model_source_folder_path,
                name=self.jobname,
            )
        elif self.machine.lower() == "comet":
            wrfhydro_sbatch = WRFHydroCometSBatchScript(
                str(int(self.wt)), self.node, self.jobname
            )
            job = WRFHydroCometJob(
                self.workspace_path,
                self.connection,
                wrfhydro_sbatch,
                model_source_folder_path,
                name=self.jobname,
            )

        job.go()

        return {
            "remote_id": job.remote_id,
            "remote_job_folder_path": job.remote_job_folder_path,
            "local_job_folder_path": job.local_job_folder_path,
        }

    def connect(self):
        if self.machine.lower() == "keeling":
            if self.username == "cigi-gisolve":
                self.connection = SSHConnection(
                    "keeling.earth.illinois.edu",
                    user_name="cigi-gisolve",
                    key_path=self.private_key_path,
                )
            else:
                self.connection = SSHConnection(
                    "keeling.earth.illinois.edu",
                    user_name=self.username,
                    user_pw=self.user_pw,
                )
        elif self.machine.lower() == "comet":
            if self.username == "cybergis":
                self.connection = SSHConnection(
                    "comet.sdsc.edu",
                    user_name="cybergis",
                    key_path=self.private_key_path,
                )
            else:
                self.connection = SSHConnection(
                    "comet.sdsc.edu", user_name=self.username, user_pw=self.user_pw
                )
        self.connection.login()
        return self

    def job_status(self, remote_id):
        # Keeling has both squeue (slurm) and qstat (pbs) for queue management
        # Based our test, however, squeue Can Not show Completed jobs and kicks job off
        # queue record very soon. So it is hard to tell if a run is completed or does not exist
        # So we use qstat (pbs) to monitor job status
        # get current hpc time and job status (remove line 1 and 3)
        cmd = "qstat {}".format(remote_id)

        try:
            out = self.connection.run_command(
                cmd, line_delimiter=None, raise_on_error=True
            )
            if out is None:
                return "UNKNOWN"
            # out = \
            # ['Job id              Name             Username        Time Use S Queue          ',
            # '------------------- ---------------- --------------- -------- - ---------------',
            # '3142249             singularity      cigi-gisolve    00:00:00 R node           ']

            return out[2].split()[-2]
        except Exception as ex:
            return "ERROR"

    def download(
        self,
        remote_job_folder_path,
        local_job_folder_path,
    ):
        self.connection.download(
            os.path.join(remote_job_folder_path, "output"),
            local_job_folder_path,
            remote_is_folder=True,
        )