import os
import time
import datetime
from string import Template

from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from .utils import get_logger
from .connection import SSHConnection

logger = get_logger()


class SummaKeelingSBatchScript(KeelingSBatchScript):

    file_name = "summa.sbatch"

    SCRIPT_TEMPLATE = """#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime
#SBATCH --partition=$partition

## allocated hostnames
echo $$SLURM_JOB_NODELIST

$module_config

srun --mpi=pmi2 singularity exec -B $remote_job_folder_path:/workspace \
   $remote_singularity_img_path \
   python /workspace/runSumma.py

cp slurm-$$SLURM_JOB_ID.out $remote_model_folder_path/output
"""

    def __init__(self, walltime, ntasks, jobname,
                 *args, **kargs):

        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        self.remote_workspace_folder_path = "/data/cigi/scratch/cigi-gisolve"
        self.remote_singularity_img_path = "/data/keeling/a/cigi-gisolve/simages/pysumma_ensemble.img_summa3"
        self.module_config = "module list"
        self.partition = "node"  # node sesempi


class SummaCometSBatchScript(SummaKeelingSBatchScript):

    def __init__(self, walltime, ntasks, jobname,
                 *args, **kargs):
        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        # Lustre Comet scratch filesystem: /oasis/scratch/comet/$USER/temp_project
        # see: https://www.sdsc.edu/support/user_guides/comet.html
        self.remote_workspace_folder_path = "/oasis/scratch/comet/cybergis/temp_project"
        self.remote_singularity_img_path = "/home/cybergis/SUMMA_IMAGE/pysumma_ensemble.img_summa3"
        self.module_config = "module list && module load singularity/3.5 && module list"
        self.partition = "compute"  # compute, shared


class SummaUserScript(BaseScript):
    name = "SummaUserScript"

    SCRIPT_TEMPLATE = """
import json
import os
import numpy as np
from mpi4py import MPI
import subprocess
import pysumma as ps

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
hostname = MPI.Get_processor_name()

print("{}/{}: {}".format(rank, size, hostname))

job_folder_path = "$singularity_job_folder_path"
instance = "$remote_model_folder_name"
instance_path = os.path.join(job_folder_path, instance)
json_path = os.path.join(job_folder_path, instance, "summa_options.json")

workers_folder_name = "workers"
workers_folder_path = os.path.join(job_folder_path, workers_folder_name)

if rank == 0:
   os.system("mkdir -p {}".format(workers_folder_path))
comm.Barrier()

try:
    with open(json_path) as f:
        options_dict = json.load(f)
except:
    options_dict = {}
options_list = [(k,v) for k,v in options_dict.items()]
options_list.sort()
groups = np.array_split(options_list, size)
config_pair_list = groups[rank].tolist()

# copy instance folder to workers folder
new_instance_path = os.path.join(workers_folder_path, instance + "_{}".format(rank))
os.system("cp -rf {} {}".format(instance_path, new_instance_path))
# sync: make every rank finishes copying
subprocess.run(
    ["./installTestCases_local.sh"], cwd=new_instance_path,
)
comm.Barrier()

# file manager path
file_manager = os.path.join(new_instance_path, "$file_manager_rel_path")
print(file_manager)
executable = "/usr/bin/summa.exe"

s = ps.Simulation(executable, file_manager)
# fix setting_path to point to this worker
s.manager["settingsPath"].value = s.manager["settingsPath"].value.replace(instance_path, new_instance_path) 
s.manager["outputPath"].value = os.path.join(instance_path, "output/")

# Dont not use this as it rewrites every files including those in original folder -- Race condition
#s._write_configuration()

# Instead, only rewrite filemanager
s.manager.write()

if len(config_pair_list) == 0:
    config_pair_list = [("_test", {})]
for config_pair in config_pair_list:

    try:
        name = config_pair[0]
        config = config_pair[1]
        print(name)
        print(config)
        print(type(config))
        
        # create a new Simulation obj each time to avoid potential overwriting issue or race condition
        ss = ps.Simulation(executable, file_manager, False)
        ss.initialize()
        ss.apply_config(config)
        ss.run('local', run_suffix=name)
        print(ss.stdout)
    except Exception as ex:
        print("Error in ({}/{}) {}: {}".format(rank, size, name, str(config)))
        print(ex)

comm.Barrier()
print("Done in {}/{} ".format(rank, size))

"""

    file_name = "runSumma.py"


class SummaKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "Summa_"
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
            self.logger.error("33333333333333333333333")
            self.logger.error(kwargs)
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

    def post_submission(self):
        gateway_username = os.getenv("JUPYTERHUB_USER")
        if gateway_username is None:
            gateway_username = "anonymous_user"

        # report gateway_user metric to XSEDE
        xsede_key_path = os.getenv("XSEDE_KEY_PATH", "")
        if len(str(xsede_key_path)) == 0:
            return

        cmd_template = 'curl -XPOST --data @$xsede_key_path  \
    --data-urlencode "gatewayuser=$gatewayuser"  \
    --data-urlencode "xsederesourcename=comet.sdsc.xsede"  \
    --data-urlencode "jobid=$jobid"  \
    --data-urlencode "submittime=$submittime" \
    https://xsede-xdcdb-api.xsede.org/gateway/v2/job_attributes'

        parameter_kw = {
            "xsede_key_path": xsede_key_path,
            "gatewayuser": gateway_username,
            "jobid": self.remote_id,
            "submittime": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

        cmd = Template(cmd_template).substitute(parameter_kw)
        logger.debug(cmd)
        logger.info(
            "Metric sent to XSEDE: {gatewayuser}, {jobid}".format(
                gatewayuser=gateway_username, jobid=self.remote_id
            )
        )
        out = self.connection.run_command(cmd)


def SummaSubmission(workspace, mode_source_folder_path, nodes, wtime,
                       hpc="keeling",
                       key=None, user=None, passwd=None,
                    file_manager_rel_path=""):

    server_url = "keeling.earth.illinois.edu"
    user_name = "cigi-gisolve"
    SummaSBatchScriptClass = SummaKeelingSBatchScript
    SummaJobClass = SummaKeelingJob

    if hpc == "comet":
        server_url = "comet.sdsc.edu"
        user_name = "cybergis"
        SummaSBatchScriptClass = SummaCometSBatchScript
        SummaJobClass = SummaCometJob
    if user is not None:
        user_name = user

    con = SSHConnection(server_url,
                                user_name=user_name,
                                key_path=key,
                                user_pw=passwd)

    summa_sbatch = SummaSBatchScriptClass(wtime, nodes, "summa")

    local_workspace_folder_path = workspace
    local_model_source_folder_path = mode_source_folder_path
    job = SummaJobClass(local_workspace_folder_path, local_model_source_folder_path,
                           con, summa_sbatch,
                             name="Summa",
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
