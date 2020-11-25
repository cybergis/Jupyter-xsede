import os
from string import Template

from .utils import get_logger


class BaseConnection(object):
    connection_type = str()
    server = str()

    def __init__(self):
        self.logger = get_logger()

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


class BaseScript(object):
    file_name = "script.sh"
    SCRIPT_TEMPLATE = str()

    def __init__(self):
        self.logger = get_logger()

    def parameter_dict(self, *args, **kwargs):
        return self.__dict__

    def generate_script(self, local_folder_path=None, _additional_parameter_dict=None):
        local_folder_path = str(local_folder_path)
        parameter_dict = self.parameter_dict()
        self.logger.info(parameter_dict)
        if isinstance(_additional_parameter_dict, dict):
            parameter_dict.update(_additional_parameter_dict)

        self.logger.debug(self.SCRIPT_TEMPLATE)
        self.logger.debug(parameter_dict)
        script = Template(self.SCRIPT_TEMPLATE).substitute(
            **parameter_dict
        )
        self.logger.debug(script)
        if os.path.isdir(local_folder_path):
            _local_path = os.path.join(local_folder_path, self.file_name)
            with open(_local_path, 'w') as f:
                f.write(script)
            os.chmod(_local_path, 0o775)
            self.logger.debug("{} saved to {}".format(self.name, _local_path))
            return _local_path
        else:
            return script

    def update_template(self, **kw):
        self.SCRIPT_TEMPLATE = Template(self.SCRIPT_TEMPLATE).substitute(kw)


class BaseJob(object):
    def __init__(self):
        self.logger = get_logger()
    pass


class SBatchScript(BaseScript):
    name = "SBatchScript"
    file_name = "job.sbatch"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

srun $exe'''

    # see: https://slurm.schedmd.com/sbatch.html
    walltime = "01:00:00"   # 1 hour
    ntasks = int(1)  # number of task
    jobname = ""
    stdout = None  # Path to output
    stderr = None  # Path to err
    exe = ""

    def __init__(self, walltime_hour, ntasks, jobname, exe, stdout=None, stderr=None):
        super().__init__()
        self.walltime = "{:02d}:00:00".format(int(walltime_hour))
        self.ntasks = ntasks
        self.jobname = jobname
        self.exe = exe
        self.stdout = stdout
        self.stderr = stderr
