from .baseSupervisorToHPC import BaseSupervisorToHPC
from .summa import SummaKeelingSBatchScript, SummaKeelingJob, \
    SummaCometSBatchScript, SummaCometJob


class SummaSupervisorToHPC(BaseSupervisorToHPC):
    _KeelingSBatchScriptClass = SummaKeelingSBatchScript
    _KeelingJobClass = SummaKeelingJob
    _CometSBatchScriptClass = SummaCometSBatchScript
    _CometJobClass = SummaCometJob

    def __init__(
            self,
            parameters,
            username="cigi-gisolve",
            private_key_path="/opt/cybergis/.gisolve.key",
            user_pw=None,
    ):

        super().__init__(parameters,
                         username=username,
                         private_key_path=private_key_path,
                         user_pw=user_pw, )
        try:
            self.file_manager_rel_path = parameters["file_manager_rel_path"]
        except:
            pass

    def submit(self, **kargs):
        return super().submit(file_manager_rel_path=self.file_manager_rel_path)
