import os
import datetime
from string import Template
import math

from .base import SBatchScript
from .job import SlurmJob
from .utils import get_logger

logger = get_logger()


class CometSBatchScript(SBatchScript):

    # change to point to Expanse on 07/15/2021

    def __init__(self, walltime, ntasks, *args, **kargs):
        super().__init__(walltime, ntasks, *args, **kargs)
        # # Lustre Comet scratch filesystem: /oasis/scratch/comet/$USER/temp_project
        # # see: https://www.sdsc.edu/support/user_guides/comet.html
        # self.remote_workspace_folder_path = "/oasis/scratch/comet/cybergis/temp_project"

        # expanse: https://www.sdsc.edu/support/user_guides/expanse.html
        self.remote_workspace_folder_path = "/expanse/lustre/scratch/cybergis/temp_project"
        if self.partition is None:
            self.partition = "shared"  # compute, shared
        # Expanse has 128 cpu/node
        if self.ntasks < 1:
            self.ntasks = 1
        if self.ntasks > 128 * 2:
            self.ntasks = 128 * 2
        if self.ntasks < 128:
            self.partition = "shared"
        else:
            nodesN = math.ceil(self.ntasks/128)
            self.nodes = nodesN
            self.ntasks = nodesN * 128
            self.partition = "compute"


class CometJob(SlurmJob):

    def post_submission(self):
        gateway_username = os.getenv('JUPYTERHUB_USER')
        if gateway_username is None:
            gateway_username = "anonymous_user"

        # report gateway_user metric to XSEDE
        xsede_key_path = os.getenv('XSEDE_KEY_PATH', "")
        if len(str(xsede_key_path)) == 0:
            return

        cmd_template = 'curl -XPOST --data @$xsede_key_path  \
    --data-urlencode "gatewayuser=$gatewayuser"  \
    --data-urlencode "xsederesourcename=comet.sdsc.xsede"  \
    --data-urlencode "jobid=$jobid"  \
    --data-urlencode "submittime=$submittime" \
    https://xsede-xdcdb-api.xsede.org/gateway/v2/job_attributes'

        parameter_kw = {"xsede_key_path": xsede_key_path,
                        "gatewayuser": gateway_username,
                        "jobid": self.remote_id,
                        "submittime": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

        cmd = Template(cmd_template).substitute(parameter_kw)
        logger.debug(cmd)
        logger.info("Metric sent to XSEDE: {gatewayuser}, {jobid}".format(gatewayuser=gateway_username,
                                                                          jobid=self.remote_id))
        out = self.connection.run_command(cmd)
