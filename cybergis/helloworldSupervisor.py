from .baseSupervisorToHPC import BaseSupervisorToHPC
from .helloworld import HelloWorldKeelingSBatchScript, HelloWorldKeelingJob, \
                        HelloWorldCometSBatchScript, HelloWorldCometJob


class HelloWorldSupervisorToHPC(BaseSupervisorToHPC):

    jobname = "helloworld"

    _KeelingSBatchScriptClass = HelloWorldKeelingSBatchScript
    _KeelingJobClass = HelloWorldKeelingJob
    _CometSBatchScriptClass = HelloWorldCometSBatchScript
    _CometJobClass = HelloWorldCometJob

