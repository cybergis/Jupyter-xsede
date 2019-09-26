import logging
import os
from general import *


logger = logging.getLogger("cybergis")
logger.setLevel("DEBUG")
streamHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


if __name__ == "__main__":

    walltime = 1000
    nodes = 1
    jobname = "testjob"
    summa_sbatch = SummaKeelingSBatchScript(walltime, nodes, jobname)

    keeling_con = SSHConnection("keeling.earth.illinois.edu",
                            user_name="cigi-gisolve",
                            key_path="/Users/zhiyul/Documents/Projects/summa/keeling.key")

    model_source_folder_path = "/Users/zhiyul/Documents/Projects/summa/Jupyter-xsede/SummaModel_ReynoldsAspenStand_StomatalResistance_sopron"
    file_manager_path = os.path.join(model_source_folder_path, "settings/summa_fileManager_riparianAspenSimpleResistance.txt")

    sjob = SummaKeelingJob("/tmp", keeling_con, summa_sbatch,
                           model_source_folder_path, file_manager_path,
                           name="my_summa_testcase")
    sjob.prepare()

    a = 1
