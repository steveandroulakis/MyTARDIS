import glob
# To change this template, choose Tools | Templates
# and open the template in the editor.

__author__="grischa"
__date__ ="$15/09/2010 3:17:37 PM$"

# IMPORTS LOCAL
import uuid
import secrets
import hpc
# IMPORTS PYTHON STDLIB
import tempfile
import shutil
import zipfile
import os

if __name__ == "__main__":
    print "Hello World"

class HPCJob:
    """
    Class that holds submitted jobs
    """
    jobid = None
    idsOnHPC = []
    dirOnHPC = None
    myHPC = None
    filelist = []
    mtz_file_path = None
    parameters = None
    tmpdir = "" # temporary local staging directory
    jobfiles = [] # array of qsub jobs to submit
    retrieved = False
    username = None

    def __init__(self, username, jobid = -1):
        """create job with or without known jobid"""
        if jobid == -1:
            self.jobid = self.getUniqueID()
        else:
            self.jobid = jobid
        self.username = username
        self.dirOnHPC = "mrtardisjobs/" + self.jobid
        print "JOBID=" + self.jobid
    
    def _ensureHPC(self):
       if self.myHPC == None or not self.myHPC.testConnection():
            self.myHPC = hpc.hpc(secrets.hostname, self.username, key = secrets.privatekey, keytype = secrets.keytype)

    def status(self):
        """Returns status as Unknown Finished Queueing Running in dictionary with jobid key"""
        status = "Unknown"
        self._ensureHPC()
        output = dict()
        for jobid in self.idsOnHPC:
            #print jobid
            (out,err) = self.myHPC.getOutputError("source /etc/profile;qstat -j " + jobid)
            if err.startswith("Following jobs do not exist"):
                status = "Finished"
            else:
                lines = out.split("\n")
                for line in lines:
                    if line.startswith("Following jobs do not exist"):
                        status = "Finished"
                        break
                    elif line.startswith("usage"):
                        status =  "Running"
                        break
                    else:
                        status = "Queuing"
            output[jobid] = status
        return output

    def getUniqueID(self):
        return str(uuid.uuid1())

    def uploadToHPC(self):
        self._ensureHPC()
        #print "UPLOADING"
        self.myHPC.upload(self.dirOnHPC, self.filelist, self.tmpdir)
        #print "FINISHED UPLOADING"

    def submit(self):
        """submit job to queue after files have been uploaded, including a jobscript"""
        self._ensureHPC()
        print self.jobfiles
        for jobfile in self.jobfiles:
            (out,err) = self.myHPC.getOutputError("source /etc/profile; cd "+self.dirOnHPC+ "; qsub " + "-N " + jobfile + " " + jobfile)
            print out
            if err.strip() == "":
                self.idsOnHPC.append(out.split(" ")[2])
            else:
                print "ERROR 123"
                print err
        print self.idsOnHPC

    def stage(self, parameters, filenamearray):
        self.parameters = parameters
        self.tmpdir = tempfile.mkdtemp()
        for file in filenamearray:
            if file[-4:] == ".zip":
                myZip = zipfile.ZipFile(file, 'r')
                filelist = myZip.namelist()
                extractlist = []
                for file in filelist:
                    if not file.startswith("__MACOSX"):
                        extractlist.append(file)
                myZip.extractall(self.tmpdir, extractlist)
                myZip.close()
            elif file[-4:] == ".mtz":
                self.mtz_file_path = os.path.basename(file)
                shutil.copy(file, self.tmpdir)
            else:
                shutil.copy(file, self.tmpdir)
        self.makeJobScripts()
        self.filelist = os.listdir(self.tmpdir)
        #print self.filelist
        self.uploadToHPC()

    def retrieve(self, destdir):
        self._ensureHPC()
        srcdir = self.dirOnHPC
        destdir = destdir + "/" + self.jobid
        os.makedirs(destdir)
        self.myHPC.download(srcdir, destdir, excludefiles = self.filelist)
        self.retrieved = True

    def __del__(self):
        if self.retrieved:
            self.cleanuplocal()
            self.cleanupHPC()
        #print "cleaned up"

    def cleanuplocal(self):
        #print self.tmpdir
        shutil.rmtree(self.tmpdir)
        # TODO: add HPC cleanup later

    def cleanupHPC(self):
        self._ensureHPC()
        self.myHPC.rmtree(self.dirOnHPC)

    def makeJobScripts( self ):
        """create PBS/OGE job submission files, one for each pdb file and spacegroup"""
        time = "12:0:0"
        pbs_prefix = "#$ "
        pbs_head = "#!/bin/sh\n"
        pbs_head += pbs_prefix + "-m abe\n"
        pbs_head += pbs_prefix + "-S /bin/bash\n"
        pbs_head += pbs_prefix + "-cwd\n"
        pbs_commands = """
. /etc/profile
module load phenix
. $PHENIX/build/$PHENIX_MTYPE/setpaths.sh
"""
        pbs_options = pbs_prefix + "-l h_rt=" + time + "\n"
        phaser_command = "phenix.phaser"
        for pdbfile in glob.glob(self.tmpdir + "/*.pdb"):
            pdbfile = os.path.basename(pdbfile)
            if type(self.parameters["space_group"]).__name__ == 'string': # ie. not list or tuple
                spacegroups = [self.parameters["space_group"]]
            else:
                spacegroups = self.parameters["space_group"]
            for space_group in spacegroups:
                if type(self.parameters["rmsd"]).__name__ != 'list': # ie. not list or tuple
                    rmsds = [self.parameters["rmsd"]]
                else:
                    rmsds = self.parameters["rmsd"]
                for rmsd in rmsds:
                    #print pdbfile
                    parameters = self.preparePhaserInput( space_group, rmsd, pdbfile)
                    output = pbs_head + pbs_options + pbs_commands
                    output += "echo -e \"" + parameters + "\"|" + phaser_command + " \n"
                    jobfilename = pdbfile+ "_" + space_group + "_" +rmsd + ".jobfile"
                    ofile = open(self.tmpdir + "/" + jobfilename, 'w')
                    ofile.write(output)
                    ofile.close()
                    self.jobfiles.append(jobfilename)
    

    def preparePhaserInput(self,space_group, rmsd, pdb_file_path):
        f_value = self.parameters["f_value"]
        sigf_value = self.parameters["sigf_value"]
        mol_weight = self.parameters["mol_weight"]
        num_in_asym = self.parameters["num_in_asym"]
        ensemble_number = self.parameters["ensemble_number"]
        packing = self.parameters["packing"]
        phaserinput = "MODE MR_AUTO\\n" + "HKLIN "+ self.mtz_file_path + "\\n" +\
                      "LABIN  F="+ f_value + " " + "SIGF=" + sigf_value + "\\n" +\
                      "TITLE " + pdb_file_path + "_" + space_group + "_" + rmsd + "\\n"
        if space_group == "ALL":
            phaserinput += "SGALTERNATIVE ALL\\n"
        else:
            phaserinput += "SGALTERNATIVE TEST " + space_group + "\\n"
        
        phaserinput += "COMPOSITION PROTEIN MW " + mol_weight +\
                       " NUMBER " + num_in_asym + "\\n" +\
                       "ENSEMBLE pdb PDBFILE " + pdb_file_path +\
                       " RMS " + rmsd + "\\n" +\
                       "SEARCH ENSEMBLE pdb NUMBER "+ ensemble_number + "\\n" +\
                       "PACK CUTOFF " + packing + "\\n" +\
                       "ROOT " + pdb_file_path + "_" + space_group + "_" +\
                       rmsd +"_result\\n"
        return phaserinput
    
    def getJobType(self):
        return "This job is of the amazingly awesome type"

