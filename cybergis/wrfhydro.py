import os
import time

from .keeling import KeelingJob, KeelingSBatchScript
from .comet import CometSBatchScript
from .base import BaseScript
from .utils import get_logger
from .connection import SSHConnection

logger = get_logger()

WRFHYDRO_SBATCH_SCRIPT_TEMPLATE_keeling = \
'''#!/bin/bash

#SBATCH --job-name=$job_name
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime
#SBATCH --partition=$partition

## allocated hostnames
echo $$SLURM_JOB_NODELIST

$module_config

## compile mode from source
singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/compile_wrfhydro.py

## change wrf_hydro.exe permission
chmod +x $remote_model_folder_path/wrf_hydro.exe

## count number of folders job_xxxx
## $$ is to escape single dollar sign, which are used as bash variables later
## See: https://docs.python.org/2.4/lib/node109.html
job_num=$$(find $remote_model_folder_path/job_* -type d | wc -l)

## see: https://docs.nersc.gov/jobs/examples/#multiple-parallel-jobs-sequentially
## loop through 0 -- job_num-1
for (( job_index=0; job_index<$$job_num; job_index++ ))
do
  echo $$job_index

  ## parallel run
  srun --mpi=pmi2 singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/run_mpi_call_singularity.py $$job_index

  ## sequential run for testing
  ## singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/run_mpi_call_singularity.py $$job_index

  if [ $$job_index -lt $$((job_num-1)) ]
    then
       echo "sleep for 5s"
       sleep 5
  fi
done

singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/copy_outputs.py

'''


WRFHYDRO_SBATCH_SCRIPT_TEMPLATE_expanse = \
'''#!/bin/bash

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

## compile mode from source
singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/compile_wrfhydro.py

## change wrf_hydro.exe permission
chmod +x $remote_model_folder_path/wrf_hydro.exe

## count number of folders job_xxxx
## $$ is to escape single dollar sign, which are used as bash variables later
## See: https://docs.python.org/2.4/lib/node109.html
job_num=$$(find $remote_model_folder_path/job_* -type d | wc -l)

## see: https://docs.nersc.gov/jobs/examples/#multiple-parallel-jobs-sequentially
## loop through 0 -- job_num-1
for (( job_index=0; job_index<$$job_num; job_index++ ))
do
  echo $$job_index

  ## parallel run
  srun --mpi=pmi2 singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/run_mpi_call_singularity.py $$job_index

  ## sequential run for testing
  ## singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/run_mpi_call_singularity.py $$job_index

  if [ $$job_index -lt $$((job_num-1)) ]
    then
       echo "sleep for 5s"
       sleep 5
  fi
done

singularity exec -B $remote_job_folder_path:/workspace $remote_singularity_img_path python /workspace/copy_outputs.py

'''

class WRFHydroKeelingSBatchScript(KeelingSBatchScript):
    '''
    Current implementation follows the "Host MPI" or "Hybrid" model
    where Host MPI installation (outside singularity) calls MPI installation inside singularity
    to execute the MPI Program inside singularity
    eg: mpirun -np 2 singularity exec PATH_TO_MPI_PROGRAM_INSIDE_SINGULARITY
    See: https://sylabs.io/guides/3.3/user-guide/mpi.html

    The MPI_PROGRAM here is a Python script (User Script) that makes use of wrf_hydro_py to invoke wrf_hydro.exe binary.
    Ideally, we want the Python script (User Script) to be "MPI-Aware" using MPI4Py, like only
    one python process (Rank0) to do the copyings of config files. Then, each python process launches only one wrf_hydro.exe process
    (since there are NP Python processes launched by MPI so we would have NP wrf_hydro.exe processes launched,
    which are expected to run in parallel)

    However, things do not work as expected . If the Python script (User Script) is MPI-Aware, it would use the established MPI environment.
    So when this Python script launches wrf_hydro.exe process. the wrf_hydro.exe CANNOT use the same established MPI environment again.

    As a trade-off, current implementation of Python script (User Script) is Not MPI-Aware, and the logics that loop through all model runs (Jobs) is
    in the Sbatch Script.

    ------------

    Each model run ("Job" object in wrf_hydro_py) has its own folder named "jobXXXX"
    this Sbatch Script gets job_num by counting "jobXXXX" folders and loops through job indices [0 to job_num-1]
    the job_index is passed into the Python Script (User Script), which parses 'simulation.pkl' file and extracts the Job
    object by job_index. The Jobs will run in the same order in which they were stored.
    '''

    file_name = "wrfhydro.sbatch"

    SCRIPT_TEMPLATE = WRFHYDRO_SBATCH_SCRIPT_TEMPLATE_keeling

    def __init__(self, walltime, ntasks, *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)

        self.remote_singularity_img_path = "/data/keeling/a/cigi-gisolve/simages/wrfhydro_xenial.simg"
        self.module_config = "module list"


class WRFHydroUserScript(BaseScript):
    file_name = "run_mpi_call_singularity.py"

    SCRIPT_TEMPLATE = \
'''
import os
import sys
import pickle
import pathlib
from pprint import pprint

print ('Number of arguments:', len(sys.argv), 'arguments.')
print ('Argument List:', str(sys.argv))

job_index = int(sys.argv[1])

folder = pathlib.Path("/workspace/$remote_model_folder_name")
# pickle obj has the jobs in right order
pickle_file = folder / "simulation.pkl"

sim = pickle.load(folder.joinpath('simulation.pkl').open('rb'))

job = sim.jobs[job_index]

pprint("==================   Working on {job_id}  ===================".format(job_id=job.job_id))

# side-effect: all processes to do the same copying, which is ok for now
os.system('cp /workspace/$remote_model_folder_name/job_{job_id}/* /workspace/$remote_model_folder_name/'.format(job_id=job.job_id))
os.system('cd /workspace/$remote_model_folder_name && ./wrf_hydro.exe')

pprint("==================  Done with {job_id}  ===================".format(job_id=job.job_id))
exit()

'''


class WRFHydroUserScript2(BaseScript):
    file_name = "copy_outputs.py"

    SCRIPT_TEMPLATE = \
'''
import os
import sys
import shutil
import pickle
import pathlib
from pprint import pprint
import wrfhydropy

output_folder_path = "/workspace/output"
if not os.path.exists(output_folder_path):
    os.makedirs(output_folder_path)
try:    
    output = wrfhydropy.core.simulation.SimulationOutput()
    output.collect_output(sim_dir="/workspace/$remote_model_folder_name")
    for key, val in output.__dict__.items():
        for path in val:
            #shutil.copyfile(str(path), os.path.join(output_folder_path, os.path.basename(str(path))))
            shutil.move(str(path), os.path.join(output_folder_path, os.path.basename(str(path))))
except Exception:
    pass
os.system("cp /workspace/slurm* /workspace/output/")
os.system("cp /workspace/$remote_model_folder_name/diag* /workspace/output/")
os.system("cp /workspace/$remote_model_folder_name/*stdout /workspace/output/")
os.system("cp /workspace/$remote_model_folder_name/*stderr /workspace/output/")
os.system("cp /workspace/$remote_model_folder_name/*.exe /workspace/output/")
os.system("cp /workspace/$remote_model_folder_name/*.pkl /workspace/output/")
'''


class WRFHydroUserScript3(BaseScript):
    file_name = "compile_wrfhydro.py"

    SCRIPT_TEMPLATE = \
'''
import wrfhydropy
import pathlib
import os
import pickle
import tempfile


in_model_pkl = '/workspace/$remote_model_folder_name/WrfHydroModel.pkl'
out_folder = '/workspace/$remote_model_folder_name'
repo = "https://github.com/NCAR/wrf_hydro_nwm_public.git"

model = pickle.load(pathlib.Path(in_model_pkl).open('rb'))
config = model.model_config
commit_id = model.git_hash
print("{}; {}".format(commit_id, config))

temp = tempfile.mkdtemp()

cmd = "git clone {repo} {temp} && cd {temp} && git checkout {commit_id}".format(repo=repo, temp=temp, commit_id=commit_id)
os.system(cmd)

experiment_dir = pathlib.Path(temp)
model_src = experiment_dir / 'trunk/NDHMS'

model = wrfhydropy.Model(
    model_src,
    compiler='gfort',
    model_config=config)
    
compile_dir = pathlib.Path(out_folder)
model.compile(compile_dir)

'''


class WRFHydroKeelingJob(KeelingJob):
    job_name = "WRFHydro"
    sbatch_script_class = WRFHydroKeelingSBatchScript

    def prepare(self):
        ## Save sbatch script and user scripts to local job or model folder
        # Local Directory: "/Workspace/Job/Model/"
        # save SBatch script
        self.sbatch_script.generate_script(local_folder_path=self.local_job_folder_path,
                                           _additional_parameter_dict=self.to_dict())
        # save user scripts
        user_scripts = [WRFHydroUserScript(), WRFHydroUserScript2(), WRFHydroUserScript3()]
        for user_script in user_scripts:
            user_script.generate_script(local_folder_path=self.local_job_folder_path,
                                        _additional_parameter_dict=self.to_dict())

    def download(self):
        self.connection.download(os.path.join(self.remote_job_folder_path, "output"),
                                 self.local_job_folder_path, remote_is_folder=True)
        self.connection.download(self.remote_slurm_out_file_path, self.local_job_folder_path)


class WRFHydroCometSBatchScript(CometSBatchScript):
    file_name = "wrfhydro.sbatch"
    SCRIPT_TEMPLATE = WRFHYDRO_SBATCH_SCRIPT_TEMPLATE_expanse

    def __init__(self, walltime, ntasks, *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)

        self.remote_singularity_img_path = "/home/cybergis/SUMMA_IMAGE/wrfhydro_xenial.simg"
        self.module_config = "module list && module load singularitypro/3.5 && module list"


class WRFHydroCometJob(WRFHydroKeelingJob):
    sbatch_script_class = WRFHydroCometSBatchScript


def WRFHydroSubmission(workspace, mode_source_folder_path, nodes, wtime,
                       hpc="keeling",
                       key=None, user=None, passwd=None):
    server_url = "keeling.earth.illinois.edu"
    user_name = "cigi-gisolve"
    WRFHydroSBatchScriptClass = WRFHydroKeelingSBatchScript
    WRFHydroJobClass = WRFHydroKeelingJob

    if hpc == "comet" or hpc == "expanse":
        server_url = "login.expanse.sdsc.edu"
        user_name = "cybergis"
        WRFHydroSBatchScriptClass = WRFHydroCometSBatchScript
        WRFHydroJobClass = WRFHydroCometJob
    if user is not None:
        user_name = user

    con = SSHConnection(server_url,
                        user_name=user_name,
                        key_path=key,
                        user_pw=passwd)

    wrfhydro_sbatch = WRFHydroSBatchScriptClass(wtime, nodes)

    local_workspace_folder_path = workspace
    local_model_source_folder_path = mode_source_folder_path
    job = WRFHydroJobClass(local_workspace_folder_path, local_model_source_folder_path,
                           con, wrfhydro_sbatch)
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
