from .baseSupervisorToHPC import BaseSupervisorToHPC
from .summa import SummaKeelingSBatchScript, SummaKeelingJob, \
    SummaCometSBatchScript, SummaCometJob


class SummaSupervisorToHPC(BaseSupervisorToHPC):
    _KeelingSBatchScriptClass = SummaKeelingSBatchScript
    _KeelingJobClass = SummaKeelingJob
    _CometSBatchScriptClass = SummaCometSBatchScript
    _CometJobClass = SummaCometJob
