import os

from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from .utils import get_logger

logger = get_logger()


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

    name = "WRFHydroKeelingSBatchScript"
    file_name = "wrfhydro.sbatch"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash

#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

$module_config

## count number of folders job_xxxx
## $$ is to escape single dollar sign, which are used as bash variables later
## See: https://docs.python.org/2.4/lib/node109.html
job_num=$$(ls -dp $remote_workspace_path/$job_folder_name/run/job* | wc -l)

## see: https://docs.nersc.gov/jobs/examples/#multiple-parallel-jobs-sequentially
## loop through 0 -- job_num-1
for (( job_index=0; job_index<$$job_num; job_index++ ))
do
  echo $$job_index
  srun --mpi=pmi2 singularity exec -B $remote_workspace_path/$job_folder_name:/workspace $remote_singularity_img_path python /workspace/run_mpi_call_singularity.py $$job_index
done

'''

    def __init__(self, walltime, ntasks, jobname,
                 job_folder_name=None,
                 *args, **kargs):

        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        self.job_folder_name = job_folder_name
        self.remote_workspace_path = "/data/keeling/a/cigi-gisolve"
        self.remote_singularity_img_path = "/data/keeling/a/cigi-gisolve/simages/wrfhydro_test3.img"
        self.module_config = "module list"


class WRFHydroUserScript(BaseScript):
    name = "WRFHydroUserScript"
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

folder = pathlib.Path("/workspace/run")
# pickle obj has the jobs in right order
pickle_file = folder / "simulation.pkl"

sim = pickle.load(folder.joinpath('simulation.pkl').open('rb'))

job = sim.jobs[job_index]

pprint("==================   Working on {job_id}  ===================".format(job_id=job.job_id))

# side-effect: all processes to do the same copying, which is ok for now
os.system('cp /workspace/run/job_{job_id}/* /workspace/run/'.format(job_id=job.job_id))
os.system('cd /workspace/run && ./wrf_hydro.exe')

pprint("==================  Done with {job_id}  ===================".format(job_id=job.job_id))
exit()


'''

class WRFHydroUserScript2(BaseScript):
    name = "WRFHydroUserScript2"
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


output = wrfhydropy.core.simulation.SimulationOutput()
output.collect_output(sim_dir="/workspace/run")
pprint(output.__dict__)
output_folder_path = "/workspace/output"
if not os.path.exists(output_folder_path):
    os.makedirs(output_folder_path)
for key, val in output.__dict__.items():
    for path in val:
        shutil.move(str(path), os.path.join(output_folder_path, os.path.basename(str(path))))
os.system("cp /workspace/slurm* /workspace/output/")

'''

class WRFHydroKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "WRFHydro_"
    sbatch_script_class = WRFHydroKeelingSBatchScript
    user_script_class = WRFHydroUserScript
    localID = None

    def __init__(self, local_workspace_path, connection, sbatch_script,
                 model_source_folder_path,
                 local_id=None,
                 move_source=False,
                 *args, **kwargs):

        if local_id is None:
            t = str(int(time.time()))
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX + "{}_".format(t))
            self.localID=local_id

        super().__init__(local_workspace_path, connection, sbatch_script, local_id=local_id, *args, **kwargs)

        # fix symbolic here (not required as shutil.copytree() already resolves symbolics to real files)
        # https://www.thetopsites.net/article/52124943.shtml
        # rsync symdir/ symdir_output/ -a --copy-links -v

        # Directory: "/Workspace/Job/Model/"
        model_source_folder_path = self._check_abs_path(model_source_folder_path)
        self.model_source_folder_path = model_source_folder_path
        self.model_folder_name = os.path.basename(self.model_source_folder_path)
        self.move_source = move_source

    def getlocalid(self):
        return self.localID

    def prepare(self):
        # Local Directory: "/Workspace/Job/Model/"

        # copy/move model folder to local job folder
        if self.move_source:
            self.move_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        else:
            self.copy_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        self.local_model_folder_path = os.path.join(self.local_job_folder_path,
                                                    self.model_folder_name)

        self.logger.info(self.local_model_folder_path)

        # connection login remote
        self.connection.login()


        self.remote_workspace_path = self.connection.remote_user_home
        self.remote_job_folder_name = self.local_job_folder_name
        self.remote_job_folder_path = os.path.join(self.remote_workspace_path,
                                                   self.remote_job_folder_name)
        self.remote_model_folder_path = os.path.join(self.remote_job_folder_path,
                                                     self.model_folder_name)

        self.logger.info(self.remote_job_folder_name)
        self.logger.info(self.model_folder_name)


        user_script = WRFHydroUserScript()
        user_script.generate_script(local_folder_path=self.local_job_folder_path)

        user_script2 = WRFHydroUserScript2()
        user_script2.generate_script(local_folder_path=self.local_job_folder_path)

        # save SBatch script
        self.sbatch_script.job_folder_name = self.local_job_folder_name
        self.sbatch_script.generate_script(local_folder_path=self.local_job_folder_path)
        self.sbatch_script.remote_folder_path = self.remote_job_folder_path


    def go(self):
        self.prepare()
        self.upload()
        self.submit()
        self.post_submission()

    def download(self):
        self.connection.download(os.path.join(self.remote_job_folder_path, "run"),
                                 self.local_job_folder_path, remote_is_folder=True)
        self.connection.download(self.remote_slurm_out_file_path, self.local_job_folder_path)

    def submit(self):
        # submit job to HPC scheduler

        self.remote_run_sbatch_folder_path = self.sbatch_script.remote_folder_path
        self.logger.info("Submitting Job {} to queue".format(self.sbatch_script.file_name))
        cmd = "cd {} && sbatch {}".format(self.remote_run_sbatch_folder_path,
                                          self.sbatch_script.file_name)

        out = self.connection.run_command(cmd)
        remote_id = self._save_remote_id(out)
        self.logger.info("Remote Job ID assigned: {}".format(remote_id))
        self.slurm_out_file_name = "slurm-{}.out".format(remote_id)
        self.remote_slurm_out_file_path = os.path.join(self.remote_run_sbatch_folder_path,
                                                       self.slurm_out_file_name)


class WRFHydroCometSBatchScript(WRFHydroKeelingSBatchScript):
    name = "WRFHydroCometSBatchScript"

    def __init__(self, walltime, ntasks, jobname,
                 job_folder_name=None,
                 *args, **kargs):
        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        self.job_folder_name = job_folder_name
        self.remote_workspace_path = "/home/cybergis"
        self.remote_singularity_img_path = "/home/cybergis/SUMMA_IMAGE/wrfhydro_test3.img"
        self.module_config = "module list && module load singularity/3.5 && module list"


class WRFHydroCometJob(WRFHydroKeelingJob):

    JOB_ID_PREFIX = "WRFHydro_"
    sbatch_script_class = WRFHydroCometSBatchScript



import time
from .connection import SSHConnection
def WRFHydroSubmission(workspace, mode_path, nodes, wtime, hpc="keeling", key=None):

    if key is not None:
        key_path = key
    else:
        key_path = "/wrf_hydro_py/keeling_test_20200804.key"

    server_url = "keeling.earth.illinois.edu"
    user_name = "cigi-gisolve"
    WRFHydroSBatchScriptClass = WRFHydroKeelingSBatchScript
    WRFHydroJobClass = WRFHydroKeelingJob

    if hpc == "comet":
        server_url = "comet.sdsc.edu"
        user_name = "cybergis"
        WRFHydroSBatchScriptClass = WRFHydroCometSBatchScript
        WRFHydroJobClass = WRFHydroCometJob



    con = SSHConnection(server_url,
                                user_name=user_name,
                                key_path=key_path)


    wrfhydro_sbatch = WRFHydroSBatchScriptClass(wtime, nodes, "wrfhydro")


    local_workspace_path = workspace
    model_source_folder_path = mode_path
    job = WRFHydroJobClass(local_workspace_path, con, wrfhydro_sbatch, model_source_folder_path,
                             name="WRFHydro")
    job.prepare()
    job.upload()
    job.submit()

    job_local_id = job.local_id
    job_remote_id = job.remote_id
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
