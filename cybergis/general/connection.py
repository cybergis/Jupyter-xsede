
from .utils import UtilsMixin
from .base import AbstractConnection
import paramiko
import logging
from getpass import getpass
import os
import zipfile

logger = logging.getLogger("cybergis")


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