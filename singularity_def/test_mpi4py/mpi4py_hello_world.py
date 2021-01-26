from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
hostname = MPI.Get_processor_name()
ver = MPI.Get_version()
lib_ver = MPI.Get_library_version()
lib_ver = ""

try:
    print("Hello World! ({}/{}: {}; Ver{}; Lib{})".format(rank, size, hostname, ver, lib_ver))
    comm.Barrier()
    print("Done! ({}/{}: {})".format(rank, size, hostname))
except Exception as ex:
    print("{} ({}/{}: {}; Ver{}; Lib{})".format(ex, rank, size, hostname, ver, lib_ver))
