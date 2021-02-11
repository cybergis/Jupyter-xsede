from .baseSupervisorToHPC import BaseSupervisorToHPC
from .rhessys import RHESSysKeelingSBatchScript, RHESSysKeelingJob, \
    RHESSysCometSBatchScript, RHESSysCometJob


class RHESSysSupervisorToHPC(BaseSupervisorToHPC):
    _KeelingSBatchScriptClass = RHESSysKeelingSBatchScript
    _KeelingJobClass = RHESSysKeelingJob
    _CometSBatchScriptClass = RHESSysCometSBatchScript
    _CometJobClass = RHESSysCometJob