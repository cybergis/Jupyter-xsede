import os
import time

from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from .utils import get_logger
from .connection import SSHConnection

logger = get_logger()


class HelloWorldKeelingSBatchScript(KeelingSBatchScript):

    file_name = "helloworld.sbatch"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash

#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

## allocated hostnames
echo $$SLURM_JOB_NODELIST

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
        ## Save sbatch script and user scripts to local job or model folder
        # Local Directory: "/Workspace/Job/Model/"
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


# def HelloWorldSubmission(workspace, mode_source_folder_path, nodes, wtime,
#                        hpc="keeling",
#                        key=None, user=None, passwd=None):
#
#     server_url = "keeling.earth.illinois.edu"
#     user_name = "cigi-gisolve"
#     SBatchScriptClass = HelloWorldKeelingSBatchScript
#     JobClass = HelloWorldKeelingJob
#
#     if hpc == "comet":
#         server_url = "comet.sdsc.edu"
#         user_name = "cybergis"
#         SBatchScriptClass = HelloWorldCometSBatchScript
#         JobClass = HelloWorldCometJob
#
#     if user is not None:
#         user_name = user
#
#     con = SSHConnection(server_url,
#                                 user_name=user_name,
#                                 key_path=key,
#                                 user_pw=passwd)
#
#     sbatch = SBatchScriptClass(wtime, nodes, "helloword")
#
#     local_workspace_folder_path = workspace
#     local_model_source_folder_path = mode_source_folder_path
#     job = JobClass(local_workspace_folder_path, local_model_source_folder_path,
#                    con, sbatch,
#                    name="HelloWorld")
#     job.go()
#
#     for i in range(600):
#         time.sleep(3)
#         status = job.job_status()
#         if status == "ERROR":
#             logger.info("Job status ERROR")
#             break
#         elif status == "C" or status == "UNKNOWN":
#             logger.info("Job completed: {}; {}".format(job.local_id, job.remote_id))
#             job.download()
#             break
#         else:
#             logger.info(status)
#     logger.info("Done")
#     return job.local_job_folder_path
