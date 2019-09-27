from .base import SBatchScript
from .job import SlurmJob
from .connection import SSHConnection
import logging

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

    def _save_remote_id(self, msg):
        if 'ERROR' in msg or 'WARN' in msg:
            logger.error('Submit job {} error: {}'.format(self.local_id, msg))
        remote_id = msg.split(' ')[-1]
        self.remote_id = remote_id
        logger.debug("Job local_id {} remote_id {}".format(self.local_id, self.remote_id))

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