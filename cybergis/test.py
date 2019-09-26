from general import *
# from general.summa import *
# from general.keeling import *
# from general.connection import *
# from general.base import *

import logging

logger = logging.getLogger("cybergis")
logger.setLevel("DEBUG")
streamHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

if __name__ == "__main__":

    summa_uscript = SummaUserScript("local_path1111", "instance_name2222", 'file_manager_name3333')

    walltime = 1000
    nodes = 1
    jobname = "testjob"
    summa_sbatch = SummaKeelingSBatchScript(walltime, nodes, jobname, summa_uscript)

    out = summa_sbatch.generate_script(local_folder_path="/tmp")


    keeling_con = SSHConnection("keeling.earth.illinois.edu",
                            user_name="cigi-gisolve",
                            key_path="/Users/zhiyul/Documents/Projects/summa/keeling.key")



    sjob = SummaKeelingJob("/tmp", keeling_con, summa_sbatch,
                           name="my_summa_testcase",
                           model_source_folder_path="/Users/zhiyul/Documents/Projects/summa/my_summa_testcast")
    sjob.prepare()
