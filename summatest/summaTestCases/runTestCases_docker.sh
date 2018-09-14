#!/bin/bash

# Used to run the test cases for SUMMA

# There are two classes of test cases:
#  1) Test cases based on synthetic/lab data; and
#  2) Test cases based on field data.

# The commands assume that you are in the directory {localInstallation}//summaTestCases_2.x/settings/
# and that the control files are in {localInstallation}/settings/

# LOCAL_TEST_CASES_PATH should be set to the full path for the parent directory of the summaTestCases_2.x directory
DOCKER_TEST_CASES_PATH=

# Set the docker image you want to run
SUMMA_EXE=bartnijssen/summa:latest

if  [ -z ${SUMMA_EXE} ]
    then
        echo "Must define the SUMMA executable SUMMA_EXE in $0"
        exit 1
fi

if  [ -z ${DOCKER_TEST_CASES_PATH} ]
    then
        echo "Must define the LOCAL_TEST_CASES_PATH $0"
        exit 1
fi

# *************************************************************************************************
DISK_MAPPING=${DOCKER_TEST_CASES_PATH}/summaTestCases_2.x:/summaTestCases_2.x


# *************************************************************************************************
# * PART 1: TEST CASES BASED ON SYNTHETIC OR LAB DATA

# Synthetic test case 1: Simulations from Celia (WRR 1990)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/celia1990/summa_fileManager_celia1990.txt

# Synthetic test case 2: Simulations of drainage through snow pack from Clark et al. (WRR 2016) based on Colbeck (1976)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/colbeck1976/summa_fileManager_colbeck1976-exp1.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/colbeck1976/summa_fileManager_colbeck1976-exp2.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/colbeck1976/summa_fileManager_colbeck1976-exp3.txt

# Synthetic test case 3: Simulations from Miller (WRR 1998)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/miller1998/summa_fileManager_millerClay.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/miller1998/summa_fileManager_millerLoam.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/miller1998/summa_fileManager_millerSand.txt

# Synthetic test case 4: Simulations of the lab experiment of Mizoguchi (1990)
#                         as described by Hansson et al. (VZJ 2005)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/mizoguchi1990/summa_fileManager_mizoguchi.txt

# Synthetic test case 5: Simulations of rain on a sloping hillslope from Wigmosta (WRR 1999)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/wigmosta1999/summa_fileManager-exp1.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _testSumma_docker -m /summaTestCases_2.x/settings/syntheticTestCases/wigmosta1999/summa_fileManager-exp2.txt

# End of test cases based on synthetic/lab data
# *************************************************************************************************
# * PART 2: TEST CASES BASED ON FIELD DATA, AS DESCRIBED BY CLARK ET AL. (WRR 2015B)

# Figure 1: Radiation transmission through an Aspen stand, Reynolds Mountain East
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenBeersLaw        -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenBeersLaw.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenNLscatter       -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenNLscatter.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenUEB2stream      -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenUEB2stream.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenCLM2stream      -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenCLM2stream.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenVegParamPerturb -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenVegParamPerturb.txt

# Figure 2: Wind attenuation through an Aspen stand, Reynolds Mountain East
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenWindParamPerturb -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure02/summa_fileManager_riparianAspenWindParamPerturb.txt

# Figure 3: Impacts of canopy wind profile on surface fluxes, surface temperature, and snow melt (Aspen stand, Reynolds Mountain East)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _riparianAspenExpWindProfile -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure03/summa_fileManager_riparianAspenExpWindProfile.txt

# Figure 4: Form of different interception capacity parameterizations
# (no model simulations conducted/needed)

# Figure 5: Snow interception at Umpqua
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _hedpom9697 -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure05/summa_fileManager_9697_hedpom.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _hedpom9798 -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure05/summa_fileManager_9798_hedpom.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _storck9697 -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure05/summa_fileManager_9697_storck.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _storck9798 -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure05/summa_fileManager_9798_storck.txt

# Figure 6: Sensitivity to snow albedo representations at Reynolds Mountain East and Senator Beck
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _reynoldsConstantDecayRate -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure06/summa_fileManager_reynoldsConstantDecayRate.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _reynoldsVariableDecayRate -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure06/summa_fileManager_reynoldsVariableDecayRate.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _senatorConstantDecayRate  -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure06/summa_fileManager_senatorConstantDecayRate.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _senatorVariableDecayRate  -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure06/summa_fileManager_senatorVariableDecayRate.txt

# Figure 7: Sensitivity of ET to the stomatal resistance parameterization (Aspen stand at Reynolds Mountain East)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _jarvis           -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure07/summa_fileManager_riparianAspenJarvis.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _ballBerry        -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure07/summa_fileManager_riparianAspenBallBerry.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _simpleResistance -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure07/summa_fileManager_riparianAspenSimpleResistance.txt

# Figure 8: Sensitivity of ET to the root distribution and the baseflow parameterization (Aspen stand at Reynolds Mountain East)
#  (NOTE: baseflow simulations conducted as part of Figure 9)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _perturbRoots -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure08/summa_fileManager_riparianAspenPerturbRoots.txt

# Figure 9: Simulations of runoff using different baseflow parameterizations (Reynolds Mountain East)
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _1dRichards          -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure09/summa_fileManager_1dRichards.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _lumpedTopmodel      -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure09/summa_fileManager_lumpedTopmodel.txt
docker run -v ${DISK_MAPPING} ${SUMMA_EXE} -p never -s _distributedTopmodel -m /summaTestCases_2.x/settings/wrrPaperTestCases/figure09/summa_fileManager_distributedTopmodel.txt

# End of test cases based on field data
# *************************************************************************************************
