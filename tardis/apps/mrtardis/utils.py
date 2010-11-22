from tardis.apps.mrtardis.models import MrTUser, Job
#from django.contrib.auth.models import User

import tardis.apps.mrtardis.backend.hpc as hpc
import tardis.apps.mrtardis.backend.hpcjob as hpcjob
import tardis.apps.mrtardis.backend.secrets as secrets
#from tardis.tardis_portal.logger import logger


def test_hpc_connection(user):
    try:
        hpcuser = MrTUser.objects.get(pk=user.id)
    except MrTUser.DoesNotExist:
        return False
#    logger.debug(dir(hpcuser))
    if hpcuser.testedConnection:
#        logger.debug("testConnection = True")
        return True
    myHPC = hpc.hpc(secrets.hostname,
                    hpcuser.hpc_username,
                    type="sge", authtype="key",
                    key=secrets.privatekey, keytype="rsa")
    if myHPC.testConnection():
        hpcuser.testedConnection = True
#        logger.debug("tested for real: " + `hpcuser.testedConnection`)
        hpcuser.save()
        return True
    else:
        hpcuser.testedConnection = False
        hpcuser.save()
        return False


def getPublicKey():
    return secrets.publickey


def update_job_status(experiment_id, user_id):
    hpcuser = MrTUser.objects.get(pk=user_id)
    for job in Job.objects.filter(username=hpcuser.hpc_username):
        thisjob = hpcjob.HPCJob(username=hpcuser.hpc_username, jobid=job.jobid)
        stati = thisjob.status()
        for status in stati:
            jobentry = Job(jobid=job.jobid,
                           jobstatus=status,
                           experiment_id=experiment_id)
            jobentry.save()


def extractMetaDataFromMTZFile(filepath):
    """extracts meta data from end of MTZ file"""
    ifile = open(filepath, 'r')
    file_contents = ""
    lines = ifile.readlines()
    for line in lines:
        if "VERS MTZ" in line.upper():
            file_contents += line + "\n"
    ifile.close()
    meta_data_start = file_contents.index("VERS MTZ")
    meta_data = file_contents[meta_data_start:].strip()
    meta = []
    for i in range(len(meta_data) / 80 + 1):
        if (i + 1) * 80 < len(meta_data):
            meta.append(meta_data[i * 80:(i + 1) * 80])
        else:
            meta.append(meta_data[i * 80:])
    return meta


def spacegroupNumberNameTranslation(number=None, name=None):
    translation_table = {1: "P1", 3: "P2", 4: "P21",
                         5: "C2", 16: "P222", 17: "P2221",
                         18: "P21212", 19: "P212121", 20: "C2221",
                         21: "C222", 22: "F222", 23: "I222",
                         24: "I212121", 75: "P4", 76: "P41",
                         77: "P42", 78: "P43", 79: "I4",
                         80: "I41", 89: "P422", 90: "P4212",
                         91: "P4122", 92: "P41212", 93: "P4222",
                         94: "P42212", 95: "P4322", 96: "P43212",
                         97: "I422", 98: "I4122", 143: "P3",
                         144: "P31", 145: "P32", 146: "R3",
                          149: "P312", 150: "P321", 151: "P3112",
                          152: "P3121", 153: "P3212", 154: "P3221",
                          155: "R32", 168: "P6",
                          169: "P61", 170: "P65", 171: "P62",
                          172: "P64", 173: "P63", 177: "P622",
                          178: "P6122", 179: "P6522", 180: "P6222",
                          181: "P6422", 182: "P6322", 195: "P23",
                          196: "F23", 197: "I23", 198: "P213",
                          199: "I213", 207: "P432", 208: "P4232",
                          209: "F432", 210: "F4132", 211: "I432",
                          212: "P4332", 213: "P4132", 214: "I4132", }
    if number != None and name == None:
        if type(number).__name__ != 'int':
            number = int(number)
        return translation_table[number]
    elif number == None and name != None:
        for (key, value) in translation_table.iteritems():
            if value == name:
                return key
    else:
        return False


def getSpaceGroupGroup(sgNumber):
    """get Space Group Group from Space Group number"""
    types = {1: "triclinic",
             3:  "monoclinic_p", 4: "monoclinic_p",
             5: "monoclinic_c",
             16: "orthorhombic_p", 17: "orthorhombic_p", 18: "orthorhombic_p",
             19: "orthorhombic_p",
             20: "orthorhombic_c", 21: "orthorhombic_c",
             22: "orthorhombic_f",
             23: "orthorhombic_i", 24: "orthorhombic_i",
             75: "tetragonal_p4", 76: "tetragonal_p4", 77: "tetragonal_p4",
             78: "tetragonal_p4",
             79: "tetragonal_i4", 80: "tetragonal_i4",
             89: "tetragonal_p422", 90: "tetragonal_p422",
             91: "tetragonal_p422",
             92: "tetragonal_p422", 93: "tetragonal_p422",
             94: "tetragonal_p422",
             95: "tetragonal_p422", 96: "tetragonal_p422",
             97: "tetragonal_i422", 98: "tetragonal_i422",
             143: "trigonal_p3", 144: "trigonal_p3", 145: "trigonal_p3",
             146: "trigonal_r", 155: "trigonal_r",
             149: "trigonal_p312", 151: "trigonal_p312", 153: "trigonal_p312",
             150: "trigonal_p321", 152: "trigonal_p321", 154: "trigonal_p321",
             168: "hexagonal_p6", 169: "hexagonal_p6", 170: "hexagonal_p6",
             171: "hexagonal_p6", 172: "hexagonal_p6", 173: "hexagonal_p6",
             177: "hexagonal_p622", 178: "hexagonal_p622",
             179: "hexagonal_p622", 180: "hexagonal_p622",
             181: "hexagonal_p622", 182: "hexagonal_p622",
             195: "cubic_p2", 198: "cubic_p2",
             196: "cubic_i2",
             207: "cubic_p4", 208: "cubic_p4", 212: "cubic_p4",
             213: "cubic_p4",
             209:  "cubic_f4", 210: "cubic_f4",
             211:  "cubic_i4", 214: "cubic_i4", }
    return types[sgNumber]


def getSpaceGroupGroupHTML(sgNumber):
    group = getSpaceGroupGroup(sgNumber)
    filename = "spacegroups/" + group + ".html"
    return filename


def calcMW(sequence):
    """input sequence and get molecular weight"""
    MWtable = {"A": 71.0788, "C": 103.1388, "D": 115.0886,
               "E": 129.1155, "F": 147.1766, "G": 57.0519,
               "H": 137.1411, "I": 113.1594, "K": 128.1741,
               "L": 113.1594, "M": 131.1926, "N": 114.1038,
               "P": 97.1167, "Q": 128.1307, "R": 156.1875,
               "S": 87.0782, "T": 101.1051, "V": 99.1326,
               "W": 186.2132, "Y": 163.1760,
               }
    mw = 0
    for aa in sequence:
        mw += MWtable[aa]
    return mw
