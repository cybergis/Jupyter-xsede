from .base import SBatchScript
from .job import SlurmJob
from .connection import SSHConnection
import logging

logger = logging.getLogger("cybergis")


class KeelingSBatchScript(SBatchScript):

    SCRIPT_TEMPLATE = '''
#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$nodes
#SBATCH -t $walltime

$exec'''

    def __init__(self, walltime, nodes, jobname, exec, *args, **kargs):
        self.walltime = walltime
        self.nodes = nodes
        self.jobname = jobname
        self.exec = exec

    def parameter_dict(self):
        return dict(jobname=self.jobname,
                    nodes=self.nodes,
                    walltime=self.walltime,
                    exec=self.exec
                    )


class KeelingJob(SlurmJob):

    JOB_ID_PREFIX = "Keeling_"
    backend = "keeling"
    connection_class = SSHConnection
    sbatch_script_class = KeelingSBatchScript

    def prepare(self):
        raise NotImplementedError()

    def _save_remote_id(self, in_msg):
        if 'ERROR' in in_msg or 'WARN' in in_msg:
            logger.error('Submit job {} error: {}'.format(self.local_id, in_msg))
        self.remote_id = in_msg

