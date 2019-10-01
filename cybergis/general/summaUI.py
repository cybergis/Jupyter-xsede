import logging
import os
from .base import *
from .connection import *
from .keeling import *
from .summa import *
from .utils import *
from .job import *
from .summaUI import *
import time
from ipywidgets import *
from IPython.display import display
#from tkinter import Tk, filedialog
#import traitlets

logger = logging.getLogger("cybergis")

def Labeled(label, widget):
    width='130px'
    return (Box([HTML(value='<p align="right" style="width:%s">%s&nbsp&nbsp</p>'%(width,label)),widget],
                layout=Layout(display='flex',align_items='center',flex_flow='row')))


def Title():
    return (Box([HTML(value='<h1>Welcome to Summa General Case</h1>')],
        layout=Layout(display='flex',align_items='center',flex_flow='row')
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

class summaUI():
    username = ""
    machine = ""
    model_source_folder_path = "" ## the path to the summa testcase folder
    file_manager_path = "" ## the path to the filemanager folder
    jobname = "test" ## the name of the job
    walltime = 10
    node = 1
    keeling_con = None
    workspace_path = None
    nNodes=IntSlider(
        value=5,
        min=1,
        max=10,
        step=1,
        continuous_update=False,
        orientation='horizontal',
        readout=True,
        readout_format='d',
        slider_color='white'
    )
    walltime=FloatSlider(
        value=10,
        min=1.0,
        max=48.0,
        step=1.0,
        continuous_update=False,
        orientation='horizontal',
        readout=True,
        readout_format='.1f',
        slider_color='white'
    )
    confirm=Button(
        description='Submit Job',
        button_style='', # 'success', 'info', 'warning', 'danger' or ''
        tooltip='Submit job'
    )
    filemanager=SelectFilesButton()
    folder = SelectFolderButton()


    def __init__(self, model_folder_path, filemanager_path, workspace_path, username="cigi-gisolve", machine="keeling"):
        self.username=username
        self.machine="keeling"
        self.file_manager_path = filemanager_path
        self.model_source_folder_path = model_folder_path
        self.workspace_path = workspace_path

    def submit(self, b):
        self.node = self.nNodes.value
        self.walltime = self.walltime.value
        self.file_manager_path=self.filemanager.value
        self.model_source_folder_path=self.folder.value

        model_source_folder_path = self.model_source_folder_path
        file_manager_path = self.file_manager_path

        summa_sbatch = SummaKeelingSBatchScript(self.walltime, self.node, self.jobname)


        sjob = SummaKeelingJob(self.workspace_path, self.keeling_con, summa_sbatch, model_source_folder_path, file_manager_path, name=self.jobname)
        sjob.go()
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
        logger.info("Done")

    def runSumma(self):
        if (self.machine=="keeling"):
            if (self.username == "cigi-gisolve"):
                self.keeling_con = SSHConnection("keeling.earth.illinois.edu",
                            user_name="cigi-gisolve",
                            key_path="/opt/cybergis/.gisolve.key")
            else:
                self.keeling_con = SSHConnection("keeling.earth.illinois.edu",
                            user_name=self.username)
                self.keeling_con.login()
        else:
            print ("Not implemented yet")


        self.__submitUI()


    def __submitUI(self):
        submitForm=VBox([
            Title(),
            Labeled('Walltime (h)', self.walltime),
            Labeled('Nodes', self.nNodes),
            #Labeled('Filemanager',self.filemanager),
            #Labeled('Work Folder', self.folder),
            Labeled('', self.confirm)
        ])
        display(submitForm)
        self.confirm.on_click(self.submit)



