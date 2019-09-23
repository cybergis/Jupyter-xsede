from __future__ import print_function
import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")
from getpass import getpass
import os
import paramiko
from string import Template
from sys import exit
import logging

logger = logging.getLogger(__name__)

# class JobManager(object):
#     # threading to manage multiple jobs
#     pass
#


class Job(object):
    backend = ""  # keeling or comet
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

    def submit(self):
        # submit job to HPC scheduler
        self.ssh_connection.runCommand(self.sbatch_script)
        self.remote_id = ""

    def download(self):
        # download job from HPC to local
        self.ssh_connection.download(self.remote_output_path, self.local_output_path)


class SummaJob(Job):


    pass


class AbstractScript(object):
    def generate_script(self, *args, **kargs):
        raise NotImplementedError()


class SBatchScript(AbstractScript):
    walltime = int(100)
    node = int(1)
    jobname = None
    stdout = None ## Path to output 
    stderr = None ## Path to


class KeelingSBatchScript(SBatchScript):

    KEELING_SBATCH_TEMPLATE = '''
#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime
#SBATCH --output=$stdout
#SBATCH -e $stderr

$exe'''

    def __init__(self, walltime, node, jobname, stdout, stderr, exec=None):
        self.walltime = walltime
        self.node = node
        self.jobname = jobname
        self.stdout = stdout
        self.stderr = stderr
        self.exec = exec

    def generate_script(self, local_path=None):
        sbscript = Template(self.KEELING_SBATCH_TEMPLATE).substitute(
            jobname=self.jobname,
            n_nodes=self. node,
            walltime=self.walltime,
            stdout=self.stdout,
            stderr=self.stderr,
            exe=self.exec
            )
        logger.debug(sbscript)
        if local_path is None:
            return sbscript
        else:
            with open(local_path, 'w') as f:
                f.write(sbscript)
            logging.debug("KeelingSBatchScript saved to {}".format(local_path))


class SummaKeelingSBatchScript(KeelingSBatchScript):

    simg_remote_path = None
    userscript_remote_path = None
    EXEC = "singularity exec $simg $userscript"

    def __init__(self, walltime, node, jobname, stdout, stderr, simg_path, userscript_path):
        _exec = Template(self.EXEC).substitute(simg=simg_path, userscript=userscript_path)
        super().__init__(walltime, node, jobname, stdout, stderr, _exec)


class SummaUserScript(AbstractScript):

    SUMMA_USER_TEMPLATE = '''
#!/bin/bash
SUMMA_EXE=/code/bin/summa.exe
SUMMA_SETTING=$settingpath

if  [ -z ${SUMMA_EXE} ]
    then
        echo "Can not find the SUMMA executable SUMMA_EXE"
        exit 1
fi

${SUMMA_EXE} -p never -s $casename -m ${SUMMA_SETTING}'''

    settingpath = None
    casename = None
    userscript_fname = "runSummaTest.sh"

    def __init__(self, settingpath, casename):
        self.settingpath = settingpath
        self.casename = casename

    def generate_script(self, local_folder_path):

        uscript = self.SUMMA_USER_TEMPLATE.substitute(
                settingpath=self.settingpath,
                casename=self.casename
                )
        logger.debug(uscript)
        if not os.path.exists(local_folder_path) or not os.path.isdir(local_folder_path):
            return uscript
        else:
            local_path = os.path.join(local_folder_path, self.userscript_fname)
            with open(local_path, "w") as f:
                f.write(uscript)
            logging.debug("SummaUserScript saved to {}".format(local_path))


class UtilsMixin(object):

    def remove_new_line(self, in_str):
        out_str = in_str.replace("\r", "").replace("\n", "")
        return out_str


class SSHConnection(UtilsMixin, object):
    _client = None
    _sftp = None
    server_url = None
    user_name = None
    user_pw = None
    key_path = None
    remote_user_name = None
    remote_login_path = None

    def __init__(self, server_url, user_name=None, user_pw=None, key_path=None):
        self.server_url = server_url
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.user_name = user_name
        self.user_pw = user_pw
        self.key_path = key_path

        self._login()
        self.get_login_path()
        self.get_login_uname()
        self._sftp = self.client.open_sftp()

    @property
    def client(self):
        return self._client

    @property
    def sftp(self):
        return self._sftp

    def _login_password(self):
        self._client.connect(self.server_url,
                            username=self.user_name,
                            password=self.user_pw)

    def _login_key(self):
        self._client.connect(self.server_url,
                             username=self.user_name,
                             key_filename=self.key_path)

    def _login(self):

        if self.key_path is not None:
            self._login_key()
        elif self.user_pw is None:
            print("user password")
            self.user_pw = getpass()
            self._login_password()
        print("SSH logged into {}".format(self.server_url))

    def logout(self):
        self._client.close()
        self._sftp.close()
        print("SSH logged off {}".format(self.server_url))

    def upload_file(self, local_fpath, remote_fpath, *args, **kwargs):
        local_fpath, remote_fpath = self.before_upload_file(local_fpath, remote_fpath, *args, **kwargs)
        self.sftp.put(local_fpath, remote_fpath)
        self.after_upload_file(local_fpath, remote_fpath, *args, **kwargs)

    def before_upload_file(self, local_fpath, remote_fpath, *args, **kwargs):
        return (local_fpath.strip(), remote_fpath.strip())

    def after_upload_file(self,local_fpath, remote_fpath, *args, **kwargs):
        pass

    def download_file(self, remote_fpath, local_fpath):
        remote_fpath = remote_fpath.strip()
        local_fpath = local_fpath.strip()
        self.sftp.get(remote_fpath,
                      local_fpath)

    def run_command(self, command):
        try:
            stdin, stdout, stderr = self._client.exec_command(command)
        except Exception as e:
            logger.warning("error when run command " + command + " caused by " + str(e))
            raise e
        out = stdout.readlines()
        err = stderr.readlines()
        if len(err) > 0:
            logger.warning("run_command {} got error {}".format(command, ';'.join(err)))
        return self.remove_new_line(''.join(out))

    def get_login_path(self):
        self.remote_login_path = self.get_pwd()

    def get_login_uname(self):
        out = self.run_command("whoami")
        self.remote_user_name = out

    def get_pwd(self):
        return self.run_command("pwd")






if __name__ == "__main__":


    keeling = SSHConnection("keeling.earth.illinois.edu", user_name="cigi-gisolve", key_path="/Users/zhiyul/Documents/Projects/summa/Jupyter-xsede/cybergis/keeling.key")
    keeling.upload_file(os.path.join(os.path.abspath(__file__)),
                        os.path.join(keeling.remote_login_path, "g.py"))

    print(keeling.remote_user_name, keeling.remote_login_path)
    pass

    # sbatch = SummaKeelingSBatchScript(1, 2, "test", "out", "stderr", 'simg_path', "userscript_path")
    # uscript = SummaUserScript()
    # print(sbatch.generarte_script("./abc.sh"))


class KeelingSSHConnection(object):

    jobDir = None
    host = None

    def login(self):
        if not os.path.exists(self.jobDir):
            os.makedirs(self.jobDir)
        login_success = False
        if (self.host_userName == 'cigi-gisolve'):
            try:
                self.__client.connect(self.host, username=self.host_userName, key_filename='/opt/cybergis/.gisolve.key')
                self.__sftp = self.__client.open_sftp()
            except Exception as e:
                logger.warn("can not connect to server " + self.host + ", caused by " + str(e))
                exit()
            else:
                logger.info('Successfully logged in as %s' % self.host_userName)
                login_success = True
                self.pw = None

        else:
            while not login_success:
                pw = getpass(prompt='Password')
                try:
                    self.__client.connect(self.host, username=self.host_userName, password=pw)
                    self.__sftp = self.__client.open_sftp()
                except Exception as e:
                    logger.warn("can not connect to server " + self.host + ", caused by " + str(e))
                    exit()
                else:
                    logger.info('Successfully logged in as %s' % self.host_userName)
                    login_success = True
                    self.pw = pw
        if 'exists' not in self.__runCommand("if [ -d " + HPC_PRJ + " ]; then echo 'exists'; fi"):
            self.__runCommand("mkdir " + HPC_PRJ)

        moduleList = self.__runCommand("module avail 2>&1 | grep -v '/sw' | tr ' ' '\n' | sed '/^$/d' | sort")

        self.module_avail = {_: _ for _ in moduleList.replace('(default)', '').split() if _.count('-') < 3}
        self.m = self.module_avail
        self.modules = set()
