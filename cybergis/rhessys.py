import os
import time

from .keeling import KeelingJob, KeelingSBatchScript
from .comet import CometSBatchScript
from .base import BaseScript
from .utils import get_logger
from .connection import SSHConnection

logger = get_logger()

RHESSys_SBATCH_SCRIPT_TEMPLATE_expanse = \
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
   python /workspace/runRHESSys.py

cp slurm-$$SLURM_JOB_ID.out $remote_model_folder_path/model/output
echo done
"""

RHESSys_SBATCH_SCRIPT_TEMPLATE_keeling = \
"""#!/bin/bash

#SBATCH --job-name=$job_name
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime
#SBATCH --partition=$partition

## allocated hostnames
echo $$SLURM_JOB_NODELIST

$module_config

srun --mpi=pmi2 singularity exec -B $remote_job_folder_path:/workspace \
   $remote_singularity_img_path \
   python /workspace/runRHESSys.py

cp slurm-$$SLURM_JOB_ID.out $remote_model_folder_path/model/output
echo done
"""

class RHESSysKeelingSBatchScript(KeelingSBatchScript):
    file_name = "rhessys.sbatch"
    SCRIPT_TEMPLATE = RHESSys_SBATCH_SCRIPT_TEMPLATE_keeling

    def __init__(self, walltime, ntasks,
                 *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)
        self.remote_singularity_img_path = "/data/keeling/a/cigi-gisolve/simages/rhessys72.simg"
        self.module_config = "module list"

class RHESSysCometSBatchScript(CometSBatchScript):
    file_name = "rhessys.sbatch"
    SCRIPT_TEMPLATE = RHESSys_SBATCH_SCRIPT_TEMPLATE_expanse

    def __init__(self, walltime, ntasks, *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)

        self.remote_singularity_img_path = "/home/cybergis/SUMMA_IMAGE/rhessys72.simg"
        self.module_config = "module list && module load singularitypro && module list"


RHESSys_USER_SCRIPT_TEMPLATE = \
"""
import json
import os, shutil
from pathlib import Path
import traceback
import numpy as np
from mpi4py import MPI
import subprocess
import pyrhessys as pr
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
# each process to call install.sh to localize RHESSys model
subprocess.run(
    ["./installTestCases_local.sh"], cwd=new_instance_path,
)
json_path = os.path.join(new_instance_path, "rhessys_options.json")
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
    print("{}/{}: Error in parsing rhessys_options.js: {}".format(rank, size, ex))
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
executable = "/code/rhessysEC.7.2"
print(instance_path)
model_dir = os.path.join(new_instance_path, "model")

for config_pair in config_pair_list:
    try:
        name = config_pair[0]
        config = config_pair[1]
        print(name)
        print(config)
        
        ss = pr.Simulation(executable, model_dir)
        
        f = open(os.path.join(model_dir, 'init_parameters.json'), 'r')
        data = json.load(f)
        ss.parameters['version'] = data['version']
        ss.parameters['start_date'] = data['start_date'] 
        ss.parameters['end_date'] = data['end_date']
        ss.parameters['gw1'] = data['gw1']
        ss.parameters['gw2'] = data['gw2']
        ss.parameters['s1'] = data['s1']
        ss.parameters['s2'] = data['s2']
        ss.parameters['s3'] = data['s3']
        ss.parameters['snowEs'] = data['snowEs']
        ss.parameters['snowTs'] = data['snowTs']
        ss.parameters['sv1'] = data['sv1']
        ss.parameters['sv2'] = data['sv2']
        ss.parameters['svalt1'] = data['svalt1']
        ss.parameters['svalt2'] = data['svalt2']
        ss.parameters['locationid'] = data['locationid']

        # apply config
        ss.apply_config(config)
        # change output folder
        #ss.manager["outputPath"].value = ss.manager["outputPath"].value.replace(new_instance_path, instance_path)
        # write configs in mem to disk
        #ss.manager.write()
        # run model
        ss.run('local', run_suffix=name)
        
        shutil.copy(ss.output + "/" + name + "_basin.daily", instance_path+"/model/output/")
        # print debug info
        #print(ss.stdout) 
        
    except Exception as ex:
        print("Error in ({}/{}) {}: {}".format(rank, size, name, str(config)))
        print(ex)
        print(traceback.format_exc())
comm.Barrier()
print("Done in {}/{} ".format(rank, size))
"""

class RHESSysUserScript(BaseScript):
    SCRIPT_TEMPLATE = RHESSys_USER_SCRIPT_TEMPLATE
    file_name = "runRHESSys.py"


class RHESSysKeelingJob(KeelingJob):
    job_name = "RHESSys"
    sbatch_script_class = RHESSysKeelingSBatchScript

    def prepare(self):
        # Directory: "/Workspace/Job/Model/"
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
        user_script = RHESSysUserScript()
        user_script.generate_script(
            local_folder_path=self.local_job_folder_path,
            _additional_parameter_dict=self.to_dict()
        )

    def download(self):
        self.connection.download(
            os.path.join(self.remote_model_folder_path, "model/output"),
            self.local_job_folder_path,
            remote_is_folder=True,
        )
        self.connection.download(
            self.remote_slurm_out_file_path, self.local_job_folder_path
        )

class RHESSysCometJob(RHESSysKeelingJob):
    sbatch_script_class = RHESSysCometSBatchScript
