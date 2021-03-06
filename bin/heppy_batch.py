#!/usr/bin/env python

import sys
import imp
import copy
import os
import shutil
import dill
import pickle
import json
import math
from heppy.utils.batchmanager import BatchManager
from heppy.framework.config import split
from heppy.utils.versions import Versions

import heppy.framework.looper as looper

heppy_option_str = None

def batchScriptPADOVA( index, jobDir='./'):
   '''prepare the LSF version of the batch script, to run on LSF'''
   script = """#!/bin/bash
#BSUB -q local
#BSUB -J test
#BSUB -o test.log
cd {jdir}
echo 'PWD:'
pwd
export VO_CMS_SW_DIR=/cvmfs/cms.cern.ch
source $VO_CMS_SW_DIR/cmsset_default.sh
echo 'environment:'
echo
env > local.env
env
# ulimit -v 3000000 # NO
echo 'copying job dir to worker'
eval `scram runtime -sh`
ls
echo 'running'
python {looper} pycfg.py config.pck --options=options.json >& local.output
exit $? 
#echo
#echo 'sending the job directory back'
#echo cp -r Loop/* $LS_SUBCWD 
""".format(looper=looper.__file__, jdir=jobDir)

   return script

def batchScriptPISA( index, remoteDir=''):
   '''prepare the LSF version of the batch script, to run on LSF'''
   script = """#!/bin/bash
#BSUB -q cms
echo 'PWD:'
pwd
export VO_CMS_SW_DIR=/cvmfs/cms.cern.ch
source $VO_CMS_SW_DIR/cmsset_default.sh
echo 'environment:'
echo
env > local.env
env
# ulimit -v 3000000 # NO
echo 'copying job dir to worker'
###cd $CMSSW_BASE/src
eval `scramv1 runtime -sh`
#eval `scramv1 ru -sh`
# cd $LS_SUBCWD
# eval `scramv1 ru -sh`
##cd -
##cp -rf $LS_SUBCWD .
ls
echo `find . -type d | grep /`
echo 'running'
python {looper} pycfg.py config.pck --options=options.json >& local.output
exit $? 
#echo
#echo 'sending the job directory back'
#echo cp -r Loop/* $LS_SUBCWD 
""".format(looper=looper.__file__)
   return script

def batchScriptCERN( jobDir ):
   # exactly the same as previous batchScriptCERN_FCC
   '''prepare the CONDOR version of the batch script, to run on CONDOR'''

   dirCopy = """echo 'sending the logs back'  # will send also root files if copy failed
cp -r Loop/* $LS_SUBCWD
if [ $? -ne 0 ]; then
   echo 'ERROR: problem copying job directory back'
else
   echo 'job directory copy succeeded'
fi"""
   cpCmd=dirCopy

   script_old = """#!/bin/bash
unset LD_LIBRARY_PATH
unset PYTHONHOME
export PYTHONPATH={pythonpath}
echo 'copying job dir to worker'
source {fccswpath}/init_fcc_stack.sh
cd $HEPPY
source ./init.sh
echo 'environment:'
echo
env | sort
echo
which python
cd -
cp -rf $LS_SUBCWD .
ls
cd `find . -type d | grep _pp_`
echo 'running'
python {looper} config.pck {heppy_option_str}
echo
{copy}
""".format(looper=looper.__file__,
           heppy_option_str=heppy_option_str, 
           copy=cpCmd,
           pythonpath=os.getcwd(), fccswpath=os.environ['FCCSWPATH'])

# IMPORTANT -> need to make safer get back of the files with line :
# cd `find . -type d | grep _pp_`
# intially it was :
# cd `find . -type d | grep /`
# but condor generates var and tmp directorirs which makes this command not working
# -> and job fails as it cannot get back the output files/dirs


# new setup :
# -----------

#  add these lines in init.sh
#export FCCEDM="unused"
#export PODIO="unused"
#export FCCPHYSICS="unused"
#export FCCSWPATH="unused"

# the script to use and comment old above :
#   script_new = """#!/bin/bash
#unset LD_LIBRARY_PATH
#unset PYTHONHOME
#export PYTHONPATH={pythonpath}
#echo 'copying job dir to worker'
#source {fccswpath}/setup.sh
#cd $HEPPY
#source ./init.sh
#export FCCEDM="unused"
#export PODIO="unused"
#export FCCPHYSICS="unused"
#echo 'environment:'
#echo
#env | sort
#echo
#which python
#cd -
#cp -rf $LS_SUBCWD .
#ls
#cd `find . -type d | grep _pp_`
#echo 'running'
#python {looper} config.pck {heppy_option_str}
#echo
#{copy}
#""".format(looper=looper.__file__,
#           heppy_option_str=heppy_option_str,
#           copy=cpCmd,
#           pythonpath=os.getcwd(), fccswpath=os.environ['FCCVIEW'])

   script = script_old
   #script = script_new

   return script

def batchScriptPSI( index, jobDir, remoteDir=''):
   '''prepare the SGE version of the batch script, to run on the PSI tier3 batch system'''

   cmssw_release = os.environ['CMSSW_BASE']
   VO_CMS_SW_DIR = "/swshare/cms"  # $VO_CMS_SW_DIR doesn't seem to work in the new SL6 t3wn

   if remoteDir=='':
       cpCmd="""echo 'sending the job directory back'
rm Loop/cmsswPreProcessing.root
cp -r Loop/* $SUBMISIONDIR"""
   elif remoteDir.startswith("/pnfs/psi.ch"):
       cpCmd="""echo 'sending root files to remote dir'
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/lib64/dcap/ # Fabio's workaround to fix gfal-tools
for f in Loop/mt2*.root
do
   ff=`basename $f | cut -d . -f 1`
   #d=`echo $f | cut -d / -f 2`
   gfal-mkdir {srm}
   echo "gfal-copy file://`pwd`/Loop/$ff.root {srm}/${{ff}}_{idx}.root"
   gfal-copy file://`pwd`/Loop/$ff.root {srm}/${{ff}}_{idx}.root
   if [ $? -ne 0 ]; then
      echo "ERROR: remote copy failed for file $ff"
   else
      echo "remote copy succeeded"
      rm Loop/$ff.root
   fi
done
rm Loop/cmsswPreProcessing.root
cp -r Loop/* $SUBMISIONDIR""".format(idx=index, srm='srm://t3se01.psi.ch'+remoteDir+jobDir[jobDir.rfind("/"):jobDir.find("_Chunk")])
   else:
      print "remote directory not supported yet: ", remoteDir
      print 'path must start with "/pnfs/psi.ch"'
      sys.exit(1)
      

   script = """#!/bin/bash
shopt expand_aliases
##### MONITORING/DEBUG INFORMATION ###############################
DATE_START=`date +%s`
echo "Job started at " `date`
cat <<EOF
################################################################
## QUEUEING SYSTEM SETTINGS:
HOME=$HOME
USER=$USER
JOB_ID=$JOB_ID
JOB_NAME=$JOB_NAME
HOSTNAME=$HOSTNAME
TASK_ID=$TASK_ID
QUEUE=$QUEUE

EOF
echo "######## Environment Variables ##########"
env
echo "################################################################"
TOPWORKDIR=/scratch/`whoami`
JOBDIR=sgejob-$JOB_ID
WORKDIR=$TOPWORKDIR/$JOBDIR
SUBMISIONDIR={jdir}
if test -e "$WORKDIR"; then
   echo "ERROR: WORKDIR ($WORKDIR) already exists! Aborting..." >&2
   exit 1
fi
mkdir -p $WORKDIR
if test ! -d "$WORKDIR"; then
   echo "ERROR: Failed to create workdir ($WORKDIR)! Aborting..." >&2
   exit 1
fi

#source $VO_CMS_SW_DIR/cmsset_default.sh
source {vo}/cmsset_default.sh
export SCRAM_ARCH=slc6_amd64_gcc481
#cd $CMSSW_BASE/src
cd {cmssw}/src
shopt -s expand_aliases
cmsenv
cd $WORKDIR
cp -rf $SUBMISIONDIR .
ls
cd `find . -type d | grep /`
echo 'running'
python {looper} pycfg.py config.pck --options=options.json
echo
{copy}
###########################################################################
DATE_END=`date +%s`
RUNTIME=$((DATE_END-DATE_START))
echo "################################################################"
echo "Job finished at " `date`
echo "Wallclock running time: $RUNTIME s"
exit 0
""".format(jdir=jobDir, vo=VO_CMS_SW_DIR,cmssw=cmssw_release, looper=looper.__file__, copy=cpCmd)

   return script

def batchScriptIC(jobDir):
   '''prepare a IC version of the batch script'''


   cmssw_release = os.environ['CMSSW_BASE']
   script = """#!/bin/bash
export X509_USER_PROXY=/home/hep/$USER/myproxy
source /vols/cms/grid/setup.sh
cd {jobdir}
cd {cmssw}/src
eval `scramv1 ru -sh`
cd -
echo 'running'
python {looper} pycfg.py config.pck --options=options.json
echo
echo 'sending the job directory back'
mv Loop/* ./ && rm -r Loop
""".format(jobdir = jobDir, looper=looper.__file__, cmssw = cmssw_release)
   return script

def batchScriptLocal(  remoteDir, index ):
   '''prepare a local version of the batch script, to run using nohup'''

   script = """#!/bin/bash
echo 'running'
python {looper} config.pck --options=options.json {heppy_option_str}
echo
echo 'sending the job directory back'
mv Loop/* ./
""".format(looper=looper.__file__, heppy_option_str=heppy_option_str) 
   return script


class MyBatchManager( BatchManager ):
   '''Batch manager specific to cmsRun processes.''' 
         
   def PrepareJobUser(self, jobDir, value ):
      '''Prepare one job. This function is called by the base class.'''
      print value
      print self.components[value]

      #prepare the batch script
      scriptFileName = jobDir+'/batchScript.sh'
      scriptFile = open(scriptFileName,'w')
      storeDir = self.remoteOutputDir_.replace('/castor/cern.ch/cms','')
      mode = self.RunningMode(self.options_.batch)
      if mode == 'LXPLUS':
         scriptFile.write( batchScriptCERN( jobDir ) )
      elif mode == 'PSI':
         # storeDir not implemented at the moment
         scriptFile.write( batchScriptPSI ( value, jobDir, storeDir ) ) 
      elif mode == 'LOCAL':
         # watch out arguments are swapped (although not used)         
         scriptFile.write( batchScriptLocal( storeDir, value) ) 
      elif mode == 'PISA' :
         scriptFile.write( batchScriptPISA( storeDir, value) ) 	
      elif mode == 'PADOVA' :
         scriptFile.write( batchScriptPADOVA( value, jobDir) )        
      elif mode == 'IC':
         scriptFile.write( batchScriptIC(jobDir) )
      scriptFile.close()
      os.system('chmod +x %s' % scriptFileName)

      # save the configuration python file for later unpickling of the
      # config
      shutil.copy(batchManager.cfgFileName,
                  '/'.join([jobDir, '__cfg_to_run__.py']))
      # update components in config for this job,
      # and save it as a pickle file
      cfo = copy.deepcopy(self.config)
      cfo.components = [ self.components[value] ]
      with open('/'.join([jobDir, 'config.pck']), 'w') as outconfig:
         pickle.dump(cfo, outconfig, protocol=-1)
      if hasattr(self,"heppyOptions_"):
         optjsonfile = open(jobDir+'/options.json','w')
         optjsonfile.write(json.dumps(self.heppyOptions_))
         optjsonfile.close()


def create_batch_manager(): 
   batchManager = MyBatchManager()
   batchManager.parser_.usage="""
    %prog [options] <cfgFile>

    Run Colin's python analysis system on the batch.
    Job splitting is determined by your configuration file.
    """
   return batchManager


def main(options, heppy_args, batchManager): 
   batchManager.cfgFileName = args[0]

   handle = open(batchManager.cfgFileName, 'r')
   cfo = imp.load_source('__cfg_to_run__',
                         batchManager.cfgFileName,
                         handle)
   config = cfo.config
   handle.close()

   versions = None
   config.versions = Versions(batchManager.cfgFileName)
   batchManager.config = config

   batchManager.components = split( [comp for comp in config.components \
                                     if len(comp.files)>0] )
   listOfValues = range(0, len(batchManager.components))
   listOfNames = [comp.name for comp in batchManager.components]

   batchManager.PrepareJobs( listOfValues, listOfNames )
   waitingTime = 0.1
   batchManager.SubmitJobs( waitingTime )
 
def looper_options(batchManager, options):
   '''select a subset of options,
   and return the option string that can be used on the command line,
   when calling the looper in the batch scripts.
   '''
   select = ['--nevents']
   opts = []
   for opt in batchManager.parser_.option_list:
      optstr = opt.get_opt_string()
      if optstr not in select:
         continue
      else:
         value = getattr(options, opt.dest)
         opts.append('{}={}'.format(optstr, value))
   return ' '.join(opts)

if __name__ == '__main__':
   import sys
   batchManager = create_batch_manager()
   batchManager.parser_.add_option(
      "-N", "--nevents",
      dest="nevents",
      type="int",
      help="number of events to process",
      default=sys.maxint
   )
   options, args = batchManager.ParseOptions()
   from heppy.framework.heppy_loop import _heppyGlobalOptions
   for opt in options.extraOptions:
      if "=" in opt:
         (key,val) = opt.split("=",1)
         _heppyGlobalOptions[key] = val
      else:
         _heppyGlobalOptions[opt] = True
   batchManager.heppyOptions_=_heppyGlobalOptions
   heppy_option_str = looper_options(batchManager, options)
   main(options, args, batchManager)
