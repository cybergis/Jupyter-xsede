
from .base import SBatchScript, Job
from .connection import SSHConnection
from string import Template
import logging

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

    def generate_script(self, local_path=None):
        sbscript = Template(self.KEELING_SBATCH_TEMPLATE).substitute(
            jobname=self.jobname,
            n_nodes=self. node,
            walltime=self.walltime,
            exe=self.exec
            )
        logger.debug(sbscript)
        if local_path is None:
            return sbscript
        else:
            local_path=local_path+"/sbatch.sh"
            with open(local_path, 'w') as f:
                f.write(sbscript)
            logger.debug("KeelingSBatchScript saved to {}".format(local_path))


class KeelingJob(Job):

    JOB_ID_PREFIX = "Keeling_"
    backend = "keeling"
    connection_class = SSHConnection
    sbatch_script_class = KeelingSBatchScript
