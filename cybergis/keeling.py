import logging
import os

from .base import SBatchScript
from .job import SlurmJob
from .connection import SSHConnection


logger = logging.getLogger("cybergis")


class KeelingSBatchScript(SBatchScript):
    pass


class KeelingJob(SlurmJob):

    JOB_ID_PREFIX = "Keeling_"
    backend = "keeling"
    connection_class = SSHConnection
    sbatch_script_class = KeelingSBatchScript

    def prepare(self):
        raise NotImplementedError()

    def _save_remote_id(self, msg, *args, **kwargs):
        if 'ERROR' in msg or 'WARN' in msg:
            logger.error('Submit job {} error: {}'.format(self.local_id, msg))
        remote_id = msg.split()[-1]
        self.remote_id = remote_id
        logger.debug("Job local_id {} remote_id {}".format(self.local_id, self.remote_id))
        self.slurm_out_file_name = "slurm-{}.out".format(self.remote_id)
        self.remote_slurm_out_file_path = os.path.join(self.remote_run_sbatch_folder_path,
                                                       self.slurm_out_file_name)
        return remote_id

    def job_status(self):
        # Keeling has both squeue (slurm) and qstat (pbs) for queue management
        # Based our test, however, squeue Can Not show Completed jobs and kicks job off
        # queue record very soon. So it is hard to tell if a run is completed or does not exist
        # So we use qstat (pbs) to monitor job status

        # get current hpc time and job status (remove line 1 and 3)
        remote_id = self.remote_id
        cmd = 'qstat {}'.format(remote_id)

        try:
            out = self.connection.run_command(cmd,
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
            logger.warning("Job status error: ".format(ex.message))
            return "ERROR"
