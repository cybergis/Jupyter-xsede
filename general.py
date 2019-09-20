# class JobManager(object):
#     # threading to manage multiple jobs
#     pass
#


class CyberGISJob(object):
    name = ""
    local_id = ""
    remote_id = ""
    state = ""

    sbatch_script = ""
    user_script = ""

    remote_data_path = ""
    remote_output_path = ""
    local_data_path = ""
    local_output_path = ""
    ssh_connection = None

    def upload(self):
        # organize run_script and local data
        # upload to HPC
        # no remote_id
        self.ssh_connection.upload(self.local_data_path,
                                   self.remote_data_path)
        pass

    def submit(self):
        # submit job to HPC scheduler
        self.ssh_connection.runCommand(self.sbatch_script)
        self.remote_id = ""


    def download(self):
        # download job from HPC to local
        self.ssh_connection.download(self.remote_output_path, self.local_output_path)
        pass


class SummaJob(CyberGISJob):


    pass


class AbstractScript(object):
    def generarte_script(self):
        pass


class SBatchScript(AbstractScript):
    walltime = None
    node = int(1)

class UserScript(AbstractScript):
    run_command = ""

class SummaUserScript(UserScript):
    pass

class SummaSBatchScript(SBatchScript):
    pass


class SSHConnection(object):

    def login(self):
        pass

    def logout(self):
        pass

    def upload(self, local_path, remote_path):
        pass

    def download(self, remote_path, local_path):
        pass

    def runCommand(self):
        pass

