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
