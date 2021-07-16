import uuid
import os
import time
from .base import SBatchScript, BaseJob
from .connection import SSHConnection
from .utils import UtilsMixin


class SlurmJob(UtilsMixin, BaseJob):
    # This is a Slurm Job
    job_name = "CyberGIS"
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
    connection_class = SSHConnection
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
            local_id = self.random_id(prefix=self.job_name + "_{}_".format(t))
        else:
            local_id = "{}_{}".format(self.job_name, local_id)

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

        self.job_name = name if name is not None else self.job_name
        self.sbatch_script.job_name = self.job_name
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

    def download(self):
        # download job from HPC to local
        pass

    def prepare(self, *args, **kwargs):
        # prepare sbatch script and user scripts here
        pass

    def _save_remote_id(self, msg, *args, **kwargs):
        if 'ERROR' in msg or 'WARN' in msg:
            self.loggert.error('Submit job {} error: {}'.format(self.local_id, msg))
        remote_id = msg.split()[-1]
        self.remote_id = remote_id
        self.logger.debug("Job local_id {} remote_id {}".format(self.local_id, self.remote_id))
        self.slurm_out_file_name = "slurm-{}.out".format(self.remote_id)
        self.remote_slurm_out_file_path = os.path.join(self.remote_run_sbatch_folder_path,
                                                       self.slurm_out_file_name)
        return remote_id

    def job_status(self):
        return self.job_status_pbs(self.remote_id, self.connection)

    # def job_status_pbs(self):
    #     # Slurm supports both squeue (slurm) and qstat (pbs) for queue management
    #     # Based our test, however, squeue Can Not show Completed jobs and kicks job off
    #     # queue record very soon. So it is hard to tell if a run is completed or does not exist
    #     # So we use qstat (pbs) to monitor job status
    #
    #     # get current hpc time and job status (remove line 1 and 3)
    #     remote_id = self.remote_id
    #     cmd = 'qstat {}'.format(remote_id)
    #
    #     try:
    #         out = self.connection.run_command(cmd,
    #                                           line_delimiter=None,
    #                                           raise_on_error=True)
    #         if out is None:
    #             return "UNKNOWN"
    #         # out = \
    #         # ['Job id              Name             Username        Time Use S Queue          ',
    #         # '------------------- ---------------- --------------- -------- - ---------------',
    #         # '3142249             singularity      cigi-gisolve    00:00:00 R node           ']
    #
    #         return out[2].split()[-2]
    #     except Exception as ex:
    #         self.logger.warning("Job status error: ".format(ex.message))
    #         return "ERROR"

    # def job_status_slurm(self):
    #     # monitor job status
    #     # see https://slurm.schedmd.com/squeue.html
    #     # "JOB STATE CODES" section for more states
    #     # PD PENDING, R RUNNING, S SUSPENDED,
    #     # CG COMPLETING, CD COMPLETED
    #
    #     # get current hpc time and job status (remove line 1 and 3)
    #     remote_id = self.remote_id
    #     cmd = 'squeue --job {}'.format(remote_id)
    #     try:
    #         out = self.connection.run_command(cmd,
    #                                           line_delimiter=None,
    #                                           raise_on_error=True)
    #         # out[0].split()
    #         #   ['JOBID', 'PARTITION', 'NAME', 'USER', 'ST', 'TIME', 'NODES', 'NODELIST(REASON)']
    #         # out[1].split()
    #         #   ['3142135', 'node', 'singular', 'cigi-gis', 'R', '0:11', '1', 'keeling-b08']
    #         return out[1].split()[4]
    #     except Exception as ex:
    #         return "ERROR"

    def job_status_sacct(self, remote_id, connection):
        # https://ubccr.freshdesk.com/support/solutions/articles/5000686909-how-to-retrieve-job-history-and-accounting
        cmd = 'sacct -j {} --format=state%-40'.format(remote_id)

        def __check_status():
            out = connection.run_command(cmd,
                                         line_delimiter=None,
                                         raise_on_error=True)
            # PENDING RUNNING COMPLETED FAILED c+
            # https://slurm.schedmd.com/sacct.html

            # State out[0]
            # ---------- out[1]
            # COMPLETED out[2].split()[0]
            # COMPLETED
            # COMPLETED

            status = out[2].split()[0]
            self.logger.warning("Job {} status: {} ".format(remote_id, status))
            if "COMPLETED" in status:
                status = "C"
            elif "CANCELLED" in status:
                status = "Error"
            elif "FAILED" in status:
                status = "Error"
            elif "OUT_OF_MEMORY" in status:
                status = "Error"
            elif "TIMEOUT" in status:
                status = "Error"
            elif "REVOKED" in status:
                status = "Error"
            return status

        try:
            return __check_status()
        except Exception as ex:
            self.logger.error("Got Error when Checking Job {} status: {} ".format(remote_id, ex.message))
            self.logger.error("Trying again... ")
            time.sleep(10)
            try:
                return __check_status()
            except Exception as ex:
                self.logger.error("Got Error Again when Checking Job {} status: {} ".format(remote_id, ex.message))
                return "ERROR"


    def job_status_slurm(self, remote_id, connection):

        cmd = 'squeue --job {}'.format(remote_id)
        try:
            out = connection.run_command(cmd,
                                         line_delimiter=None,
                                         raise_on_error=True)
            # out[0].split()
            #   ['JOBID', 'PARTITION', 'NAME', 'USER', 'ST', 'TIME', 'NODES', 'NODELIST(REASON)']
            # out[1].split()
            #   ['3142135', 'node', 'singular', 'cigi-gis', 'R', '0:11', '1', 'keeling-b08']
            return out[1].split()[4]
        except Exception as ex:
            self.logger.error("Job {} status error: {} ".format(remote_id, ex.message))
            return "ERROR"

    def job_status_pbs(self, remote_id, connection):
        # Slurm supports both squeue (slurm) and qstat (pbs) for queue management
        # Based our test, however, squeue Can Not show Completed jobs and kicks job off
        # queue record very soon. So it is hard to tell if a run is completed or does not exist
        # So we use qstat (pbs) to monitor job status

        # get current hpc time and job status (remove line 1 and 3)
        cmd = 'qstat {}'.format(remote_id)

        try:
            out = connection.run_command(cmd,
                                         line_delimiter=None,
                                         raise_on_error=True)
            if out is None:
                return "UNKNOWN"
            # out = \
            # ['Job id              Name             Username        Time Use S Queue          ',
            # '------------------- ---------------- --------------- -------- - ---------------',
            # '3142249             singularity      cigi-gisolve    00:00:00 R node           ']

            return out[2].split()[-2]
        except Exception as ex:
            self.logger.error("Job {} status error: {} ".format(remote_id, ex.message))
            return "ERROR"
