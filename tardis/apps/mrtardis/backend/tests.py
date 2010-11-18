# Testing

## EXAMPLE USER INPUT BEGIN
example_input = { "f_value": "FP",
                  "sigf_value": "SIGFP",
                  "space_group": ["P6","P61"],
                  "mol_weight": "11807",
                  "sequence": "SEKIIHLTDDSFDTDVLKADGAILVDFWAEWCGPCKMIAPILDEIADEYQGKLTVAKLNIDQNPGTAPKYGIRGIPTLLLFKNGEVAATKVGALSKGQLKEFLDANLA",
                  "num_in_asym": "2",
                  "rmsd": "1.0",
                  "ensemble_number": "1",
                  "packing": "10",
}


mtzfile = "../../testfiles/2H74_structure_factors.mtz"
pdbfiles = [ "../../testfiles/example.zip"]
### EXAMPLE USER INPUT END
outputdir = "../../testresults/"

import mrtardis
import utils
import time

files = [mtzfile] + pdbfiles
newjob = mrtardis.runJob(example_input, files, "grischam")
finished = False
quit()
while not finished:
    status = newjob.status()
    print status
    if "Queuing" not in status.values() and "Running" not in status.values():
        finished = True
    time.sleep(30)
print "Finished"
newjob.retrieve(outputdir)
del newjob
