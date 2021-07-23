import os
import time

from .keeling import KeelingJob, KeelingSBatchScript
from .comet import CometSBatchScript
from .base import BaseScript
from .utils import get_logger
from .connection import SSHConnection

logger = get_logger()

SUMMA_SBATCH_SCRIPT_TEMPLATE_expanse = \
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

# if there is a "regress_data" folder in "output" folder, calculate KGE
if [ -d "$remote_model_folder_path/output/regress_data" ] 
then
    echo "!!!!!!!  Merging and KGE !!!!!!!!!!!!!" 
    singularity exec -B $remote_job_folder_path:/workspace \
      $remote_singularity_img_path \
      bash -c "pip install natsort && python /workspace/camels.py"
    mv $remote_model_folder_path/output $remote_model_folder_path/output2
    mkdir -p $remote_model_folder_path/output
    mv $remote_model_folder_path/output2/regress_data $remote_model_folder_path/output/
fi

cp slurm-$$SLURM_JOB_ID.out $remote_model_folder_path/output
rm -rf ./workers
"""

SUMMA_SBATCH_SCRIPT_TEMPLATE_keeling = \
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
   python /workspace/runSumma.py

# if there is a "regress_data" folder in "output" folder, calculate KGE
if [ -d "$remote_model_folder_path/output/regress_data" ] 
then
    echo "!!!!!!!  Merging and KGE !!!!!!!!!!!!!" 
    singularity exec -B $remote_job_folder_path:/workspace \
      $remote_singularity_img_path \
      bash -c "pip install natsort && python /workspace/camels.py"
    mv $remote_model_folder_path/output $remote_model_folder_path/output2
    mkdir -p $remote_model_folder_path/output
    mv $remote_model_folder_path/output2/regress_data $remote_model_folder_path/output/
fi

cp slurm-$$SLURM_JOB_ID.out $remote_model_folder_path/output
rm -rf ./workers
"""


class SummaKeelingSBatchScript(KeelingSBatchScript):
    file_name = "summa.sbatch"
    SCRIPT_TEMPLATE = SUMMA_SBATCH_SCRIPT_TEMPLATE_keeling

    def __init__(self, walltime, ntasks,
                 *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)
        self.remote_singularity_img_path = "/data/keeling/a/cigi-gisolve/simages/summa3_xenial.simg"
        self.module_config = "module list"


class SummaCometSBatchScript(CometSBatchScript):
    file_name = "summa.sbatch"
    SCRIPT_TEMPLATE = SUMMA_SBATCH_SCRIPT_TEMPLATE_expanse

    def __init__(self, walltime, ntasks, *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)

        self.remote_singularity_img_path = "/home/cybergis/SUMMA_IMAGE/summa3_xenial.simg"
        self.module_config = "module list && module load singularitypro/3.5 && module list"


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
        #print(ss.stdout) 
        
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

CAMELS_USER_SCRIPT_TEMPlATE = \
"""
import os
from natsort import natsorted
import xarray as xr
import pandas as pd

job_folder_path = "$singularity_job_folder_path"
instance = "$remote_model_folder_name"
instance_path = os.path.join(job_folder_path, instance)

# check output directory
output_path = os.path.join(instance_path, "output")
truth_path = os.path.join(output_path, "truth")

def sort_nc_files(folder_path):
    name_list = os.listdir(folder_path)
    full_list1 = [os.path.join(folder_path, i) for i in name_list if i.endswith(".nc")]
    sorted_list = natsorted(full_list1)
    sorted_list = natsorted(sorted_list, key=lambda v: v.upper())
    print("Number of NC files: {}".format(len(sorted_list)))
    return sorted_list

sorted_list = sort_nc_files(truth_path)
all_ds = [xr.open_dataset(f) for f in sorted_list]
all_name = [n.split("_")[-2] for n in sorted_list]
all_merged = xr.concat(all_ds, pd.Index(all_name, name="decision"))
merged_truth_path = os.path.join(output_path, "merged_day/NLDAStruth_configs_latin.nc")
all_merged.to_netcdf(merged_truth_path)
print(merged_truth_path)


constant_path = os.path.join(output_path, "constant")
sorted_list = sort_nc_files(constant_path)

i = 0
all_ds = [xr.open_dataset(f) for f in sorted_list]
ens_decisions = []
for f in sorted_list:
    ens_decisions.append(f.split("_")[-2])
constant_vars= ['airpres','airtemp','LWRadAtm','pptrate','spechum','SWRadAtm','windspd']
for v in constant_vars:
    all_merged = xr.concat(all_ds[i:i+int(len(sorted_list)/7)], pd.Index(ens_decisions[i:i+int(len(sorted_list)/7)], name="decision"))
    merged_constant_path = os.path.join(output_path, 'merged_day/NLDASconstant_' + v +'_configs_latin.nc')
    all_merged.to_netcdf(merged_constant_path)
    print(merged_constant_path)
    i = i + int(len(sorted_list)/7)

#### KGE ##########
print("#################### KGE #########################")
import os
from natsort import natsorted
import xarray as xr
import pandas as pd
import numpy as np

initialization_days = 365
regress_folder_path = os.path.join(output_path, "regress_data")
try:
    regress_param_path = os.path.join(regress_folder_path, "regress_param.json")
    with open(regress_param_path) as f:
        regress_param = json.load(f)
        initialization_days = int(regress_param["initialization_days"])
except Exception as ex:
    pass
print("#################### initialization_days: {}".format(initialization_days))

# Set forcings and create dictionaries, reordered forcings and output variables to match paper 
constant_vars= ['pptrate','airtemp','spechum','SWRadAtm','LWRadAtm','windspd','airpres'] 
allforcings = constant_vars+['truth']
comp_sim=['scalarInfiltration','scalarSurfaceRunoff','scalarAquiferBaseflow','scalarSoilDrainage',
          'scalarTotalSoilWat','scalarCanopyWat','scalarLatHeatTotal','scalarTotalET','scalarTotalRunoff',
          'scalarSWE','scalarRainPlusMelt','scalarSnowSublimation','scalarSenHeatTotal','scalarNetRadiation']
var_sim = np.concatenate([constant_vars, comp_sim])


# definitions for KGE computation, correlation with a constant (e.g. all SWE is 0) will be 0 here, not NA
def covariance(x,y,dims=None):
    return xr.dot(x-x.mean(dims), y-y.mean(dims), dims=dims) / x.count(dims)

def correlation(x,y,dims=None):#
    return (covariance(x,y,dims)) / (x.std(dims) * y.std(dims))


settings_folder = os.path.join(instance_path, "settings")
attrib = xr.open_dataset(settings_folder+'/attributes.nc')
the_hru = np.array(attrib['hruId'])

# check output directory
output_path = os.path.join(instance_path, "output")


# Names for each set of problem complexities.
choices = [1,0,0,0]
suffix = ['_configs_latin.nc','_latin.nc','_configs.nc','_hru.nc']

for i,k in enumerate(choices):
    if k==0: continue
    sim_truth = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDAStruth'+suffix[i]))
    
# Get decision names off the files
    if i<3: decision_set = np.array(sim_truth['decision']) 
    if i==3: decision_set = np.array(['default'])

# set up error calculations
    summary = ['KGE','raw']
    shape = ( len(decision_set),len(the_hru), len(allforcings),len(summary))
    dims = ('decision','hru','var','summary')
    coords = {'decision':decision_set,'hru': the_hru, 'var':allforcings, 'summary':summary}
    error_data = xr.Dataset(coords=coords)
    for s in comp_sim:
        error_data[s] = xr.DataArray(data=np.full(shape, np.nan),
                                     coords=coords, dims=dims,
                                     name=s)
        
# calculate summaries
    truth0_0 = sim_truth.drop_vars('hruId').load()
    for v in constant_vars:
        truth = truth0_0
        truth = truth.isel(time = slice(initialization_days*24,None)) #don't include first year, 5 years
        sim = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDASconstant_' + v + suffix[i]))
        sim = sim.drop_vars('hruId').load()
        sim = sim.isel(time = slice(initialization_days*24,None)) #don't include first year, 5 years
        r = sim.mean(dim='time') #to set up xarray since xr.dot not supported on dataset and have to do loop
        for s in var_sim:         
            r[s] = correlation(sim[s],truth[s],dims='time')
        ds = 1 - np.sqrt( np.square(r-1) 
        + np.square( sim.std(dim='time')/truth.std(dim='time') - 1) 
        + np.square( (sim.mean(dim='time') - truth.mean(dim='time'))/truth.std(dim='time') ) )
        for s in var_sim:   
            #if constant and identical, want this as 1.0 -- correlation with a constant = 0 and std dev = 0
            for h in the_hru:
                if i<3: 
                        for d in decision_set:  
                            ss = sim[s].sel(hru=h,decision = d)
                            tt = truth[s].sel(hru=h,decision = d)
                            ds[s].loc[d,h] =ds[s].sel(hru=h,decision = d).where(np.allclose(ss,tt, atol = 1e-10)==False, other=1.0)
                else:
                    ss = sim[s].sel(hru=h)
                    tt = truth[s].sel(hru=h)
                    ds[s].loc[h] =ds[s].sel(hru=h).where(np.allclose(ss,tt, atol = 1e-10)==False, other=1.0)

        ds = ds/(2.0-ds)
        ds0 = ds.load()
        for s in comp_sim:
            error_data[s].loc[:,:,v,'KGE']  = ds0[s]
            error_data[s].loc[:,:,v,'raw']  = sim[s].sum(dim='time') #this is raw data, not error
        print(v)
    for s in comp_sim:
        error_data[s].loc[:,:,'truth','raw']  = truth[s].sum(dim='time') #this is raw data, not error      
        
    #save file
    
    if not os.path.exists(regress_folder_path):
        os.makedirs(regress_folder_path)
    error_data.to_netcdf(os.path.join(regress_folder_path, 'error_data'+suffix[i]))

"""


class CAMELSUserScript(BaseScript):
    SCRIPT_TEMPLATE = CAMELS_USER_SCRIPT_TEMPlATE
    file_name = "camels.py"


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

        # save user scripts for camels
        camels_user_scripts = CAMELSUserScript()

        camels_user_scripts.generate_script(local_folder_path=self.local_job_folder_path,
                                            _additional_parameter_dict=self.to_dict())

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
