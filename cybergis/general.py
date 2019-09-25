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
import uuid

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
class UtilsMixin(object):

    def remove_newlines(self, in_str):
        out_str = in_str.replace("\r", "").replace("\n", "")
        return out_str

    def zip_local_folder(self, local_dir, output_dir=None):
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

    def create_local_folder(self, folder_path):

        logger.debug("Creating local folder: {}".format(folder_path))
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def copy_local(self, source, target):
        """
        file --> file
        file --> target/file
        folder --> target/folder
        :param source:
        :param target:
        :return:
        """
        if not os.path.exists(source):
            raise Exception("Source does not exist")
        source_is_folder = os.path.isdir(source)
        target_exists = os.path.exists(target)
        target_is_file = os.path.isfile(target)

        if source_is_folder:
            if target_exists:
                source_folder_name = os.path.basename(source)
                target = os.path.join(target, source_folder_name)
            shutil.copytree(source, target)
        else:  # source is file
            if target_is_file:
                raise Exception("Target file exists")
            shutil.copy(source, target)

        logger.debug("Local copying {} to {}".format(source, target))

    def move_local(self, source, target):
        """
        file --> file
        file --> target/file
        folder --> target/folder
        :param source:
        :param target:
        :return:
        """
        logger.debug("Local moving {} to {}".format(source, target))
        shutil.move(source, target)

class AbstractConnection(object):
    connection_type = str()
    server = str()

    def login(self):
        raise NotImplementedError()

    def logout(self):
        raise NotImplementedError()

    def upload(self, local_fpath, remote_fpath, *args, **kwargs):
        raise NotImplementedError()

    def download(self, remote_fpath, local_fpath, *args, **kwargs):
        raise NotImplementedError()

    def run_command(self, command, *args, **kwargs):
        raise NotImplementedError()


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


class Job(UtilsMixin):
    JOB_ID_PREFIX = "CyberGIS_"
    backend = ""  # keeling or comet
    local_id = ""
    remote_id = ""
    state = ""

    local_workspace_path = ""
    local_job_folder_path = ""
    local_output_folder_name = ""

    remote_workspace_path = ""
    remote_job_folder_name = ""
    remote_output_folder_name = ""

    sbatch_script = None
    user_script = None
    connection = None
    connection_class = AbstractConnection
    sbatch_script_class = SBatchScript
    user_script_class = AbstractScript

    def __init__(self, local_workspace_path, connection,
                 sbatch_script, user_script, local_id=None,
                 name=None, description=None,
                 *args, **kwargs):

        if not os.path.isdir(local_workspace_path):
            raise Exception("Local workspace folder does not exist")

        if local_id is None:
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX)
        self.local_id = local_id

        assert isinstance(connection, self.connection_class)
        assert isinstance(sbatch_script, self.sbatch_script_class)
        assert isinstance(user_script, AbstractScript)
        self.connection = connection
        self.sbatch_script = sbatch_script
        self.user_script = user_script

        self.name = name if name is not None else local_id
        self.description = description

        self._create_local_job_folder()

    def _create_local_job_folder(self):
        local_job_folder_path = os.path.join(self.local_workspace_path,
                                             self.local_id)
        self.create_local_folder(local_job_folder_path)
        self.local_job_folder_path = local_job_folder_path
        return local_job_folder_path

    def random_id(self, digit=10, prefix=str(), suffix=str()):
        id = str(uuid.uuid4()).replace("-", "")
        if digit < 8:
            digit = 8
        elif digit > 32:
            digit = 32
        out = "{pre}{id}{suf}".format(pre=prefix,
                                      id=id[0:digit],
                                      suf=suffix)
        return out

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





class KeelingSBatchScript(SBatchScript):

    KEELING_SBATCH_TEMPLATE = '''
#!/bin/bash
#SBATCH --job-name=$jobname
#SBATCH --nodes=$n_nodes
#SBATCH -t $walltime

$exe'''

    def __init__(self, walltime, node, jobname, exec, *args, **kargs):
        self.walltime = walltime
        self.node = node
        self.jobname = jobname
        self.exec = exec

    def generate_script(self, local_path=None):
        sbscript = Template(self.KEELING_SBATCH_TEMPLATE).substitute(
            jobname=self.jobname,
            n_nodes=self. node,
            walltime=self.walltime,
            exe=self.exec
            )
        logger.debug(sbscript)
        if local_path is None:
            return sbscript
        else:
            local_path=local_path+"/sbatch.sh"
            with open(local_path, 'w') as f:
                f.write(sbscript)
            logger.debug("KeelingSBatchScript saved to {}".format(local_path))


class SummaKeelingSBatchScript(KeelingSBatchScript):

    simg_remote_path = None
    userscript_remote_path = None
    EXEC = "singularity exec $simg $userscript"

    def __init__(self, walltime, node, jobname, userscript_path, *args, **kargs):
        userscript_path=userscript_path+"/run.py"
        _exec = Template(self.EXEC).substitute(simg="/data/keeling/a/zhiyul/images/pysumma_ensemble.img", userscript=userscript_path)
        super().__init__(walltime, node, jobname, _exec, *args, **kargs)


class SummaUserScript(AbstractScript):

    SUMMA_USER_TEMPLATE = '''
import pysumma as ps
import pysumma.hydroshare_utils as utils
from hs_restclient import HydroShare
import shutil, os
import subprocess
from ipyleaflet import Map, GeoJSON
import json

os.chdir("$local_path")
instance = '$instance_name'

file_manager = os.getcwd() + '/' + instance + '/settings/$file_manager_name'
executable = "/code/bin/summa.exe"

S = ps.Simulation(executable, file_manager)


S.run('local', run_suffix='_test')

'''

    local_path = None
    instance_name = None
    file_manager_name = None
    userscript_name = "run.py"

    def __init__(self, local_path, instance_name, file_manager_name, *args, **kargs):
        self.local_path=local_path
        self.instance_name=instance_name
        self.file_manager_name=file_manager_name

    def generate_script(self, local_folder_path=None, *args, **kargs):

        uscript = Template(self.SUMMA_USER_TEMPLATE).substitute(
                local_path=self.local_path,
                instance_name=self.instance_name,
                file_manager_name=self.file_manager_name
                )
        logger.debug(uscript)
        if not os.path.exists(local_folder_path) or not os.path.isdir(local_folder_path):
            return uscript
        else:
            local_path = os.path.join(local_folder_path, self.userscript_name)
            with open(local_path, "w") as f:
                f.write(uscript)
            logging.debug("SummaUserScript saved to {}".format(local_path))



class SSHConnection(UtilsMixin, AbstractConnection):
    connection_type = "ssh"
    _client = None
    _sftp = None
    server = None
    user_name = None
    user_pw = None
    key_path = None
    remote_user_name = None
    remote_user_home = None

    def __init__(self, server, user_name=None, user_pw=None, key_path=None, **kargs):
        self.server = server
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.user_name = user_name
        self.user_pw = user_pw
        self.key_path = key_path

        self.login()
        self.remote_user_home = self.remote_home_directory()
        self.remote_user_name = self.remote_whoami()

        self._sftp = self.client.open_sftp()

    @property
    def client(self):
        return self._client

    @property
    def sftp(self):
        return self._sftp

    def _login_with_password(self, *args, **kwargs):
        self._client.connect(self.server,
                             username=self.user_name,
                             password=self.user_pw)

    def _login_with_key(self, *args, **kwargs):
        self._client.connect(self.server,
                             username=self.user_name,
                             key_filename=self.key_path)

    def login(self, *args, **kwargs):
        if self.key_path is not None:
            self._login_with_key()
        elif self.user_pw is None:
            print("input password for {}".format(self.user_name))
            self.user_pw = getpass()
            self._login_with_password()
        logger.debug("SSH logged into {}".format(self.server))

    def logout(self, *args, **kwargs):
        self._client.close()
        self._sftp.close()
        logger.debug("SSH logged off {}".format(self.server))

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
            zip_fpath = self.zip_local_folder(local_fpath)
            local_fpath = zip_fpath
            unzip = True
        local_fname = os.path.basename(local_fpath)
        if remote_is_folder:
            remote_fpath = os.path.join(remote_fpath, local_fname)
        self._sftp_push(local_fpath, remote_fpath)
        if unzip and remote_fpath.lower().endswith(".zip"):
            self.remote_unzip(remote_fpath, os.path.dirname(remote_fpath))
            self.remote_rm(remote_fpath)
        if cleanup:
            os.remove(local_fpath)
            logger.debug("Removing {}".format(local_fpath))

    def download(self, remote_fpath, local_fpath,
                 remote_is_folder=False, unzip=False, *args, **kwargs):
        cleanup = False
        remote_fpath = remote_fpath.strip()
        local_fpath = local_fpath.strip()
        if remote_is_folder:
            if not os.path.isdir(local_fpath):
                raise Exception("local must be folder when remote is folder")
            unzip = True
            cleanup = True
            remote_folder_name = os.path.basename(remote_fpath)
            remote_zip_fpath = os.path.join("/tmp", remote_folder_name + ".zip")
            # zip folder up on server for download
            self.remote_zip(remote_fpath, remote_zip_fpath)
            remote_fpath = remote_zip_fpath

        remote_fname = os.path.basename(remote_fpath)
        if os.path.isdir(local_fpath):
            local_fpath = os.path.join(local_fpath, remote_fname)
        self._sftp_get(remote_fpath, local_fpath)
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

    def remote_home_directory(self):
        out = self.run_command("echo ~")
        return out

    def remote_whoami(self, *args, **kwargs):
        out = self.run_command("whoami")
        return out

    def remote_pwd(self, *args, **kwargs):
        out = self.run_command("pwd")
        return out

    def remote_ls(self, remote_path="./", line_delimiter=None, **kwargs):
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

    def remote_unzip(self, zip_fpath, output_folder=None):
        if output_folder is None:
            output_folder = self.remote_pwd()
        logger.debug("remote unzipping {} to {}".format(zip_fpath, output_folder))
        self.run_command("unzip -o {} -d {}".format(zip_fpath, output_folder))

    def remote_rm(self, target_path):
        logger.debug("remote rm: {}".format(target_path))
        self.run_command("rm -rf {}".format(target_path))

    def remote_zip(self, target_path, output_fpath):
        logger.debug("remote zip: {} to {}".format(target_path, output_fpath))
        self.run_command("cd {} && zip -r {} {}".format(os.path.dirname(target_path),
                                                        output_fpath,
                                                        os.path.basename(target_path)))

    def _sftp_get(self, remote_fpath, local_fpath):
        logger.debug("sftp getting {} to {}".format(remote_fpath, local_fpath))
        self.sftp.get(remote_fpath, local_fpath)

    def _sftp_push(self, local_fpath, remote_fpath):
        logger.debug("sftp pushing {} to remote @ {}".format(local_fpath, remote_fpath))
        self.sftp.put(local_fpath, remote_fpath)

class KeelingJob(Job):

    JOB_ID_PREFIX = "Keeling_"
    backend = "keeling"
    connection_class = SSHConnection
    sbatch_script_class = KeelingSBatchScript


class SummaKeelingJob(KeelingJob):

    JOB_ID_PREFIX = "Summa_"
    sbatch_script_class = SummaKeelingSBatchScript
    user_script_class = SummaUserScript

    def __init__(self, connection, sbatch_script, user_script, local_id=None, *args, **kwargs):

        if local_id is None:
            local_id = self.random_id(prefix=self.JOB_ID_PREFIX)

        super().__init__(connection, sbatch_script, user_script, local_id=local_id, *args, **kwargs)



if __name__ == "__main__":

    u=UtilsMixin()
    u.copy_local("/Users/zhiyul/Downloads/111abc2", "/tmp")
    u.move_local("/tmp/111abc2", "/tmp/222abc")

    keeling_con = SSHConnection("keeling.earth.illinois.edu",
                            user_name="cigi-gisolve",
                            key_path="/Users/zhiyul/Documents/Projects/summa/Jupyter-xsede/cybergis/keeling.key")
    aa = keeling_con.run_command("cd ~")

    print(keeling_con.remote_ls())
    pass
    sbatch = SummaKeelingSBatchScript(1, 2, "test", "out", "stderr", 'simg_path', "userscript_path")
    uscript = SummaUserScript('settingpath', 'casename')

    sjob = SummaKeelingJob(keeling_con, sbatch, uscript, job_name="123")
    a= 1
    pass
    # sbatch = SummaKeelingSBatchScript(1, 2, "test", "out", "stderr", 'simg_path', "userscript_path")
    # uscript = SummaUserScript('settingpath', 'casename')
    # print(sbatch.generate_script("./abc.sh"))
    #
    # zip = keeling.upload("/Users/zhiyul/Downloads/111abc2", "/tmp", remote_is_folder=True)
    # keeling.remote_ls(remote_path="/tmp")
    #
    # keeling.download("/tmp/111abc2", "/tmp/test", remote_is_folder=True)



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
