## Possible Error on keeling when sbatch or srun submits a mpi4py-enabled python job in singularity container:
## Example using sbatch
## #SBATCH --ntasks=4
## srun --mpi=pmi2 singularity exec PATH_TO_SINGULARITY_IMAGE python MPI4PY_ENABLED_PYTHON_SCRIPT
## Example outside sbatch
## srun -n 4 --mpi=pmi2 singularity exec PATH_TO_SINGULARITY_IMAGE python MPI4PY_ENABLED_PYTHON_SCRIPT
## An error occurred in MPI_Init_thread on a NULL communicator MPI_ERRORS_ARE_FATAL 
## (processes in this communicator will now abort, and potentially your MPI job)
## Workaround: 
## Install Miniconda Py37: https://repo.continuum.io/miniconda/Miniconda3-py37_4.8.3-Linux-x86_64.sh
## Install specific "build" of MPI4py for Python3.7 on conda-forge: the one uses MPICH (not OpenMPI) as dependency
## How to find specific MPI4py "build" on conda-forge repo
## Goto https://anaconda.org/conda-forge/mpi4py/files
## Search for "linux-aarch64/mpi4py-3.0.3-py37"
## Click "!" icon and check "depends" field:  "mpich" (not "openmpi")
## conda instal -c conda-forge mpi4py=<VERSION>=<BUILD_ID>
RUN /opt/miniconda3/bin/conda install -c conda-forge mpi4py=3.0.3=py37h0c5ec45_2
