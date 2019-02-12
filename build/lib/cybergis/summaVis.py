import logging
import atexit
import time
import matplotlib
import matplotlib.pyplot as plt
import xarray as xr


# logger config
logger_format = '%(asctime)-15s %(message)s'
logging.basicConfig(format=logger_format)
logger = logging.getLogger('summaVis')
logger.setLevel(logging.DEBUG)


# class to visualize summa output
# support chart: 
# 	line
class summaVis:

    def __init__(self, filepath):
        self.filepath = filepath
	self.ds = xr.open_dataset(filepath)

# read NetCDF file 
# parameter input 
# 	filepath: String, NetCDF file path 

    def __readData(self, filepath):
        self.ds = xr.open_dataset(filepath)

# line chart
# parameter:
#	attr: String, the arrtibute to draw

    def attrPlot(self, attr):
        ax = self.ds[attr].plot()
	plt.show()
	return ax 
