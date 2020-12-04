from .baseSupervisorToHPC import BaseSupervisorToHPC
from .wrfhydro import WRFHydroKeelingSBatchScript, WRFHydroKeelingJob, \
    WRFHydroCometSBatchScript, WRFHydroCometJob


class WRFHydroSupervisorToHPC(BaseSupervisorToHPC):
    jobname = "wrfhydro"

    _KeelingSBatchScriptClass = WRFHydroKeelingSBatchScript
    _KeelingJobClass = WRFHydroKeelingJob
    _CometSBatchScriptClass = WRFHydroCometSBatchScript
    _CometJobClass = WRFHydroCometJob
