#!/bin/bash
HOME_DIR=$PWD
set -o allexport
 RUNNTIME=$1
set +o allexport

module load singularity
if [  -d ${HOME_DIR}/summaTestCases/settings ]
	then
		rm -rf ${HOME_DIR}/summaTestCases/settings
fi 
	mkdir ${HOME_DIR}/summaTestCases/settings

# Pull SUMMA-docker as singuarity image
if [ ! -f ${HOME_DIR}/summa.simg ]
    then
        #echo "summa.simg is not exist in current directory, start download..."
        #singularity pull docker://bartnijssen/summa summa.img
        echo "summa.simg is not exist in current directory, copying..."
        cp /data/keeling/a/zhiyul/images/summa.simg ${HOME_DIR}/summa.simg
fi

# Install SUMMA test cases
#if [ ! -d ${HOME_DIR}/summaTestCases ]
#    then
#        echo "summa test case is not in current directory, start dowload..."
#		if [ ! -f ${HOME_DIR}/summatestcases-2.x.tar.gz ]
#			then
#       			wget ${TEST_URL}
#		fi
#        		tar -zxvf ${HOME_DIR}/summatestcases-2.x.tar.gz
#fi

# Configure environment variables and pathes
cd ${HOME_DIR}/summaTestCases

for i in `seq 1 $RUNNTIME`
do
OUTPUT_PATH=${HOME_DIR}/summaTestCases/output/output$i/
BASESETTING=${HOME_DIR}/summaTestCases/settings/settings$i
TESTDATA=${HOME_DIR}/summaTestCases/testCases_data
BASEOUTPUT=${HOME_DIR}/summaTestCases/output/output$i

TEST_URL="https://ral.ucar.edu/sites/default/files/public/projects/structure-for-unifying-multiple-modeling-alternatives-summa/summatestcases-2.x.tar.gz"

if [ -d ${OUTPUT_PATH} ]
    then
        rm -rf ${OUTPUT_PATH}
fi

# create the paths for the output files
#mkdir -p ${OUTPUT_PATH}/syntheticTestCases/celia1990
#mkdir -p ${OUTPUT_PATH}/syntheticTestCases/colbeck1976
#mkdir -p ${OUTPUT_PATH}/syntheticTestCases/miller1998
#mkdir -p ${OUTPUT_PATH}/syntheticTestCases/mizoguchi1990
#mkdir -p ${OUTPUT_PATH}/syntheticTestCases/wigmosta1999
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure01
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure02
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure03
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure04
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure05
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure06
mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure07
mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure08
#mkdir -p ${OUTPUT_PATH}/wrrPaperTestCases/figure09

chmod -R 777 ${OUTPUT_PATH}

if [ ! -d ${TESTDATA} ]
	then 
		BASEDIR=`pwd`
        DIR=testCases_data
        cp -rp ${DIR}_org ${DIR}
        for file in `grep -l '<BASEDIR>' -R ${DIR}`
        	do
            	sed "s|<BASEDIR>|${BASEDIR}|" $file > junk
                mv junk $file
            done
fi
if [ ! -d ${BASESETTING} ]
	then
		echo 'install...'
        BASEDIR=`pwd`
        DIR=settings/settings$i
        cp -rp settings_org ${DIR}
        for file in `grep -l '<BASEDIR>' -R ${DIR}`
        	do  
            	sed "s|<BASEDIR>|${BASEDIR}|; s|<BASESETTING>|${BASESETTING}|; s|<BASEOUTPUT>|${BASEOUTPUT}|" $file > junk
                mv junk $file
            done
        echo "TestCases $i installed"
fi
done

# Submit the configured job script to HPC
#qsub ${HOME_DIR}/run.qsub
