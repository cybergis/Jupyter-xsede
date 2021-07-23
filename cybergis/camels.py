import os
from natsort import natsorted
import xarray as xr
import pandas as pd
import glob
import numpy as np

from mpi4py import MPI

# init mpi
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
hostname = MPI.Get_processor_name()
print("{}/{}: {}".format(rank, size, hostname))

job_folder_path = "/workspace"
instance = "1626453788irdY"
instance_path = os.path.join(job_folder_path, instance)

# check output directory
output_path = os.path.join(instance_path, "output")
truth_path = os.path.join(output_path, "truth")


def sort_nc_files(nc_list):
    # name_list = os.listdir(folder_path)
    # name_list = glob.glob(os.path.join(folder_path, keyword))
    # full_list1 = [os.path.join(folder_path, i) for i in name_list if i.endswith(".nc")]
    sorted_list = natsorted(nc_list)
    sorted_list = natsorted(sorted_list, key=lambda v: v.upper())
    print("Number of NC files: {}".format(len(sorted_list)))
    return sorted_list


experiments = ['truth', 'airpres', 'airtemp', 'LWRadAtm', 'pptrate', 'spechum', 'SWRadAtm', 'windspd']

groups = np.array_split(experiments, size)
# assign to process by rank
experiments_assigned = groups[rank].tolist()
print("{}/{}: {}".format(rank, size, str(experiments_assigned)))


def concat(nc_list_sorted, dim, output_nc_path):
    all_ds = [xr.open_dataset(f) for f in nc_list_sorted]
    merged = xr.concat(all_ds, dim)
    merged.to_netcdf(output_nc_path)
    print(output_nc_path)


for experiment in experiments_assigned:
    experiment_type = "constant"
    output_nc_filename = "merged_day/NLDAS{}_{}_configs_latin.nc".format(experiment_type, experiment)
    if experiment.lower() == "truth":
        experiment_type = "truth"
        output_nc_filename = "merged_day/NLDAS{}_configs_latin.nc".format(experiment_type)

    in_path = os.path.join(output_path, experiment_type)
    nc_list = glob.glob(os.path.join(in_path, "*{}*.nc".format(experiment)))
    nc_list_sorted = sort_nc_files(nc_list)
    output_nc_path = os.path.join(output_path, output_nc_filename)
    all_name = [n.split("_")[-2] for n in nc_list_sorted]
    # concat(nc_list_sorted, pd.Index(all_name, name="decision"), output_nc_path)

#### KGE ##########
print("#################### KGE #########################")
import os
from natsort import natsorted
import xarray as xr
import pandas as pd
import numpy as np

from dask_mpi import initialize

initialize()

from dask.distributed import Client

client = Client()  # Connect this local process to remote workers

print(client)

# if rank != 0:
#    exit()

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
constant_vars = ['pptrate', 'airtemp', 'spechum', 'SWRadAtm', 'LWRadAtm', 'windspd', 'airpres']
allforcings = constant_vars + ['truth']
comp_sim = ['scalarInfiltration', 'scalarSurfaceRunoff', 'scalarAquiferBaseflow', 'scalarSoilDrainage',
            'scalarTotalSoilWat', 'scalarCanopyWat', 'scalarLatHeatTotal', 'scalarTotalET', 'scalarTotalRunoff',
            'scalarSWE', 'scalarRainPlusMelt', 'scalarSnowSublimation', 'scalarSenHeatTotal', 'scalarNetRadiation']
var_sim = np.concatenate([constant_vars, comp_sim])


# definitions for KGE computation, correlation with a constant (e.g. all SWE is 0) will be 0 here, not NA
def covariance(x, y, dims=None):
    return xr.dot(x - x.mean(dims), y - y.mean(dims), dims=dims) / x.count(dims)


def correlation(x, y, dims=None):  #
    return (covariance(x, y, dims)) / (x.std(dims) * y.std(dims))


settings_folder = os.path.join(instance_path, "settings")
attrib = xr.open_dataset(settings_folder + '/attributes.nc')
the_hru = np.array(attrib['hruId'])

# check output directory
output_path = os.path.join(instance_path, "output")

# Names for each set of problem complexities.
choices = [1, 0, 0, 0]
suffix = ['_configs_latin.nc', '_latin.nc', '_configs.nc', '_hru.nc']

chunk_size = 88 if size > 88 else size
for i, k in enumerate(choices):
    if k == 0: continue
    sim_truth = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDAStruth' + suffix[i]),
                                chunks={"decision": chunk_size})
    # sim_truth = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDAStruth'+suffix[i]))
    # Get decision names off the files
    if i < 3: decision_set = np.array(sim_truth['decision'])
    if i == 3: decision_set = np.array(['default'])

    # set up error calculations
    summary = ['KGE', 'raw']
    shape = (len(decision_set), len(the_hru), len(allforcings), len(summary))
    dims = ('decision', 'hru', 'var', 'summary')
    coords = {'decision': decision_set, 'hru': the_hru, 'var': allforcings, 'summary': summary}
    error_data = xr.Dataset(coords=coords)
    for s in comp_sim:
        error_data[s] = xr.DataArray(data=np.full(shape, np.nan),
                                     coords=coords, dims=dims,
                                     name=s)

    # calculate summaries
    truth0_0 = sim_truth.drop_vars('hruId').load()
    for v in constant_vars:
        truth = truth0_0
        truth = truth.isel(time=slice(initialization_days * 24, None))  # don't include first year, 5 years
        sim = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDASconstant_' + v + suffix[i]),
                              chunks={"decision": chunk_size})
        # sim = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDASconstant_' + v + suffix[i]))
        sim_truth = xr.open_dataset(os.path.join(output_path, 'merged_day/NLDAStruth' + suffix[i]))
        sim = sim.drop_vars('hruId').load()
        sim = sim.isel(time=slice(initialization_days * 24, None))  # don't include first year, 5 years
        r = sim.mean(dim='time')  # to set up xarray since xr.dot not supported on dataset and have to do loop
        for s in var_sim:
            r[s] = correlation(sim[s], truth[s], dims='time')
        ds = 1 - np.sqrt(np.square(r - 1)
                         + np.square(sim.std(dim='time') / truth.std(dim='time') - 1)
                         + np.square((sim.mean(dim='time') - truth.mean(dim='time')) / truth.std(dim='time')))
        for s in var_sim:
            # if constant and identical, want this as 1.0 -- correlation with a constant = 0 and std dev = 0
            for h in the_hru:
                if i < 3:
                    for d in decision_set:
                        ss = sim[s].sel(hru=h, decision=d)
                        tt = truth[s].sel(hru=h, decision=d)
                        ds[s].loc[d, h] = ds[s].sel(hru=h, decision=d).where(np.allclose(ss, tt, atol=1e-10) == False,
                                                                             other=1.0)
                else:
                    ss = sim[s].sel(hru=h)
                    tt = truth[s].sel(hru=h)
                    ds[s].loc[h] = ds[s].sel(hru=h).where(np.allclose(ss, tt, atol=1e-10) == False, other=1.0)

        ds = ds / (2.0 - ds)
        ds0 = ds.load()
        for s in comp_sim:
            error_data[s].loc[:, :, v, 'KGE'] = ds0[s]
            error_data[s].loc[:, :, v, 'raw'] = sim[s].sum(dim='time')  # this is raw data, not error
        print(v)
    for s in comp_sim:
        error_data[s].loc[:, :, 'truth', 'raw'] = truth[s].sum(dim='time')  # this is raw data, not error

    # save file

    if not os.path.exists(regress_folder_path):
        os.makedirs(regress_folder_path)
    error_data.to_netcdf(os.path.join(regress_folder_path, 'error_data' + suffix[i]))