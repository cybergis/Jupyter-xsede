import os
import time

from .keeling import KeelingJob, KeelingSBatchScript
from .comet import CometSBatchScript
from .base import BaseScript
from .utils import get_logger
from .connection import SSHConnection

logger = get_logger()

SUMMA_SBATCH_SCRIPT_TEMPLATE = \
"""#!/bin/bash

#SBATCH --job-name=$job_name
#SBATCH --ntasks=$ntasks
#SBATCH --nodes=$nodes
#SBATCH --time=$walltime
#SBATCH --partition=$partition
#SBATCH --account=TG-EAR190007
#SBATCH --mem=24GB

## allocated hostnames
echo $$SLURM_JOB_NODELIST

$module_config

srun --mpi=pmi2 singularity exec -B $remote_job_folder_path:/workspace \
   $remote_singularity_img_path \
   python /workspace/runSumma.py

cp slurm-$$SLURM_JOB_ID.out $remote_model_folder_path/output
"""


class SummaKeelingSBatchScript(KeelingSBatchScript):
    file_name = "summa.sbatch"
    SCRIPT_TEMPLATE = SUMMA_SBATCH_SCRIPT_TEMPLATE

    def __init__(self, walltime, ntasks,
                 *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)
        self.remote_singularity_img_path = "/data/keeling/a/cigi-gisolve/simages/summa3_xenial.simg"
        self.module_config = "module list"


class SummaCometSBatchScript(CometSBatchScript):
    file_name = "summa.sbatch"
    SCRIPT_TEMPLATE = SUMMA_SBATCH_SCRIPT_TEMPLATE

    def __init__(self, walltime, ntasks, *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)

        self.remote_singularity_img_path = "/home/cybergis/SUMMA_IMAGE/summa3_xenial.simg"
        self.module_config = "module list && module load singularity/3.5 && module list"
        self.partition = "compute"  # compute, shared


SUMMA_USER_SCRIPT_TEMPLATE = \
"""
import json
import os
from pathlib import Path
import traceback
import numpy as np
from mpi4py import MPI
import subprocess
import pysumma as ps

# init mpi
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
hostname = MPI.Get_processor_name()
print("{}/{}: {}".format(rank, size, hostname))

job_folder_path = "$singularity_job_folder_path"
instance = "$remote_model_folder_name"
instance_path = os.path.join(job_folder_path, instance)

workers_folder_name = "workers"
workers_folder_path = os.path.join(job_folder_path, workers_folder_name)

if rank == 0:
   os.system("mkdir -p {}".format(workers_folder_path))
comm.Barrier()

# copy instance folder to workers folder
new_instance_path = os.path.join(workers_folder_path, instance + "_{}".format(rank))
os.system("cp -rf {} {}".format(instance_path, new_instance_path))

# each process to call install.sh to localize SUMMA model
subprocess.run(
    ["./installTestCases_local.sh"], cwd=new_instance_path,
)

json_path = os.path.join(new_instance_path, "summa_options.json")
ensemble_flag = True
if not os.path.isfile(json_path):
    ensemble_flag = False

try:
    with Path(json_path) as f:
        f.write_text(f.read_text().replace('<PWD>', new_instance_path)
        .replace('PWD', new_instance_path)
        .replace('<BASEDIR>', new_instance_path)
        .replace('BASEDIR', new_instance_path))
    with open(json_path) as f:
        options_dict = json.load(f)
except Exception as ex:
    print("{}/{}: Error in parsing summa_options.js: {}".format(rank, size, ex))
    options_dict = {}

# group config_pairs
options_list = [(k,v) for k,v in options_dict.items()]
options_list.sort()
groups = np.array_split(options_list, size)
# assign to process by rank
config_pair_list = groups[rank].tolist()
print("{}/{}: {}".format(rank, size, str(config_pair_list)))

# if not a ensemble run, assign a fake config_pair to rank 0
if rank == 0 and (not ensemble_flag):
    config_pair_list = [("_single_run", {})]

# file manager path
file_manager = os.path.join(new_instance_path, "$file_manager_rel_path")
print("API submitted file_manager {}".format(file_manager))
executable = "/usr/bin/summa.exe"

#if len(config_pair_list) == 0:
#    config_pair_list = [("_test", {})]
for config_pair in config_pair_list:

    try:
        name = config_pair[0]
        config = config_pair[1]
        print(name)
        print(config)

        if "file_manager" in config:
            file_manager = config["file_manager"]
            print("Get file_manager form summa_options.json {}".format(file_manager))
        
        # init with file_manager
        ss = ps.Simulation(executable, file_manager)
        print("Init with file_manager: {}".format(file_manager))
        # apply config
        ss.apply_config(config)
        # change output folder
        ss.manager["outputPath"].value = ss.manager["outputPath"].value.replace(new_instance_path, instance_path)
        # write configs in mem to disk
        ss.manager.write()
        # run model
        ss.run('local', run_suffix=name)
        # print debug info
        print(ss.stdout) 
        
    except Exception as ex:
        print("Error in ({}/{}) {}: {}".format(rank, size, name, str(config)))
        print(ex)
        print(traceback.format_exc())

comm.Barrier()
print("Done in {}/{} ".format(rank, size))

"""

class SummaUserScript(BaseScript):
    SCRIPT_TEMPLATE = SUMMA_USER_SCRIPT_TEMPLATE
    file_name = "runSumma.py"


class SummaKeelingJob(KeelingJob):
    job_name = "SUMMA"
    sbatch_script_class = SummaKeelingSBatchScript

    def __init__(
            self,
            local_workspace_path,
            local_model_source_folder_path,
            connection,
            sbatch_script,
            file_manager_rel_path=None,
            **kwargs
    ):

        super().__init__(
            local_workspace_path,
            local_model_source_folder_path,
            connection,
            sbatch_script,
            **kwargs
        )

        # Directory: "/Workspace/Job/Model/"
        if file_manager_rel_path is None:
            self.file_manager_rel_path = kwargs['file_manager_rel_path']
        else:
            self.file_manager_rel_path = file_manager_rel_path

        self.model_file_manager_name = os.path.basename(
            self.file_manager_rel_path
        )
        self.local_model_source_file_manager_path = os.path.join(
            self.local_model_source_folder_path, self.file_manager_rel_path
        )

    def prepare(self):
        # Directory: "/Workspace/Job/Model/"

        self.local_model_file_manager_path = os.path.join(
            self.local_model_folder_path, self.file_manager_rel_path
        )

        self.singularity_workspace_path = "/workspace"
        self.singularity_job_folder_path = self.singularity_workspace_path
        self.singularity_model_folder_path = os.path.join(
            self.singularity_job_folder_path, self.remote_model_folder_name
        )

        # save SBatch script
        self.sbatch_script.generate_script(
            local_folder_path=self.local_job_folder_path,
            _additional_parameter_dict=self.to_dict()
        )

        # save user script
        user_script = SummaUserScript()
        user_script.generate_script(
            local_folder_path=self.local_job_folder_path,
            _additional_parameter_dict=self.to_dict()
        )

        # replace local path with remote path
        # summa file_manager:
        # file manager uses local_model_source_folder_path
        # change to singularity_model_folder_path
        self.replace_text_in_file(
            self.local_model_file_manager_path,
            [(self.local_model_source_folder_path, self.singularity_model_folder_path)],
        )

    def download(self):
        self.connection.download(
            os.path.join(self.remote_model_folder_path, "output"),
            self.local_job_folder_path,
            remote_is_folder=True,
        )
        self.connection.download(
            self.remote_slurm_out_file_path, self.local_job_folder_path
        )


class SummaCometJob(SummaKeelingJob):
    sbatch_script_class = SummaCometSBatchScript


def SummaSubmission(workspace, mode_source_folder_path, nodes, wtime,
                    hpc="keeling",
                    key=None, user=None, passwd=None,
                    file_manager_rel_path=""):
    server_url = "keeling.earth.illinois.edu"
    user_name = "cigi-gisolve"
    SummaSBatchScriptClass = SummaKeelingSBatchScript
    SummaJobClass = SummaKeelingJob

    if hpc == "comet" or hpc == "expanse":
        server_url = "login.expanse.sdsc.edu"
        user_name = "cybergis"
        SummaSBatchScriptClass = SummaCometSBatchScript
        SummaJobClass = SummaCometJob
    if user is not None:
        user_name = user

    con = SSHConnection(server_url,
                        user_name=user_name,
                        key_path=key,
                        user_pw=passwd)

    summa_sbatch = SummaSBatchScriptClass(wtime, nodes)

    local_workspace_folder_path = workspace
    local_model_source_folder_path = mode_source_folder_path
    job = SummaJobClass(local_workspace_folder_path, local_model_source_folder_path,
                        con, summa_sbatch,
                        file_manager_rel_path=file_manager_rel_path)
    job.go()

    for i in range(600):
        time.sleep(3)
        status = job.job_status()
        if status == "ERROR":
            logger.info("Job status ERROR")
            break
        elif status == "C" or status == "UNKNOWN":
            logger.info("Job completed: {}; {}".format(job.local_id, job.remote_id))
            job.download()
            break
        else:
            logger.info(status)
    logger.info("Done")
    return job.local_job_folder_path
