
from .base import SBatchScript
from .job import Job
from .connection import SSHConnection
from string import Template
import logging
import os

logger = logging.getLogger("cybergis")


class KeelingSBatchScript(SBatchScript):

    KEELING_SBATCH_TEMPLATE = '''
#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime

$exe'''

    def __init__(self, walltime, node, jobname, exec, *args, **kargs):
        self.walltime = walltime
        self.node = node
        self.jobname = jobname
        self.exec = exec

    def parameter_dict(self):
        return dict(jobname=self.jobname,
                    n_nodes=self.node,
                    walltime=self.walltime,
                    exec=self.exec
                    )


class KeelingJob(Job):

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

