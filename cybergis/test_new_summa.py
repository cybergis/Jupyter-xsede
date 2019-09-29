import logging
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

    file_manger_rel_path = "settings/summa_fileManager_riparianAspenSimpleResistance.txt"

    local_workspace_path = "/Users/zhiyul/Documents/Projects/summa/workspace"
    sjob = SummaKeelingJob(local_workspace_path, keeling_con, summa_sbatch,
                           model_source_folder_path, file_manger_rel_path,
                           name="my_summa_testcase")
    sjob.go()

    import time
    for i in range(100):
        time.sleep(1)
        status = sjob.job_status()
        if status == "ERROR":
            logger.error("Job status ERROR")
            break
        elif status == "C":
            logger.info("Job completed: {}; {}".format(sjob.local_id, sjob.remote_id))
            sjob.download()
            break
        else:
            logger.info(status)



    logger.debug("Done")
