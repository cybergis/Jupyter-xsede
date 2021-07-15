from .base import SBatchScript, BaseJob
from .connection import SSHConnection
from .job import SlurmJob
from .keeling import KeelingSBatchScript, KeelingJob
from .utils import get_logger


logger = get_logger()


class BaseSupervisorToHPC(object):
    _KeelingSBatchScriptClass = KeelingSBatchScript
    _KeelingJobClass = KeelingJob
    _CometSBatchScriptClass = SBatchScript
    _CometJobClass = SlurmJob

    def __init__(self,
                 parameters,
                 username="cigi-gisolve",
                 private_key_path="/opt/cybergis/.gisolve.key",
                 user_pw=None,
                 **kwargs,
                 ):
        self.logger = get_logger()
        self.parameters = parameters

        self.username = username
        self.private_key_path = private_key_path
        self.user_pw = user_pw

        try:
            for k, v in parameters.items():
                if v == "undefined":
                    parameters[k] = None
            self.logger.error("*" * 200)
            self.logger.error("parameters: {}".format(parameters))
        except:
            pass
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
            self.wt = parameters["walltime_hour"]
        except:
            pass
        try:
            self.jobid = parameters["jobid"]
        except:
            self.jobid = None

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
        elif self.machine.lower() == "comet" or self.machine.lower() == "expanse":
            if self.username == "cybergis":
                self.connection = SSHConnection(
                    "login.expanse.sdsc.edu",
                    user_name="cybergis",
                    key_path=self.private_key_path,
                )
            else:
                self.connection = SSHConnection(
                    "login.expanse.sdsc.edu", user_name=self.username, user_pw=self.user_pw
                )
        self.connection.login()
        return self

    def submit(self, **kargs):

        _SBatchScriptClass = self.__class__._KeelingSBatchScriptClass
        _JobClass = self.__class__._KeelingJobClass

        if self.machine == "comet" or self.machine == "expanse":
            _SBatchScriptClass = self.__class__._CometSBatchScriptClass
            _JobClass = self.__class__._CometJobClass

        kargs.update(self.parameters)
        _sbatch_obj = _SBatchScriptClass(
            int(self.wt), self.node, **kargs
        )

        job = _JobClass(
            self.workspace_path,
            self.model_source_folder_path,
            self.connection,
            _sbatch_obj,
            local_id=self.jobid,
            **kargs
        )

        job.go()

        return_dict = {
            "remote_id": job.remote_id,
            "remote_job_folder_path": job.remote_job_folder_path,
            "local_job_folder_path": job.local_job_folder_path,
            "remote_model_folder_path": job.remote_model_folder_path,
            "local_model_folder_path": job.local_model_folder_path,
            "remote_slurm_out_file_path": job.remote_slurm_out_file_path,
        }

        return return_dict

    def job_status(self, remote_id):
        return SlurmJob.job_status_sacct(BaseJob(), remote_id, self.connection)

    def download(
            self,
            remote_output_folder_path,
            local_output_parent_folder_path,
    ):
        self.connection.download(
            remote_output_folder_path,
            local_output_parent_folder_path,
            remote_is_folder=True,
        )
