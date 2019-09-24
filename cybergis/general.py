from __future__ import print_function
import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")
from getpass import getpass
import os
import paramiko
from string import Template
from sys import exit
import logging
import shutil
import tempfile
import zipfile

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")
streamHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

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
    jobname = ""
    stdout = None  # Path to output
    stderr = None  # Path to err
    exec = ""


class KeelingSBatchScript(SBatchScript):

    KEELING_SBATCH_TEMPLATE = '''
#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime
#SBATCH --output=$stdout
#SBATCH -e $stderr

$exe'''

    def __init__(self, walltime, node, jobname, stdout, stderr, exec, *args, **kargs):
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
            logger.debug("KeelingSBatchScript saved to {}".format(local_path))


class SummaKeelingSBatchScript(KeelingSBatchScript):

    simg_remote_path = None
    userscript_remote_path = None
    EXEC = "singularity exec $simg $userscript"

    def __init__(self, walltime, node, jobname, stdout, stderr, simg_path, userscript_path, *args, **kargs):
        _exec = Template(self.EXEC).substitute(simg=simg_path, userscript=userscript_path)
        super().__init__(walltime, node, jobname, stdout, stderr, _exec, *args, **kargs)


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

    def __init__(self, settingpath, casename, *args, **kargs):
        self.settingpath = settingpath
        self.casename = casename

    def generate_script(self, local_folder_path, *args, **kargs):

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

    def remove_newlines(self, in_str):
        out_str = in_str.replace("\r", "").replace("\n", "")
        return out_str

    def zip_folder(self, local_dir, output_dir=None):
        """
        Zip up a local folder /A/B/C, output zip filename: C.zip
        :param local_dir: Path to a local folder: /A/B/C
        :param output_dir: where to put C.zip in; default(None): put C.zip in a random temp folder
        :return: full path to output zip file C.zip
        """
        if not os.path.isdir(local_dir):
            raise Exception("Not a folder: {}".format(local_dir))
        folder_name = os.path.basename(local_dir)
        parent_path = os.path.dirname(local_dir)
        if output_dir is None:
            output_fprefix = os.path.join(tempfile.mkdtemp(), folder_name)
        else:
            output_fprefix = os.path.join(output_dir, folder_name)
        shutil.make_archive(output_fprefix, "zip", parent_path, folder_name)
        zip_fpath = output_fprefix + ".zip"
        logger.debug("Zipping folder {} to {}".format(local_dir, zip_fpath))
        return zip_fpath


class SSHConnection(UtilsMixin):
    _client = None
    _sftp = None
    server_url = None
    user_name = None
    user_pw = None
    key_path = None
    remote_user_name = None
    remote_login_path = None

    def __init__(self, server_url, user_name=None, user_pw=None, key_path=None, **kargs):
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

    def _login_with_password(self, *args, **kwargs):
        self._client.connect(self.server_url,
                             username=self.user_name,
                             password=self.user_pw)

    def _login_with_key(self, *args, **kwargs):
        self._client.connect(self.server_url,
                             username=self.user_name,
                             key_filename=self.key_path)

    def _login(self, *args, **kwargs):
        if self.key_path is not None:
            self._login_with_key()
        elif self.user_pw is None:
            print("input password for {}".format(self.user_name))
            self.user_pw = getpass()
            self._login_with_password()
        logger.debug("SSH logged into {}".format(self.server_url))

    def logout(self, *args, **kwargs):
        self._client.close()
        self._sftp.close()
        logger.debug("SSH logged off {}".format(self.server_url))

    def upload(self, local_fpath, remote_fpath,
               remote_is_folder=False, unzip=False, *args, **kwargs):
        """
        Upload a file or a folder to remote
        local file --> remote file
        local file --> remote folder
        local folder --> remote folder (zip and unzip)
        :param local_fpath: full path to local file or folder
        :param remote_fpath: full path to remote file or folder
        :param remote_is_folder: whether remote_is_folder is a folder path
        :param unzip: whether to unzip on remote
        :param args:
        :param kwargs:
        :return:
        """
        local_fpath = local_fpath.strip()
        remote_fpath = remote_fpath.strip()
        cleanup = False
        if os.path.isdir(local_fpath):
            cleanup = True
            if not remote_is_folder:
                raise Exception("if remote must be a folder when local is folder")
            zip_fpath = self.zip_folder(local_fpath)
            local_fpath = zip_fpath
            unzip = True
        local_fname = os.path.basename(local_fpath)
        if remote_is_folder:
            remote_fpath = os.path.join(remote_fpath, local_fname)
        logger.debug("Uploading {} to remote @ {}".format(local_fname,remote_fpath))
        self.sftp.put(local_fpath, remote_fpath)
        if unzip and remote_fpath.lower().endswith(".zip"):
            self.run_command("unzip -o {} -d {}  && rm -f {}".format(remote_fpath,
                                                                     os.path.dirname(remote_fpath),
                                                                    remote_fpath))
        if cleanup:
            os.remove(local_fpath)
            logger.debug("Removing {}".format(local_fpath))

    def download(self, remote_fpath, local_fpath,
                 remote_is_folder=False, unzip=False, *args, **kwargs):
        cleanup = False
        remote_fpath = remote_fpath.strip()
        local_fpath = local_fpath.strip()
        if remote_is_folder:
            if os.path.isfile(local_fpath):
                raise Exception("local must be folder when remote is folder")
            unzip = True
            cleanup = True
            remote_folder_name = os.path.basename(remote_fpath)
            remote_folder_parent_path = os.path.dirname(remote_fpath)
            remote_zip_fpath = os.path.join("/tmp", remote_folder_name + ".zip")
            # zip folder up on server for download
            self.run_command("cd {} && zip -r {} {}".format(remote_folder_parent_path,
                                                            remote_zip_fpath,
                                                            remote_folder_name))
            remote_fpath = remote_zip_fpath

        remote_fname = os.path.basename(remote_fpath)
        if os.path.isdir(local_fpath):
            local_fpath = os.path.join(local_fpath, remote_fname)
        self.sftp.get(remote_fpath, local_fpath)
        if cleanup:
            self.run_command("rm -f {}".format(remote_fpath))

        if unzip and local_fpath.lower().endswith(".zip"):
            with zipfile.ZipFile(local_fpath, 'r') as zip_ref:
                zip_ref.extractall(os.path.dirname(local_fpath))
            if cleanup:
                os.remove(local_fpath)

    def run_command(self, command, line_delimiter='', *args, **kwargs):
        logger.debug("run_commnad on remote: " + command)
        try:
            stdin, stdout, stderr = self._client.exec_command(command)
        except Exception as e:
            logger.warning("Got error running command " + command + " : " + str(e))
            raise e
        out = list(map(self.remove_newlines, stdout.readlines()))
        err = list(map(self.remove_newlines, stderr.readlines()))
        logger.debug("out: " + str(out))
        logger.debug("err: " + str(err))
        if len(err) > 0:
            logger.warning("run_command {} got error {}".format(command, ';'.join(err)))
        if len(out) == 0:
            return None
        if type(line_delimiter) is not str:
            return out
        return line_delimiter.join(out)

    def get_login_path(self, *args, **kwargs):
        self.remote_login_path = self.pwd()
        return self.remote_login_path

    def get_login_uname(self, *args, **kwargs):
        out = self.whoami()
        self.remote_user_name = out
        return self.remote_user_name

    def whoami(self, *args, **kwargs):
        out = self.run_command("whoami")
        return out

    def pwd(self, *args, **kwargs):
        out = self.run_command("pwd")
        return out

    def ls(self, remote_path="./", line_delimiter=None, **kwargs):
        """
        run 'ls'
        :param remote_path: ls XXX, default(./)
        :param line_delimiter: default(None): return a list;
        :param kwargs:
        :return:
        """
        out = self.run_command("ls {}".format(remote_path if remote_path is not None else "./"),
                               line_delimiter=line_delimiter)
        return out


if __name__ == "__main__":

    keeling = SSHConnection("keeling.earth.illinois.edu",
                            user_name="cigi-gisolve",
                            key_path="/Users/zhiyul/Documents/Projects/summa/Jupyter-xsede/cybergis/keeling.key")
    aa = keeling.run_command("cd ~")

    print(keeling.ls())
    pass

    sbatch = SummaKeelingSBatchScript(1, 2, "test", "out", "stderr", 'simg_path', "userscript_path")
    uscript = SummaUserScript('settingpath', 'casename')
    print(sbatch.generate_script("./abc.sh"))

    zip = keeling.upload("/Users/zhiyul/Downloads/111abc2", "/tmp", remote_is_folder=True)
    keeling.ls(remote_path="/tmp")

    keeling.download("/tmp/111abc2", "/tmp/test", remote_is_folder=True)




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
