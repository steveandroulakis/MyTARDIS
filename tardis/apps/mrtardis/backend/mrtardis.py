
__author__= "grischa"
__date__ = "$15/09/2010 3:14:35 PM$"

import hpc
import secrets
import hpcjob
import utils

if __name__ == "__main__":
    #print "Hello World"
    myHPC = hpc.hpc(secrets.hostname, "lala", key = secrets.privatekey, keytype = "rsa")
    if myHPC.testConnection():
        print "It worked!"
    (out,err) = myHPC.getOutputError("Qstat")
    print out
    print err

def runJob(parameters, files, username):
    myJob = hpcjob.HPCJob(username)
    myJob.stage(parameters, files)
    myJob.submit()
    #print myJob.status()
    return myJob

def processMTZ(mtzfile):
    """extract data from metadata block of mtz file"""
    #based on http://www.ccp4.ac.uk/html/mtzformat.html#fileformat
    metadata = utils.extractMetaDataFromMTZFile(mtzfile)
    parameters = dict()
    parameters["f_value"] = []
    parameters["sigf_value"] = []
    for line in metadata:
        first_space = line.find(" ")
        if len(line) > first_space + 1 + 30 + 1 and line[first_space + 1 + 30 + 1] == "F":
            parameters["f_value"].append( line[7:first_space + 1 + 30 + 1].strip() )
        elif len(line) > first_space + 1 + 30 + 1 and line[first_space + 1 + 30 + 1] == "Q":
                parameters["sigf_value"].append( line[7:first_space + 1 + 30 + 1].strip() )
        elif line.startswith("SYMINF"):
            fields = line.split()
            #print fields[4]
            parameters["spacegroup"] = utils.spacegroupNumberNameTranslation(number = fields[4])
    return parameters

#COLUMN FP                             F            1.7000         1178.5000    1
#123456 123456789012345678901234567890 1
