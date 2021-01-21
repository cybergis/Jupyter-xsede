from .base import SBatchScript
from .job import SlurmJob
from .connection import SSHConnection


class KeelingSBatchScript(SBatchScript):

    def __init__(self, walltime, ntasks,
                 *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)
        self.remote_workspace_folder_path = "/data/cigi/scratch/cigi-gisolve"
        if self.partition is None:
            self.partition = "node"  # node or sesempi


class KeelingJob(SlurmJob):
    ## keelingjob is the base job class
    ## For other machine, please inherit from KeelingJob
    JOB_ID_PREFIX = "Keeling_"
    backend = "keeling"
    connection_class = SSHConnection
    sbatch_script_class = KeelingSBatchScript

    def prepare(self):
        raise NotImplementedError()
