import uuid
import os
from .base import SBatchScript, BaseConnection, BaseJob
from .utils import UtilsMixin


class SlurmJob(UtilsMixin, BaseJob):
    # This is a Slurm Job

    JOB_ID_PREFIX = "CyberGIS_"
    backend = ""  # keeling or comet
    local_id = ""
    remote_id = ""
    state = ""

    local_workspace_path = ""
    local_job_folder_name = ""
    local_job_folder_path = ""
    local_output_folder_name = ""

    remote_workspace_path = ""
    remote_job_folder_name = ""
    remote_job_folder_path = ""
    remote_output_folder_name = ""

    remote_run_sbatch_folder_path = ""  # where to execute sbatch.run, this is where slurm-xxxx.out will be
    slurm_out_file_name = ""
    remote_slurm_out_file_path = ""

    sbatch_script = None
    user_script = None
    connection = None
    connection_class = BaseConnection
    sbatch_script_class = SBatchScript

    def __init__(self, local_workspace_path, connection,
                 sbatch_script, local_id=None,
                 name=None, description=None,
                 *args, **kwargs):
        super().__init__()

        local_workspace_path = self._check_abs_path(local_workspace_path)

        if not os.path.isdir(local_workspace_path):
            raise Exception("Local workspace folder does not exist")
        self.local_workspace_path = local_workspace_path

        if local_id is None:
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX)
        self.local_id = local_id

        assert isinstance(connection, self.connection_class)
        assert isinstance(sbatch_script, self.sbatch_script_class)

        self.connection = connection
        self.sbatch_script = sbatch_script

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

    def random_id(self, digit=8, prefix=str(), suffix=str()):
        local_id = str(uuid.uuid4()).replace("-", "")
        if digit < 8:
            digit = 8
        elif digit > 32:
            digit = 32
        out = "{pre}{local_id}{suf}".format(pre=prefix,
                                            local_id=local_id[0:digit],
                                            suf=suffix)
        return out

    def upload(self):
        # upload model job folder to remote
        self.connection.upload(self.local_job_folder_path,
                               self.remote_workspace_path,
                               remote_is_folder=True)

    def _save_remote_id(self, in_msg, *args, **kwargs):

        self.remote_id = ""
        raise NotImplementedError()
        return self.remote_id

    def _save_remote_id(self, msg, *args, **kwargs):
        if 'ERROR' in msg or 'WARN' in msg:
            self.logger.error('Submit job {} error: {}'.format(self.local_id, msg))
        self.remote_id = msg
        self.logger.debug("Job local_id {} remote_id {}".format(self.local_id, self.remote_id))
        return self.remote_id

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

    def post_submission(self):
        pass

    def job_status(self):
        # monitor job status
        raise NotImplementedError()

    def download(self):
        raise NotImplementedError()
        # download job from HPC to local
        self.connection.download(self.remote_output_path, self.local_output_path)

    def prepare(self, *args, **kwargs):

        raise NotImplementedError()

    def job_status(self):
        # monitor job status
        # see https://slurm.schedmd.com/squeue.html
        # "JOB STATE CODES" section for more states
        # PD PENDING, R RUNNING, S SUSPENDED,
        # CG COMPLETING, CD COMPLETED

        # get current hpc time and job status (remove line 1 and 3)
        remote_id = self.remote_id
        cmd = 'squeue --job {}'.format(remote_id)
        try:
            out = self.connection.run_command(cmd,
                                              line_delimiter=None,
                                              raise_on_error=True)
            # out[0].split()
            #   ['JOBID', 'PARTITION', 'NAME', 'USER', 'ST', 'TIME', 'NODES', 'NODELIST(REASON)']
            # out[1].split()
            #   ['3142135', 'node', 'singular', 'cigi-gis', 'R', '0:11', '1', 'keeling-b08']
            return out[1].split()[4]
        except Exception as ex:
            return "ERROR"
