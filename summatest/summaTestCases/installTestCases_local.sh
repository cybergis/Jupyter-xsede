#!/bin/bash

# install the test cases that can be run with the ./runTestCases.sh
# the script creates the necessary output directories and sets the
# paths in the model input files.

# check whether the settings, output and/or testCases_data directories already
# exist to prevent overwriting directories in which a user may have made changes
if [ -d settings -o -d output -o -d testCases_data ]
    then
        echo 'settings, output and/or testCases_data directories already exist.'
        echo 'Please remove or move the settings, output and testCases_data'
        echo 'directories to prevent overwriting'
        exit 1
fi

# create the paths for the output files
mkdir -p output/syntheticTestCases/celia1990
mkdir -p output/syntheticTestCases/colbeck1976
mkdir -p output/syntheticTestCases/miller1998
mkdir -p output/syntheticTestCases/mizoguchi1990
mkdir -p output/syntheticTestCases/wigmosta1999
mkdir -p output/wrrPaperTestCases/figure01
mkdir -p output/wrrPaperTestCases/figure02
mkdir -p output/wrrPaperTestCases/figure03
mkdir -p output/wrrPaperTestCases/figure04
mkdir -p output/wrrPaperTestCases/figure05
mkdir -p output/wrrPaperTestCases/figure06
mkdir -p output/wrrPaperTestCases/figure07
mkdir -p output/wrrPaperTestCases/figure08
mkdir -p output/wrrPaperTestCases/figure09

# modify the paths in the model input file
# we create a new directories to preserve copies of the original files in case
# something goes wrong
BASEDIR=`pwd`
for DIR in settings testCases_data
    do
        cp -rp ${DIR}_org ${DIR}
        for file in `grep -l '<BASEDIR>' -R ${DIR}`
            do
                sed "s|<BASEDIR>|${BASEDIR}|" $file > junk
                mv junk $file
            done
    done
echo "TestCases installed"
