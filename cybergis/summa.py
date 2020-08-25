import os
import time
import datetime
from string import Template

from .keeling import KeelingJob, KeelingSBatchScript
from .base import BaseScript
from .utils import get_logger

logger = get_logger()


class SummaKeelingSBatchScript(KeelingSBatchScript):

    name = "SummaKeelingSBatchScript"
    file_name = "summa.sbatch"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

srun --mpi=pmi2 singularity exec \
   $simg_path \
   python $userscript_path 
'''
    simg_path = "/data/keeling/a/cigi-gisolve/simages/pysumma_ensemble.img_summa3"

    def __init__(self, walltime, ntasks, jobname,
                 userscript_path=None, *args, **kargs):

        super().__init__(walltime, ntasks, jobname, None, *args, **kargs)
        self.userscript_path = userscript_path
        self.simg_path = self.simg_path


class SummaCometSBatchScript(SummaKeelingSBatchScript):

    name = "SummaCometSBatchScript"

    SCRIPT_TEMPLATE = \
'''#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --ntasks=$ntasks
#SBATCH --time=$walltime

module load singularity
srun --mpi=pmi2 singularity exec \
   $simg_path \
   python $userscript_path 
'''
    simg_path = "/home/cybergis/SUMMA_IMAGE/pysumma_ensemble.img_summa3"


class SummaUserScript(BaseScript):
    name = "SummaUserScript"

    SCRIPT_TEMPLATE = \
'''
import json
import os
import numpy as np
from mpi4py import MPI
import pysumma as ps

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
hostname = MPI.Get_processor_name()

print("{}/{}: {}".format(rank, size, hostname))

job_folder_path = "$singularity_job_folder_path"
instance = "$model_folder_name"
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
comm.Barrier()

# file manager path
file_manager = os.path.join(new_instance_path, 'settings/summa_fileManager_riparianAspenSimpleResistance.txt')
print(file_manager)
executable = "/code/bin/summa.exe"

s = ps.Simulation(executable, file_manager)
# fix setting_path to point to this worker
s.manager["settingsPath"].value = s.manager["settingsPath"].value.replace(instance_path, new_instance_path) 

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
        #ss.manager["settingsPath"].value = os.path.join(s.manager["settingsPath"].value, '.pysumma', name)
        ss.run('local', run_suffix=name)
        print(ss.stdout)
    except Exception as ex:
        print("Error in ({}/{}) {}: {}".format(rank, size, name, str(config)))
        print(ex)

comm.Barrier()
print("Done in {}/{} ".format(rank, size))

'''

    singularity_job_folder_path = None
    model_folder_name = None
    file_manager_name = None
    file_name = "runSumma.py"

    def __init__(self, singularity_job_folder_path, model_folder_name,
                 file_manager_name, *args, **kargs):
        super().__init__()
        self.singularity_job_folder_path = singularity_job_folder_path
        self.model_folder_name = model_folder_name
        self.file_manager_name = file_manager_name


class SummaKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "Summa_"
    sbatch_script_class = SummaKeelingSBatchScript
    user_script_class = SummaUserScript
    localID = None

    def __init__(self, local_workspace_path, connection, sbatch_script,
                 model_source_folder_path, model_source_file_manager_rel_path,
                 local_id=None,
                 move_source=False,
                 *args, **kwargs):

        if local_id is None:
            t = str(int(time.time()))
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX + "{}_".format(t))
            self.localID=local_id

        super().__init__(local_workspace_path, connection, sbatch_script, local_id=local_id, *args, **kwargs)

        # Directory: "/Workspace/Job/Model/"
        model_source_folder_path = self._check_abs_path(model_source_folder_path)
        self.model_source_folder_path = model_source_folder_path
        self.model_folder_name = os.path.basename(self.model_source_folder_path)

        self.model_source_file_manager_rel_path = model_source_file_manager_rel_path
        self.model_file_manager_name = os.path.basename(self.model_source_file_manager_rel_path)
        self.model_source_file_manager_path = os.path.join(model_source_folder_path,
                                                           self.model_source_file_manager_rel_path)

        self.move_source = move_source

    def getlocalid(self):
        return self.localID

    def prepare(self):
        # Directory: "/Workspace/Job/Model/"

        # copy/move model folder to local job folder
        if self.move_source:
            self.move_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        else:
            self.copy_local(self.model_source_folder_path,
                            self.local_job_folder_path)
        self.local_model_folder_path = os.path.join(self.local_job_folder_path,
                                                    self.model_folder_name)
        self.local_model_file_manager_path = os.path.join(self.local_model_folder_path,
                                                          self.model_source_file_manager_rel_path)
        # connection login remote
        self.connection.login()

        self.singularity_home_folder_path = "/home/{}".format(self.connection.remote_user_name)
        self.singularity_workspace_path = self.singularity_home_folder_path
        self.singularity_job_folder_path = os.path.join(self.singularity_workspace_path, self.local_job_folder_name)
        self.singularity_model_folder_path = os.path.join(self.singularity_job_folder_path, self.model_folder_name)

        self.remote_workspace_path = self.connection.remote_user_home
        self.remote_job_folder_name = self.local_job_folder_name
        self.remote_job_folder_path = os.path.join(self.remote_workspace_path,
                                                   self.remote_job_folder_name)
        self.remote_model_folder_path = os.path.join(self.remote_job_folder_path,
                                                     self.model_folder_name)

        user_script = SummaUserScript(self.singularity_job_folder_path,
                                      self.model_folder_name,
                                      self.model_file_manager_name)
        self.sbatch_script.userscript_path = user_script

        # save SBatch script
        self.sbatch_script.generate_script(local_folder_path=self.local_model_folder_path)
        self.sbatch_script.remote_folder_path = self.remote_model_folder_path

        # replace local path with remote path
        # sbatch.sh: change userscript path to path in singularity
        # local workspace path -> singularity workspace path (singularity home directory)
        self.replace_text_in_file(self.sbatch_script.local_path,
                                  [(self.local_workspace_path, self.singularity_workspace_path)])

        # summa file_manager:
        # file manager uses model_source_folder_path
        # change to singularity_model_folder_path
        self.replace_text_in_file(self.local_model_file_manager_path,
                                  [(self.model_source_folder_path, self.singularity_model_folder_path)])

    def go(self):
        self.prepare()
        self.upload()
        self.submit()
        self.post_submission()

    def download(self):
        self.connection.download(os.path.join(self.remote_model_folder_path, "output"),
                                 self.local_job_folder_path, remote_is_folder=True)
        self.connection.download(self.remote_slurm_out_file_path, self.local_job_folder_path)


class SummaCometJob(SummaKeelingJob):
    sbatch_script_class = SummaCometSBatchScript

    def post_submission(self):
        gateway_username = os.getenv('JUPYTERHUB_USER')
        if gateway_username is None:
            gateway_username = "anonymous_user"

        # report gateway_user metric to XSEDE
        xsede_key_path = os.getenv('XSEDE_KEY_PATH', "")
        if len(str(xsede_key_path)) == 0:
            return

        cmd_template = 'curl -XPOST --data @$xsede_key_path  \
    --data-urlencode "gatewayuser=$gatewayuser"  \
    --data-urlencode "xsederesourcename=comet.sdsc.xsede"  \
    --data-urlencode "jobid=$jobid"  \
    --data-urlencode "submittime=$submittime" \
    https://xsede-xdcdb-api.xsede.org/gateway/v2/job_attributes'

        parameter_kw = {"xsede_key_path": xsede_key_path,
                        "gatewayuser": gateway_username,
                        "jobid": self.remote_id,
                        "submittime": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

        cmd = Template(cmd_template).substitute(parameter_kw)
        logger.debug(cmd)
        logger.info("Metric sent to XSEDE: {gatewayuser}, {jobid}".format(gatewayuser=gateway_username,
                                                                          jobid=self.remote_id))
        out = self.connection.run_command(cmd)
