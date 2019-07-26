import logging
import os
import shutil
import paramiko


class SSHComm(object):

    def __init__(self, host_name="localhost", user_name=None, pw=None):

        if (host_name == "comet" or host_name == "Comet"):
            host_name = 'comet.sdsc.xsede.org'
        elif host_name.lower() == 'keeling':
            host_name = 'keeling.earth.illinois.edu'

        self.host = host_name
        self.host_userName = user_name or 'cigi-gisolve'

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.login_success = False
        self.pw = pw
        self.login()

    def login(self):

        if self.host_userName == 'cigi-gisolve':

            self.client.connect(self.host, username=self.host_userName, key_filename='/opt/cybergis/.gisolve.key')
            self.sftp =self.client.open_sftp()
            logging.info('Successfully logged in as %s ' % self.host_userName)
            self.login_success = True
        else:
            self.client.connect(self.host, username=self.host_userName, password=self.pw)
            self.sftp = self.client.open_sftp()
            logging.info('Successfully logged in as %s ' % self.host_userName)
            self.login_success = True
        self.pw = None

    def runCommand(self, command):
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
        except Exception as e:
            logging.warn("error when run command " + command + " caused by " + str(e))
            exit()
        return ''.join(stdout.readlines()) + ''.join(stderr.readlines())

    def runCommandBlock(self, command):
        ans = ""
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            while (not stdout.channel.exit_status_ready()):
                ans += stdout.read(1000).decode('utf-8')
        except Exception as e:
            logging.warn("error when run command " + command + " in blocking model, caused by " + str(e))
            exit()
        return ans

    def downloadFile(self, localFolder, localFilename, remoteFolder, remoteFilename):
        print(localFolder, localFilename, remoteFolder, remoteFilename)
        if not os.path.exists(localFolder):
            os.makedirs(localFolder)
        self.sftp.get(os.path.join(remoteFolder, remoteFilename), os.path.join(localFolder, localFilename))
            #self.sftp.get(remotePath, os.path.join(localPath, filename))

    def downloadFolder(self, localPath, remotePath):
        '''
        Recursive download folder content
        :param localPath:
        :param remotePath:
        :return:
        '''
        fs = self.runCommandBlock("ls " + remotePath)
        print(localPath)
        print(remotePath)

        for f in fs.split('\n'):
            f.strip('\n')
            if not f:
                continue
            nextRemotePath = os.path.join(remotePath, f)
            nextLocalPath = os.path.join(localPath, f)
            if 'file!' in self.runCommandBlock("if [ -f " + nextRemotePath + " ]; then echo 'file!'; fi"):
                self.downloadFile(localPath, f, remotePath, f)
            else:
                # if os.path.exists(nextLocalPath):
                #     shutil.rmtree(nextLocalPath)
                # os.makedirs(nextLocalPath)
                self.downloadFolder(nextLocalPath, nextRemotePath)
