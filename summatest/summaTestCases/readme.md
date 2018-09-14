# SUMMA Test Cases

This tar archive contains a series of test cases for SUMMA for SUMMA 2.0.

There are two sets of test cases:
  1) Test cases based on synthetic/lab data; and
  2) Test cases based on field data.

To run the test cases you first will need to install
[SUMMA](https://github.com/UCAR/summa) or alternatively you can use a
dockerized version of the code. Further details are provided below.


## Contents
 * readme.md: this file
 * installTestCases_local.sh: bash script to install the test cases if you use
   a locally compiled version of SUMMA.
 * installTestCases_docker.sh: bash script to install the test cases if you use
   a dockerized version of SUMMA.
 * runTestCases_local.sh: bash script to run through all the test cases if you
   use a locally compiled version of SUMMA.
 * runTestCases_docker.sh: bash script to run through all the test cases if you
   use a dockerized version of SUMMA.
 * settings_org/ : directory with settings files for test cases
 * testCases_data_org/ : directory with input data for test cases

## Installation

 * If you plan to use a locally compiled version of SUMMA:
   * Install SUMMA. This is described in the readme files that are part of the
     summa distribution. Note the location of the SUMMA executable
     (`SUMMA_EXE`).
   * In the top directory of this tar archive, run
     `./installTestCases_local.sh` or `/bin/bash installTestCases_local.sh`.
     This will create three new directories (`output`, `settings`,
     `testCases_data`) with the correct path names. The original input files in
     `settings_org` and `testCases_data_org` remain untouched so you can recover
     if something goes wrong.
   * Edit `runTestCases_local.sh` to set the `SUMMA_EXE` variable in that file.

 * If you plan to use the dockerized version of SUMMA:
   * Install docker. See https://www.docker.com/.
   * In the top directory of this tar archive, run
     `./installTestCases_docker.sh` or `/bin/bash installTestCases_docker.sh`.
     This will create three new directories (`output`, `settings`,
     `testCases_data`) with the correct path names. The original input files in
     `settings_org` and `testCases_data_org` remain untouched so you can recover
     if something goes wrong.
   * Edit `runTestCases_docker.sh` to set the `DOCKER_TEST_CASES_PATH` and the
     `SUMMA_EXE` variable in that file. The first variable should be the full
     path to the parent directory of `summaTestCases_2.x`. The second variable
     is the docker image you want to run, e.g. `bartnijssen/summa:latest`, which
     will run the latest version of the SUMMA master branch (generally this is
     what you'd want to run) or `bartnijssen/summa:develop` although that
     version may not be fully compatible with this test data set.

## Running and comparing the test cases

 * After installing the test cases, you can run them from the top directory of
   the tar archive as `./runTestCases_local.sh` or
   `/bin/bash runTestCases_local.sh` if you use the locally installed version
   of SUMMA or `./runTestCases_docker.sh` or `/bin/bash runTestCases_docker.sh`
   if you use the dockerized version of SUMMA. Note that this may run for quite
   a while (hour) depending on the speed of your machine.
 * Model output is stored in the `output` directory.

## Test cases

### Test cases based on synthetic or lab data

 * Synthetic test case 1: Simulations from Celia (WRR 1990)
 * Synthetic test case 2: Simulations of drainage through snow pack from
                          Clark et al. (WRR 2016) based on Colbeck (1976)
 * Synthetic test case 3: Simulations from Miller (WRR 1998)
 * Synthetic test case 4: Simulations of the lab experiment of Mizoguchi (1990)
                          as described by Hansson et al. (VZJ 2005)
 * Synthetic test case 5: Simulations of rain on a sloping hillslope from
                          Wigmosta (WRR 1999)

### Test cases based on field data, as described by Clark et al. (WRR 2015b)

 * Figure 1: Radiation transmission through an Aspen stand,
             Reynolds Mountain East
 * Figure 2: Wind attenuation through an Aspen stand, Reynolds Mountain East
 * Figure 3: Impacts of canopy wind profile on surface fluxes, surface
             temperature, and snow melt (Aspen stand,Reynolds Mountain East)
 * Figure 4: Form of different interception capacity parameterizations
             (no model simulations conducted/needed)
 * Figure 5: Snow interception at Umpqua
 * Figure 6: Sensitivity to snow albedo representations at Reynolds Mountain
             East and Senator Beck
 * Figure 7: Sensitivity of ET to the stomatal resistance parameterization
             (Aspen stand at Reynolds Mountain East)
 * Figure 8: Sensitivity of ET to the root distribution and the baseflow
             parameterization (Aspen stand at Reynolds Mountain East)
             (NOTE: baseflow simulations conducted as part of Figure 9)
 * Figure 9: Simulations of runoff using different baseflow parameterizations
             (Reynolds Mountain East)
