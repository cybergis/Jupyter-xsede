import os

from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from .utils import get_logger

logger = get_logger()


class HelloWorldKeelingSBatchScript(KeelingSBatchScript):

    file_name = "helloworld.sbatch"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash

#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

## allocated hostnames
echo "Compute node(s) assigned: $$SLURM_JOB_NODELIST"

mkdir -p $remote_job_folder_path/output
python helloworld.py $remote_model_folder_path/in.txt $remote_job_folder_path/output/out.txt

cp slurm-$$SLURM_JOB_ID.out $remote_job_folder_path/output
'''

    def __init__(self, walltime, ntasks, jobname,
                 *args, **kargs):

        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        self.remote_workspace_folder_path = "/data/cigi/scratch/cigi-gisolve"


class HelloWorldUserScript(BaseScript):
    file_name = "helloworld.py"

    SCRIPT_TEMPLATE = \
'''
import os
import sys
in_path = sys.argv[1]
out_path = sys.argv[2]
with open(in_path, "r") as fin:
    input = fin.readlines()
with open(out_path, "w") as fout:
    fout.write("Hello World!" + os.linesep)
    fout.writelines(input)

'''


class HelloWorldKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "HelloWorld_"
    sbatch_script_class = HelloWorldKeelingSBatchScript

    def prepare(self):
        # save SBatch script
        self.sbatch_script.generate_script(local_folder_path=self.local_job_folder_path,
                                           _additional_parameter_dict=self.to_dict())
        # save user scripts
        user_script = HelloWorldUserScript()
        user_script.generate_script(local_folder_path=self.local_job_folder_path,
                                    _additional_parameter_dict=self.to_dict())

    def download(self):
        self.connection.download(os.path.join(self.remote_job_folder_path, "output"),
                                 self.local_job_folder_path, remote_is_folder=True)


class HelloWorldCometSBatchScript(HelloWorldKeelingSBatchScript):

    def __init__(self, walltime, ntasks, jobname,
                 *args, **kargs):
        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        # Lustre Comet scratch filesystem: /oasis/scratch/comet/$USER/temp_project
        # see: https://www.sdsc.edu/support/user_guides/comet.html
        self.remote_workspace_folder_path = "/oasis/scratch/comet/cybergis/temp_project"


class HelloWorldCometJob(HelloWorldKeelingJob):
    sbatch_script_class = HelloWorldCometSBatchScript
