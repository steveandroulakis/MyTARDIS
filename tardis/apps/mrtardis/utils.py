# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Monash e-Research Centre
#   (Monash University, Australia)
# Copyright (c) 2010, VeRSI Consortium
#   (Victorian eResearch Strategic Initiative, Australia)
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    *  Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    *  Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#    *  Neither the name of the VeRSI, the VeRSI Consortium members, nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE7
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
"""
utils.py

.. moduleauthor::  Grischa Meyer <grischa.meyer@monash.edu>

"""

import os
import shutil

from django.conf import settings

from tardis.tardis_portal.models import Dataset
from tardis.tardis_portal.models import Dataset_File
from tardis.tardis_portal.staging import duplicate_file_check_rename
from tardis.tardis_portal.logger import logger

from tardis.apps.mrtardis.hpc import HPC
from tardis.apps.mrtardis.models import HPCUser


def test_hpc_connection(user):
    """
    :param user: user object
    :returns: True/False after trying to connect to the cluster,
    sets a flag if successful and returns True if flag is set as
    True without testing the connection first
    """
    logger.debug("testing if user exists")
    try:
        hpcuser = HPCUser.objects.get(user=user)
    except HPCUser.DoesNotExist:
        return False
    #logger.debug(dir(hpcuser))
    if hpcuser.testedConnection:
        #logger.debug("testConnection = True")
        return hpcuser.hpc_username
    myHPC = HPC(location="msg", username=hpcuser.hpc_username)
    if myHPC.testConnection():
        hpcuser.testedConnection = True
        #logger.debug("tested for real: " + repr(hpcuser.testedConnection))
        hpcuser.save()
        return hpcuser.hpc_username
    else:
        hpcuser.testedConnection = False
        hpcuser.save()
        return False


def getPublicKey():
    """leftover from before"""
    return HPC.getPublicKey()


def sgNumNameTrans(number=None, name=None):
    """
    translates between space group number and names
    :param number: number of a space group
    :type number: integer
    :param name: name of a space group
    :tpye name: string
    :returns: the parameter that was not provided
    """
    ttable = {1: "P1",
              3: "P2", 4: "P21",
              5: "C2",
              16: "P222", 17: "P2221", 18: "P21212", 19: "P212121",
              20: "C2221", 21: "C222",
              22: "F222",
              23: "I222", 24: "I212121",
              75: "P4", 76: "P41", 77: "P42", 78: "P43",
              79: "I4", 80: "I41",

              89: "P422", 90: "P4212", 91: "P4122", 92: "P41212", 93: "P4222",
              94: "P42212", 95: "P4322", 96: "P43212",

              97: "I422", 98: "I4122",
              143: "P3", 144: "P31", 145: "P32",
              146: "R3", 155: "R32",
              149: "P312", 151: "P3112", 153: "P3212",
              150: "P321", 152: "P3121", 154: "P3221",

              168: "P6", 169: "P61", 170: "P65", 171: "P62",
              172: "P64", 173: "P63",

              177: "P622", 178: "P6122", 179: "P6522", 180: "P6222",
              181: "P6422", 182: "P6322",

              195: "P23", 198: "P213",
              196: "F23",
              197: "I23", 199: "I213",
              207: "P432", 208: "P4232",
              209: "F432", 210: "F4132", 212: "P4332", 213: "P4132",
              211: "I432", 214: "I4132", }
    if number != None and name == None:
        if type(number).__name__ != 'int':
            number = int(number)
        return ttable[number]
    elif number == None and name != None:
        for (key, value) in ttable.iteritems():
            if value == name:
                return key
    else:
        return False
    return False


def getGroupNumbersFromNumber(number):
    """
    get Space Groups in Group from Space Group number
    :param number: space group number
    :type number: integer
    :returns: array of numbers
    """
    r = lambda x, y: range(x, y + 1)  # useful shortcut for ranges
    grouping = [[1],  # triclinic
                [3, 4],  # monoclinic p
                [5],  # monoclinic c
                r(16, 19),  # orthorhombic p
                [20, 21],  # orthorhombic c
                [22],  # orthorhombic f
                [23, 24],  # orthorhombic i
                r(75, 78),  # tetragonal p4
                [79, 80],  # tetragonal i4
                r(89, 96),  # tetragonal p422
                [97, 98],  # tetragonal i422
                r(143, 145),  # trigonal p3
                [146, 155],  # trigonal r
                [149, 151, 153],  # trigonal p312
                [150, 152, 154],  # trigonal p321
                r(168, 173),  # hexagonal p6
                r(177, 182),  # hexagonal p622
                [195, 198],  # cubic p2
                [196],  # cubic f2
                [197, 199],  # cubic i2
                [207, 208, 212, 213],  # cubic p4
                [209, 210],  # cubic f4
                [211, 214],  # cubic i4
                ]
    mydict = dict()
    for item in grouping:
        for jtem in item:
            mydict[jtem] = item
    if number in mydict:
        return mydict[number]
    else:
        return []


def calcMW(sequence):
    """
    input sequence and get molecular weight
    :param sequence: string with protein sequence
    :type sequence: string
    :returns: float
    """
    MWtable = {"A": 71.0788, "C": 103.1388, "D": 115.0886,
               "E": 129.1155, "F": 147.1766, "G": 57.0519,
               "H": 137.1411, "I": 113.1594, "K": 128.1741,
               "L": 113.1594, "M": 131.1926, "N": 114.1038,
               "P": 97.1167, "Q": 128.1307, "R": 156.1875,
               "S": 87.0782, "T": 101.1051, "V": 99.1326,
               "W": 186.2132, "Y": 163.1760,
               }
    mw = 0.0
    for aa in sequence.upper():
        try:
            mw += MWtable[aa]
        except:
            pass
    return mw


def add_staged_file_to_dataset(rel_filepath, dataset_id,
                               mimetype="application/octet-stream"):
    """
    add file in STAGING_PATH to a dataset
    may be replaced by main code functions.
    quick and dirty hack to get it working
    """
    originfilepath = os.path.join(settings.STAGING_PATH, rel_filepath)
    dataset = Dataset.objects.get(pk=dataset_id)
    newDatafile = Dataset_File()
    newDatafile.dataset = dataset
    newDatafile.size = os.path.getsize(originfilepath)
    newDatafile.protocol = "file"
    newDatafile.mimetype = mimetype
    file_dir = "/" + str(dataset.experiment.id) + "/" + str(dataset.id) + "/"
    file_path = file_dir + rel_filepath
    prelim_full_file_path = settings.FILE_STORE_PATH + file_path
    full_file_path = duplicate_file_check_rename(prelim_full_file_path)
    if prelim_full_file_path == full_file_path:
        newDatafile.filename = rel_filepath
    else:
        newDatafile.filename = full_file_path[len(settings.FILE_STORE_PATH)
                                              + len(file_dir):]
    newDatafile.url = "file://" + full_file_path
    shutil.move(originfilepath, full_file_path)
    newDatafile.save()
