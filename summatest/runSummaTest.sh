#!/bin/bash
SUMMA_EXE=/code/bin/summa.exe
SUMMA_SETTING=summaTestCases/settings/settings$1

if  [ -z ${SUMMA_EXE} ]
    then
        echo "Can not find the SUMMA executable SUMMA_EXE"
        exit 1
fi

# *************************************************************************************************
# * PART 1: TEST CASES BASED ON SYNTHETIC OR LAB DATA

# Synthetic test case 1: Simulations from Celia (WRR 1990)
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/celia1990/summa_fileManager_celia1990.txt


#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/celia1990/summa_fileManager_celia1990.txt

# Synthetic test case 2: Simulations of drainage through snow pack from Clark et al. (WRR 2016) based on Colbeck (1976)
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/colbeck1976/summa_fileManager_colbeck1976-exp1.txt
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/colbeck1976/summa_fileManager_colbeck1976-exp2.txt
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/colbeck1976/summa_fileManager_colbeck1976-exp3.txt

# Synthetic test case 3: Simulations from Miller (WRR 1998)
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/miller1998/summa_fileManager_millerClay.txt
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/miller1998/summa_fileManager_millerLoam.txt
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/miller1998/summa_fileManager_millerSand.txt

# Synthetic test case 4: Simulations of the lab experiment of Mizoguchi (1990)
#                         as described by Hansson et al. (VZJ 2005)
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/mizoguchi1990/summa_fileManager_mizoguchi.txt

# Synthetic test case 5: Simulations of rain on a sloping hillslope from Wigmosta (WRR 1999)
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/wigmosta1999/summa_fileManager-exp1.txt
#${SUMMA_EXE} -p never -s _testSumma -m ${SUMMA_SETTING}/syntheticTestCases/wigmosta1999/summa_fileManager-exp2.txt

# End of test cases based on synthetic/lab data
# *************************************************************************************************
# * PART 2: TEST CASES BASED ON FIELD DATA, AS DESCRIBED BY CLARK ET AL. (WRR 2015B)

# Figure 1: Radiation transmission through an Aspen stand, Reynolds Mountain East
#${SUMMA_EXE} -p never -s _riparianAspenBeersLaw        -m ${SUMMA_SETTING}/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenBeersLaw.txt
#${SUMMA_EXE} -p never -s _riparianAspenNLscatter       -m ${SUMMA_SETTING}/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenNLscatter.txt
#${SUMMA_EXE} -p never -s _riparianAspenUEB2stream      -m ${SUMMA_SETTING}/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenUEB2stream.txt
#${SUMMA_EXE} -p never -s _riparianAspenCLM2stream      -m ${SUMMA_SETTING}/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenCLM2stream.txt
#${SUMMA_EXE} -p never -s _riparianAspenVegParamPerturb -m ${SUMMA_SETTING}/wrrPaperTestCases/figure01/summa_fileManager_riparianAspenVegParamPerturb.txt

# Figure 2: Wind attenuation through an Aspen stand, Reynolds Mountain East
#${SUMMA_EXE} -p never -s _riparianAspenWindParamPerturb -m ${SUMMA_SETTING}/wrrPaperTestCases/figure02/summa_fileManager_riparianAspenWindParamPerturb.txt

# Figure 3: Impacts of canopy wind profile on surface fluxes, surface temperature, and snow melt (Aspen stand, Reynolds Mountain East)
#${SUMMA_EXE} -p never -s _riparianAspenExpWindProfile -m ${SUMMA_SETTING}/wrrPaperTestCases/figure03/summa_fileManager_riparianAspenExpWindProfile.txt

#${SUMMA_EXE} -p never -s _hedpom9697 -m ${SUMMA_SETTING}/wrrPaperTestCases/figure05/summa_fileManager_9697_hedpom.txt
#${SUMMA_EXE} -p never -s _hedpom9798 -m ${SUMMA_SETTING}/wrrPaperTestCases/figure05/summa_fileManager_9798_hedpom.txt
#${SUMMA_EXE} -p never -s _storck9697 -m ${SUMMA_SETTING}/wrrPaperTestCases/figure05/summa_fileManager_9697_storck.txt
#${SUMMA_EXE} -p never -s _storck9798 -m ${SUMMA_SETTING}/wrrPaperTestCases/figure05/summa_fileManager_9798_storck.txt

# Figure 6: Sensitivity to snow albedo representations at Reynolds Mountain East and Senator Beck
#${SUMMA_EXE} -p never -s _reynoldsConstantDecayRate -m ${SUMMA_SETTING}/wrrPaperTestCases/figure06/summa_fileManager_reynoldsConstantDecayRate.txt
#${SUMMA_EXE} -p never -s _reynoldsVariableDecayRate -m ${SUMMA_SETTING}/wrrPaperTestCases/figure06/summa_fileManager_reynoldsVariableDecayRate.txt
#${SUMMA_EXE} -p never -s _senatorConstantDecayRate  -m ${SUMMA_SETTING}/wrrPaperTestCases/figure06/summa_fileManager_senatorConstantDecayRate.txt
#${SUMMA_EXE} -p never -s _senatorVariableDecayRate  -m ${SUMMA_SETTING}/wrrPaperTestCases/figure06/summa_fileManager_senatorVariableDecayRate.txt

# Figure 7: Sensitivity of ET to the stomatal resistance parameterization (Aspen stand at Reynolds Mountain East)
#${SUMMA_EXE} -p never -s _jarvis           -m ${SUMMA_SETTING}/wrrPaperTestCases/figure07/summa_fileManager_riparianAspenJarvis.txt
#${SUMMA_EXE} -p never -s _ballBerry        -m ${SUMMA_SETTING}/wrrPaperTestCases/figure07/summa_fileManager_riparianAspenBallBerry.txt
${SUMMA_EXE} -p never -s _simpleResistance -m ${SUMMA_SETTING}/wrrPaperTestCases/figure07/summa_fileManager_riparianAspenSimpleResistance.txt

# Figure 8: Sensitivity of ET to the root distribution and the baseflow parameterization (Aspen stand at Reynolds Mountain East)
#  (NOTE: baseflow simulations conducted as part of Figure 9)
#${SUMMA_EXE} -p never -s _perturbRoots -m ${SUMMA_SETTING}/wrrPaperTestCases/figure08/summa_fileManager_riparianAspenPerturbRoots.txt

# Figure 9: Simulations of runoff using different baseflow parameterizations (Reynolds Mountain East)
#${SUMMA_EXE} -p never -s _1dRichards          -m ${SUMMA_SETTING}/wrrPaperTestCases/figure09/summa_fileManager_1dRichards.txt
#${SUMMA_EXE} -p never -s _lumpedTopmodel      -m ${SUMMA_SETTING}/wrrPaperTestCases/figure09/summa_fileManager_lumpedTopmodel.txt
#${SUMMA_EXE} -p never -s _distributedTopmodel -m ${SUMMA_SETTING}/wrrPaperTestCases/figure09/summa_fileManager_distributedTopmodel.txt


