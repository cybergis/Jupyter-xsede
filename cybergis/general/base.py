
from .utils import UtilsMixin
import logging
import os
import uuid
from string import Template

logger = logging.getLogger("cybergis")


class AbstractConnection(object):
    connection_type = str()
    server = str()

    def login(self):
        raise NotImplementedError()

    def logout(self):
        raise NotImplementedError()

    def upload(self, local_fpath, remote_fpath, *args, **kwargs):
        raise NotImplementedError()

    def download(self, remote_fpath, local_fpath, *args, **kwargs):
        raise NotImplementedError()

    def run_command(self, command, *args, **kwargs):
        raise NotImplementedError()


class AbstractScript(object):
    def generate_script(self, *args, **kargs):
        raise NotImplementedError()


class AbstractJob(object):
    pass


class SBatchScript(AbstractScript):
    SBATCH_TEMPLATE = str()
    file_name = "sbatch.sh"
    local_path = None

    walltime = int(100)
    node = int(1)
    jobname = ""
    stdout = None  # Path to output
    stderr = None  # Path to err
    exec = ""

    def parameter_dict(self):
        raise NotImplementedError()

        return dict()

    def generate_script(self, local_folder_path=None):
        sbscript = Template(self.SBATCH_TEMPLATE).substitute(
           **self.parameter_dict()
            )
        logger.debug(sbscript)
        if os.path.isdir(local_folder_path):
            self.local_path = os.path.join(local_folder_path, self.file_name)
            with open(self.local_path, 'w') as f:
                f.write(sbscript)
            logger.debug("SBatchScript saved to {}".format(self.local_path))
        else:
            return sbscript



