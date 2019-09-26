from .base import BaseScript, SBatchScript, BaseConnection, BaseJob
from .utils import UtilsMixin
import logging
import uuid
import os

logger = logging.getLogger("cybergis")


class SlurmJob(UtilsMixin, BaseJob):
    # This is a Slurm Job

    JOB_ID_PREFIX = "CyberGIS_"
    backend = ""  # keeling or comet
    local_id = ""
    remote_id = ""
    state = ""

    local_workspace_path = ""
    # local_job_folder_name = ""
    # local_job_folder_path = ""
    # local_output_folder_name = ""

    remote_workspace_path = ""
    remote_job_folder_name = ""
    remote_job_folder_path = ""
    remote_output_folder_name = ""

    sbatch_script = None
    user_script = None
    connection = None
    connection_class = BaseConnection
    sbatch_script_class = SBatchScript
    user_script_class = BaseScript

    def __init__(self, local_workspace_path, connection,
                 sbatch_script, user_script, local_id=None,
                 name=None, description=None,
                 *args, **kwargs):

        if not os.path.isdir(local_workspace_path):
            raise Exception("Local workspace folder does not exist")
        self.local_workspace_path = local_workspace_path

        if local_id is None:
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX)
        self.local_id = local_id

        assert isinstance(connection, self.connection_class)
        assert isinstance(sbatch_script, self.sbatch_script_class)
        assert isinstance(user_script, BaseScript)
        self.connection = connection
        self.sbatch_script = sbatch_script
        self.user_script = user_script

        self.name = name if name is not None else local_id
        self.description = description

        self._create_local_job_folder()

    @property
    def local_job_folder_name(self):
        return self.local_id

    @property
    def local_job_folder_path(self):
        return os.path.join(self.local_workspace_path,
                            self.local_job_folder_name)

    def _create_local_job_folder(self):
        return self.create_local_folder(self.local_job_folder_path)

    def random_id(self, digit=10, prefix=str(), suffix=str()):
        id = str(uuid.uuid4()).replace("-", "")
        if digit < 8:
            digit = 8
        elif digit > 32:
            digit = 32
        out = "{pre}{id}{suf}".format(pre=prefix,
                                      id=id[0:digit],
                                      suf=suffix)
        return out

    def upload(self):
        # upload model job folder to remote
        self.connection.upload(self.local_job_folder_path,
                               self.remote_workspace_path,
                               remote_is_folder=True)

    def _save_remote_id(self, in_msg):

        self.remote_id = ""
        raise NotImplementedError()

    def submit(self):
        # submit job to HPC scheduler
        cmd = "cd {} && qsub {}".format(self.remote_job_folder_path,
                                        self.sbatch_script.file_name)

        out = self.connection.runCommand(cmd)
        self._save_remote_id(out)

    def download(self):
        raise NotImplementedError()
        # download job from HPC to local
        self.connection.download(self.remote_output_path, self.local_output_path)