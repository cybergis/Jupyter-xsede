
from .utils import UtilsMixin
import logging
import os
import uuid

logger = logging.getLogger("cybergis")

class AbstractConnection(object):
    connection_type = str()
    server = str()

    def login(self):
        raise NotImplementedError()

    def logout(self):
        raise NotImplementedError()

    def upload(self, local_fpath, remote_fpath, *args, **kwargs):
        raise NotImplementedError()

    def download(self, remote_fpath, local_fpath, *args, **kwargs):
        raise NotImplementedError()

    def run_command(self, command, *args, **kwargs):
        raise NotImplementedError()


class AbstractScript(object):
    def generate_script(self, *args, **kargs):
        raise NotImplementedError()


class AbstractJob(object):
    pass


class SBatchScript(AbstractScript):
    walltime = int(100)
    node = int(1)
    jobname = ""
    stdout = None  # Path to output
    stderr = None  # Path to err
    exec = ""

class Job(UtilsMixin):
    JOB_ID_PREFIX = "CyberGIS_"
    backend = ""  # keeling or comet
    local_id = ""
    remote_id = ""
    state = ""

    local_workspace_path = ""
    local_job_folder_path = ""
    local_output_folder_name = ""

    remote_workspace_path = ""
    remote_job_folder_name = ""
    remote_output_folder_name = ""

    sbatch_script = None
    user_script = None
    connection = None
    connection_class = AbstractConnection
    sbatch_script_class = SBatchScript
    user_script_class = AbstractScript

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
        assert isinstance(user_script, AbstractScript)
        self.connection = connection
        self.sbatch_script = sbatch_script
        self.user_script = user_script

        self.name = name if name is not None else local_id
        self.description = description

        self._create_local_job_folder()

    def _create_local_job_folder(self):
        local_job_folder_path = os.path.join(self.local_workspace_path,
                                             self.local_id)
        self.create_local_folder(local_job_folder_path)
        self.local_job_folder_path = local_job_folder_path
        return local_job_folder_path

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
        # organize run_script and local data
        # upload to HPC
        # no remote_id
        self.ssh_connection.upload(self.local_data_path,
                                   self.remote_data_path)

    def submit(self):
        # submit job to HPC scheduler
        self.ssh_connection.runCommand(self.sbatch_script)
        self.remote_id = ""

    def download(self):
        # download job from HPC to local
        self.ssh_connection.download(self.remote_output_path, self.local_output_path)