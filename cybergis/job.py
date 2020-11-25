import uuid
import os
import time
from .base import SBatchScript, BaseConnection, BaseJob
from .utils import UtilsMixin


class SlurmJob(UtilsMixin, BaseJob):
    # This is a Slurm Job
    JOB_ID_PREFIX = "CyberGIS_"
    backend = ""  # keeling or comet
    # the job id assigned locally
    local_id = ""
    # the jon id assigned on HPC
    remote_id = ""
    state = ""

    # /Workspace/Job/Model
    local_output_folder_name = ""
    # output folder on HPC
    remote_output_folder_name = ""

    # where to execute sbatch.run, this is where slurm-xxxx.out will be
    remote_run_sbatch_folder_path = ""
    # filename of the slurm out file, by default slurm-XXXXXX.out
    slurm_out_file_name = ""
    # full path to slurm out file on HPC
    remote_slurm_out_file_path = ""

    # sbatch script obj
    sbatch_script = None
    # user script obj
    user_script = None
    # ssh_connection obj
    connection = None
    # Class type of connection obj
    connection_class = BaseConnection
    # Class type of sbatch script obj
    sbatch_script_class = SBatchScript

    def __init__(self,
                 local_workspace_path,
                 local_model_source_folder_path,
                 connection,
                 sbatch_script,
                 local_id=None,
                 name=None,
                 description=None,
                 move_source=False,
                 **kwargs):
        super().__init__()

        local_workspace_path = self._check_abs_path(local_workspace_path)
        if not os.path.isdir(local_workspace_path):
            raise Exception("Local workspace folder does not exist")
        # local full path to workspace folder
        self.local_workspace_path = local_workspace_path

        local_model_source_folder_path = self._check_abs_path(local_model_source_folder_path)
        if not os.path.isdir(local_model_source_folder_path):
            raise Exception("Local model source folder does not exist")
        self.local_model_source_folder_path = local_model_source_folder_path
        # model folder name parsed from 'local_model_source_path'
        self.model_folder_name = os.path.basename(local_model_source_folder_path)

        if local_id is None:
            t = str(int(time.time()))
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX + "{}_".format(t))
            self.localID = local_id

        # local job id
        self.local_id = local_id
        self._create_local_job_folder()
        self._prepare_local_model_folder(move_source)

        assert isinstance(connection, self.connection_class)
        assert isinstance(sbatch_script, self.sbatch_script_class)

        self.remote_workspace_folder_path = sbatch_script.remote_workspace_folder_path
        self.connection = connection
        self.sbatch_script = sbatch_script
        self.sbatch_script.job = self

        self.name = name if name is not None else local_id
        self.description = description

    def _prepare_local_model_folder(self, move_source):
        if move_source:
            self.move_local(self.local_model_source_folder_path,
                            self.local_job_folder_path)
        else:
            self.copy_local(self.local_model_source_folder_path,
                            self.local_job_folder_path)

    def to_dict(self):
        return_dict = self.__dict__.copy()
        more_dict = {
            "local_job_folder_name": self.local_job_folder_name,
            "local_job_folder_path": self.local_job_folder_path,
            "local_model_folder_path": self.local_model_folder_path,
            "remote_job_folder_name": self.remote_job_folder_name,
            "remote_job_folder_path": self.remote_job_folder_path,
            "remote_model_folder_name": self.remote_model_folder_name,
            "remote_model_folder_path": self.remote_model_folder_path,
        }
        return_dict.update(more_dict)
        return return_dict

    def go(self):
        self.prepare()
        self.connection.login()
        self.upload()
        self.submit()
        self.post_submission()

    @property
    def local_job_folder_name(self):
        return self.local_id

    @property
    def local_job_folder_path(self):
        return os.path.join(self.local_workspace_path,
                            self.local_job_folder_name)

    @property
    def local_model_folder_path(self):
        return os.path.join(self.local_job_folder_path,
                            self.model_folder_name)

    @property
    def remote_job_folder_name(self):
        return self.local_job_folder_name

    @property
    def remote_job_folder_path(self):
        return os.path.join(self.remote_workspace_folder_path,
                            self.remote_job_folder_name)

    @property
    def remote_model_folder_name(self):
        return self.model_folder_name

    @property
    def remote_model_folder_path(self):
        return os.path.join(self.remote_job_folder_path,
                            self.remote_model_folder_name)

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
                               self.remote_workspace_folder_path,
                               remote_is_folder=True)

    def _save_remote_id(self, msg, *args, **kwargs):
        if 'ERROR' in msg or 'WARN' in msg:
            self.logger.error('Submit job {} error: {}'.format(self.local_id, msg))
        self.remote_id = msg
        self.logger.debug("Job local_id {} remote_id {}".format(self.local_id, self.remote_id))
        return self.remote_id

    def submit(self, remote_job_submission_folder_path=None, remote_sbatch_folder_path=None):
        if remote_job_submission_folder_path is None:
            remote_job_submission_folder_path = self.remote_job_folder_path
        if remote_sbatch_folder_path is None:
            remote_sbatch_folder_path = self.remote_job_folder_path

        # submit job to HPC scheduler
        self.logger.info("Submitting Job {} to queue".format(os.path.join(remote_sbatch_folder_path,
                                                                          self.sbatch_script.file_name)))
        cmd = "cd {} && sbatch {}".format(remote_job_submission_folder_path,
                                          self.sbatch_script.file_name)

        out = self.connection.run_command(cmd)
        remote_id = self._save_remote_id(out)
        self.logger.info("Remote Job ID assigned: {}".format(remote_id))
        self.slurm_out_file_name = "slurm-{}.out".format(remote_id)
        self.remote_slurm_out_file_path = os.path.join(remote_job_submission_folder_path,
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
        # prepare sbatch script and user scripts here
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