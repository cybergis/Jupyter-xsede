#!/bin/bash

#SBATCH --job-name=mpi4py_hello_world
#SBATCH --ntasks=4
#SBATCH --time=01:00:00
#SBATCH --partition=node

## run in termianl: srun -n 4 --mpi=pmi2 singularity exec -B /data/keeling/a/cigi-gisolve/simages/test_mpi4py:/mnt /data/keeling/a/cigi-gisolve/simages/pysumma_ensemble.img_summa3 python /mnt/mpi4py_hello_world.py

module list

srun --mpi=pmi2 singularity exec -B /data/keeling/a/cigi-gisolve/simages/test_mpi4py:/mnt /data/keeling/a/cigi-gisolve/simages/summa3_xenial.simg_openmpi python /mnt/mpi4py_hello_world.py
