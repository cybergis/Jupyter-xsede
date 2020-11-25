import os
from .base import SBatchScript
from .connection import SSHConnection
from .job import SlurmJob
from .keeling import KeelingSBatchScript, KeelingJob
from .utils import get_logger


class BaseSupervisorToHPC(object):

    _KeelingSBatchScriptClass = KeelingSBatchScript
    _KeelingJobClass = KeelingJob
    _CometSBatchScriptClass = SBatchScript
    _CometJobClass = SlurmJob

    jobname = "SupervisorJob"

    def __init__(self,
                 parameters,
                 username="cigi-gisolve",
                 private_key_path="/opt/cybergis/.gisolve.key",
                 user_pw=None,
                 **kwargs,
                 ):
        self.logger = get_logger()
        self.username = username
        self.private_key_path = private_key_path
        self.user_pw = user_pw
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

    def submit(self, **kargs):

        self.logger.error("summa submit222222222222222")
        self.logger.error(kargs)
        _SBatchScriptClass = self.__class__._KeelingSBatchScriptClass
        _JobClass = self.__class__._KeelingJobClass

        if self.machine == "comet":
            _SBatchScriptClass = self.__class__._CometSBatchScriptClass
            _JobClass = self.__class__._CometJobClass

        _sbatch_obj = _SBatchScriptClass(
            int(self.wt), self.node, self.jobname
        )

        job = _JobClass(
            self.workspace_path,
            self.model_source_folder_path,
            self.connection,
            _sbatch_obj,
            name=self.jobname,
            **kargs
        )

        job.go()

        return {
            "remote_id": job.remote_id,
            "remote_job_folder_path": job.remote_job_folder_path,
            "remote_model_folder_path": job.remote_model_folder_path,
            "local_job_folder_path": job.local_job_folder_path,
            "remote_slurm_out_file_path": job.remote_slurm_out_file_path,
        }

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
        remote_output_parent_folder_path,
        local_job_folder_path,
    ):
        self.connection.download(
            os.path.join(remote_output_parent_folder_path, "output"),
            local_job_folder_path,
            remote_is_folder=True,
        )
