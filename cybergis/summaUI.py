import os
import time

import ipywidgets as widgets
from IPython.display import display
from tkinter import Tk, filedialog
import traitlets
import json

from .base import *
from .connection import *
from .keeling import *
from .summa import *
from .utils import *
from .job import *
from .utils import get_logger

logger = get_logger()


def Labeled(label, widget):
    width = '130px'
    return (
        widgets.Box([widgets.HTML(value='<p align="right" style="width:%s">%s&nbsp&nbsp</p>' % (width, label)), widget],
                    layout=widgets.Layout(display='flex', align_items='center', flex_flow='row')))


def Title():
    return (widgets.Box([widgets.HTML(value='<h1>Submit Summa Model to HPC</h1>')],
                        layout=widgets.Layout(display='flex', align_items='center', flex_flow='row')
                        ))


def Titleprint():
    return (widgets.Box([widgets.HTML(value='<h1>Print a number</h1>')],
                        layout=widgets.Layout(display='flex', align_items='center', flex_flow='row')
                        ))


class SelectFilesButton(widgets.Button):

    def __init__(self):
        super(SelectFilesButton, self).__init__()
        self.add_traits(files=traitlets.traitlets.List())
        self.description = "Select Files"
        self.icon = "square-o"
        self.style.button_color = "orange"
        self.on_click(self.select_files)

    @staticmethod
    def select_files(b):
        root = Tk()
        root.withdraw()
        root.call('wm', 'attributes', '.', '-topmost', True)
        b.value = filedialog.askopenfilename(multiple=False)
        root.update()

        b.description = "Files Selected"
        b.icon = "check-square-o"
        b.style.button_color = "lightgreen"


class SelectFolderButton(widgets.Button):
    def __init__(self):
        super(SelectFolderButton, self).__init__()
        self.add_traits(files=traitlets.traitlets.List())
        self.description = "Select Folder"
        self.icon = "square-o"
        self.style.button_color = "orange"
        self.on_click(self.select_files)

    @staticmethod
    def select_files(b):
        root = Tk()
        root.withdraw()
        root.call('wm', 'attributes', '.', '-topmost', True)
        b.value = filedialog.askdirectory()
        root.update()

        b.description = "Folder Selected"
        b.icon = "check-square-o"
        b.style.button_color = "lightgreen"


class summa_base():
    username = ""
    machine = "keeling"
    model_source_folder_path = ""  ## the path to the summa testcase folder
    file_manager_path = ""  ## the path to the filemanager folder
    jobname = "summa"  ## the name of the job
    wt = 10
    node = 1
    keeling_con = None
    workspace_path = None
    localID = None
    filemanager = SelectFilesButton()
    folder = SelectFolderButton()
    job_local_id = None
    job_remote_id = None
    private_key_path = None
    user_pw = None
    model_name = None


## New App    
class printnumber():
    number = ""


class HPCUI(summa_base, printnumber):
    def __init__(self, para_json_str,
                 username="cigi-gisolve",
                 private_key_path="/opt/cybergis/.gisolve.key",
                 user_pw=None):

        para_json = json.loads(para_json_str)
        self.username = username
        try:
            self.model_name = para_json['model']
        except:
            pass
        try:
            self.machine = para_json['machine']
        except:
            pass
        try:
            self.file_manager_path = para_json['file_manger_rel_path']
        except:
            pass
        try:
            self.model_source_folder_path = para_json['model_source_folder_path']
        except:
            pass
        try:
            self.workspace_path = para_json['workspace_dir']
        except:
            pass

        self.private_key_path = private_key_path
        self.user_pw = user_pw

    def run(self):
        if (self.model_name.lower() == "summa"):
            if (self.machine == "keeling"):
                if (self.username == "cigi-gisolve"):
                    self.keeling_con = SSHConnection("keeling.earth.illinois.edu",
                                                     user_name="cigi-gisolve",
                                                     key_path=self.private_key_path)
                else:
                    self.keeling_con = SSHConnection("keeling.earth.illinois.edu",
                                                     user_name=self.username,
                                                     user_pw=self.user_pw)
            elif self.machine.lower() == "comet" or self.machine.lower() == "expanse":
                if self.username == "cigi-gisolve":
                    self.keeling_con = SSHConnection("login.expanse.sdsc.edu",
                                                     user_name="cybergis",
                                                     key_path=self.private_key_path)
                else:
                    self.keeling_con = SSHConnection("login.expanse.sdsc.edu",
                                                     user_name=self.username,
                                                     user_pw=self.user_pw)
            # else:
            #    print("Not implemented yet")

            self.__submitUI()

        if (self.model_name.lower() == "print"):
            self.__submitprint()
        # else:
        #    print("Not implemented yet")

    def go(self):

        model_source_folder_path = self.model_source_folder_path
        file_manager_path = self.file_manager_path

        if (self.machine == "keeling"):
            summa_sbatch = SummaKeelingSBatchScript(int(self.wt), self.node, self.jobname)
            sjob = SummaKeelingJob(self.workspace_path, self.keeling_con, summa_sbatch, model_source_folder_path,
                                   file_manager_path, name=self.jobname)
            sjob.go()
            self.job_local_id = sjob.local_id
            self.job_remote_id = sjob.remote_id
            for i in range(600):
                time.sleep(3)
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
            logger.info("Done")
        elif (self.machine.lower() == "comet"):
            summa_sbatch = SummaCometSBatchScript(str(int(self.wt)), self.node, self.jobname)
            sjob = SummaCometJob(self.workspace_path, self.keeling_con, summa_sbatch, model_source_folder_path,
                                 file_manager_path, name=self.jobname)
            sjob.go()
            self.job_local_id = sjob.local_id
            self.job_remote_id = sjob.remote_id
            for i in range(600):
                time.sleep(3)
                status = sjob.job_status()
                if status == "ERROR":
                    logger.error("Job status ERROR")
                    break
                elif status == "UNKNOWN":
                    logger.info("Job completed: {}; {}".format(sjob.local_id, sjob.remote_id))
                    sjob.download()
                    break
                else:
                    logger.info(status)
            logger.info("Done")

    def goprintnumber(self):
        print("The number is " + str(self.number))

    def __submitprint(self):
        number = widgets.IntSlider(
            value=1,
            min=1,
            max=16,
            step=1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='d',
            slider_color='white'
        )
        confirm = widgets.Button(
            description='Submit Job',
            button_style='',  # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Submit job'
        )
        submitForm = widgets.VBox([
            Titleprint(),
            Labeled('print number', number),
            Labeled('', confirm)
        ])
        display(submitForm)

        def submit(b):
            b.disabled = True

            try:
                self.number = number.value
                self.goprintnumber()
            except Exception as ex:
                raise ex
            finally:
                b.disabled = False

        confirm.on_click(submit)

    def __submitUI(self):

        nNodes = widgets.IntSlider(
            value=1,
            min=1,
            max=16,
            step=1,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='d',
            slider_color='white'
        )
        walltime = widgets.FloatSlider(
            value=1,
            min=1.0,
            max=8.0,
            step=1.0,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
            slider_color='white'
        )
        confirm = widgets.Button(
            description='Submit Job',
            button_style='',  # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Submit job'
        )
        submitForm = widgets.VBox([
            Title(),
            Labeled('Walltime (h)', walltime),
            Labeled('Nodes', nNodes),
            # Labeled('Filemanager',self.filemanager),
            # Labeled('Work Folder', self.folder),
            Labeled('', confirm)
        ])
        display(submitForm)

        def submit(b):
            b.disabled = True

            try:
                self.node = nNodes.value
                self.wt = walltime.value

                self.go()
            except Exception as ex:
                raise ex
            finally:
                b.disabled = False

        confirm.on_click(submit)

    def getlocalid(self):
        return self.localID

    def printme(self):
        print("I am doing good")


class summaUI(HPCUI):
    def __init__(self, model_folder_path, filemanager_path, workspace_path,
                 username="cigi-gisolve",
                 machine="keeling",
                 private_key_path="/opt/cybergis/.gisolve.key",
                 user_pw=None):
        self.username = username
        self.machine = machine
        self.file_manager_path = filemanager_path
        self.model_source_folder_path = model_folder_path
        self.workspace_path = workspace_path
        self.private_key_path = private_key_path
        self.user_pw = user_pw
        self.model_name = "summa"

    def runSumma(self):
        self.run()


class HPCSUMMA(HPCUI):
    def __init__(self, para_json_str,
                 username="cigi-gisolve",
                 private_key_path="/opt/cybergis/.gisolve.key",
                 user_pw=None):

        para_json = json.loads(para_json_str)
        self.username = username
        try:
            self.model_name = para_json['model']
        except:
            pass
        try:
            self.machine = para_json['machine']
        except:
            pass
        try:
            self.file_manager_path = para_json['file_manger_rel_path']
        except:
            pass
        try:
            self.model_source_folder_path = para_json['model_source_folder_path']
        except:
            pass
        try:
            self.workspace_path = para_json['workspace_dir']
        except:
            pass
        try:
            self.node = para_json['node']
        except:
            pass
        try:
            self.wt = para_json['walltime']
        except:
            pass

        self.private_key_path = private_key_path
        self.user_pw = user_pw

    def run(self):
        if (self.model_name.lower() == "summa"):
            if (self.machine == "keeling"):
                if (self.username == "cigi-gisolve"):
                    self.keeling_con = SSHConnection("keeling.earth.illinois.edu",
                                                     user_name="cigi-gisolve",
                                                     key_path=self.private_key_path)
                else:
                    self.keeling_con = SSHConnection("keeling.earth.illinois.edu",
                                                     user_name=self.username,
                                                     user_pw=self.user_pw)
            elif self.machine.lower() == "comet" or self.machine.lower() == "expanse":
                if self.username == "cigi-gisolve":
                    self.keeling_con = SSHConnection("login.expanse.sdsc.edu",
                                                     user_name="cybergis",
                                                     key_path=self.private_key_path)
                else:
                    self.keeling_con = SSHConnection("login.expanse.sdsc.edu",
                                                     user_name=self.username,
                                                     user_pw=self.user_pw)

        try:
            self.node = para_json['node']
        except:
            pass
        try:
            self.wt = para_json['walltime']
        except:
            pass
        self.go()
