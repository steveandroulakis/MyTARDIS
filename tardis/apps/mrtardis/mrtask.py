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
mrtask.py

.. moduleauthor::  Grischa Meyer <grischa.meyer@monash.edu>

"""

import os
import re
import zipfile

from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.core.urlresolvers import reverse

#from tardis.tardis_portal.models import DatasetParameter
#from tardis.tardis_portal.models import Schema
#from tardis.tardis_portal.models import ParameterName
from tardis.tardis_portal.models import Dataset_File

import tardis.apps.mrtardis.utils as utils
from tardis.apps.mrtardis.models import HPCUser
from tardis.apps.mrtardis.task import Task


class MRtask(Task):
    """
    Subclass of :class:`tardis.apps.mrtardis.task.Task`
    official task tasktype: "mrtardis"
    """
    schema_name = "http://localhost/task/mrtardis"

    def run(self, request):
        """
        run task on cluster
        :param user: hpc username
        :type user: string
        """
        username = HPCUser.objects.get(user=request.user).hpc_username
        print self.get_status()
        try:
            ready = self.get_param("readyToSubmit", value=True) == "yes"
        except ObjectDoesNotExist:
            return False
        if not ready:
            return False
        self.makeJobScripts(request)
        self.stageToHPC(username)
        print "staged"
        jobids = self.run_staged_task(username)
        print jobids
        self.set_status("running")
        self.set_param_list("jobid", jobids)
        return jobids

    def add_pdb_files(self):
        """
        extract PDB files from zips then add all pdb filenames as parameters
        """
        self.extractPDBzips()
        pdbfiles = Dataset_File.objects.filter(dataset=self.dataset,
                                               filename__iendswith=".pdb")
        self.delete_params("PDBfile")
        for pdbfile in pdbfiles:
            self.new_param("PDBfile", pdbfile.filename)

    def extractPDBzips(self):
        """
        Extracts pdb files out of zips, adds them to the dataset and
        removes the zip.
        """
        zipquery = Dataset_File.objects.filter(dataset=self.dataset,
                                               filename__iendswith=".zip")
        for zipfileobj in zipquery:
            zippath = zipfileobj.get_absolute_filepath()
            thiszip = zipfile.ZipFile(zippath, 'r')
            extractlist = []
            for filename in thiszip.namelist():
                if filename.endswith((".pdb", ".PDB")) and \
                        not filename.startswith("__MACOSX"):
                    extractlist.append(filename)
            thiszip.extractall(settings.STAGING_PATH, extractlist)
            thiszip.close()
            for pdbfile in extractlist:
                #print pdbfile
                utils.add_staged_file_to_dataset(pdbfile, self.dataset.id,
                                           mimetype="chemical/x-pdb")
            zipfileobj.deleteCompletely()

    def add_mtz_file(self):
        """
        parses an MTZ file, adds its name and the metadata as parameters
        """
        mtzfiles = Dataset_File.objects.filter(dataset=self.dataset,
                                               filename__iendswith=".mtz")
        if len(mtzfiles) == 0:
            return False
        mtzfilepars = self.get_params("mtzFileName")
        for oldmtzfile in mtzfilepars:
            oldfile = Dataset_File.objects.get(
                dataset=self.dataset,
                filename=oldmtzfile.string_value)
            oldfile.deleteCompletely()
        mtzfiles = Dataset_File.objects.filter(dataset=self.dataset,
                                               filename__iendswith=".mtz")
        file_location = mtzfiles[0].get_absolute_filepath()
        metadataDict = MRtask.processMTZ(file_location)
        self.set_param("mtzFileName", mtzfiles[0].filename, "MTZ file")
        self.set_params_from_dict(metadataDict)
        return True

    def set_params_from_dict(self, dict):
        """
        set param from dictionary
        possible duplicate with a task member method
        """
        print type(dict)
        for (key, value) in dict.iteritems():
            if type(value) is list:
                self.set_param_list(key, value)
            else:
                self.set_param(key, value)

    def get_form_dictionary(self):
        """
        get dictionary to pass as initial value to MR paramForm
        """
        formargs = dict()
        ready = True
        par_strings = ["f_value",
                       "sigf_value",
                       "mol_weight",
                       "num_in_asym",
                       "packing",
                       "ensemble_number"]
        for par_string in par_strings:
            try:
                formargs[par_string] = self.get_param(par_string, value=True)
            except ObjectDoesNotExist:
                ready = False

        try:
            formargs["sg_all"] = self.get_param(
                "sg_all").string_value == "True"
        except ObjectDoesNotExist:
            pass

        formargs["space_group"] = [
            par.string_value
            for par in self.get_params("space_group")]

        readyToSubmit = (ready and
                         len(formargs["space_group"]) > 0 and
                         len(self.get_params("rmsd")) > 0)
        if readyToSubmit:
            self.set_param("readyToSubmit", "yes")
        else:
            self.delete_params("readyToSubmit")
        return formargs

    def getPhaserCommands(self, space_group, rmsd, pdb_filename):
        """
        create string with commands to be piped into phaser.
        Takes strings or numbers (for rmsd) as input.
        :param space_group: space group string or "ALL"
        :param rmsd: float or string with rmsd value
        :type rmsd: float or string
        :type pdb_filename: string with pdb filename
        """
        f_value = self.get_param("f_value", value=True)
        sigf_value = self.get_param("sigf_value", value=True)
        mol_weight = str(self.get_param("mol_weight", value=True))
        num_in_asym = str(self.get_param("num_in_asym", value=True))
        ensemble_number = str(self.get_param("ensemble_number", value=True))
        packing = str(self.get_param("packing", value=True))
        mtz_filename = self.get_param("mtzFileName", value=True)
        phaserinput = ("MODE MR_AUTO\\n" + "HKLIN " + mtz_filename +
                       "\\n" + "LABIN  F=" + f_value + " " + "SIGF=" +
                       sigf_value +
                       "\\n" + "TITLE " + pdb_filename + "_" + space_group +
                       "_" + str(rmsd) + "\\n")
        if space_group == "ALL":
            phaserinput += "SGALTERNATIVE ALL\\n"
        else:
            phaserinput += "SGALTERNATIVE TEST " + space_group + "\\n"

        phaserinput += ("COMPOSITION PROTEIN MW " + mol_weight +
                       " NUMBER " + num_in_asym + "\\n" +
                       "ENSEMBLE pdb PDBFILE " + pdb_filename +
                       " RMS " + str(rmsd) + "\\n" +
                       "SEARCH ENSEMBLE pdb NUMBER " + ensemble_number +
                        "\\n" +
                       "PACK CUTOFF " + packing + "\\n" +
                       "ROOT " + pdb_filename + "_" + space_group + "_" +
                       str(rmsd) + "_result\\n")
        return phaserinput

    def makeJobScripts(self, request):
        """
        create PBS/OGE job submission files, one for
        each rmsd, pdb file and spacegroup
        """
        time = "12:0:0"
        pbs_prefix = "#$ "
        pbs_head = "#!/bin/sh\n"
        pbs_head += "%s-m abe\n" % pbs_prefix
        pbs_head += "%s-S /bin/bash\n" % pbs_prefix
        pbs_head += "%s-cwd\n" % pbs_prefix
        pbs_head += "%s-l h_rt=%s\n" % (pbs_prefix, time)
        pbs_commands = "\n. /etc/profile\n"
        pbs_commands += "module load phenix\n"
        pbs_commands += ". $PHENIX/build/$PHENIX_MTYPE/setpaths.sh\n"
        pingurl = request.build_absolute_uri(
            reverse('tardis.apps.mrtardis.views.jobfinished',
                    args=[self.dataset.id]))
        wget_command = "wget -O - %s?jobid=$JOB_ID" % pingurl
        #pbs_footer = "while [[ \"true\" != `%s` ]]; do continue; done\n" %\
        #    wget_command
        pbs_footer = wget_command
        phaser_command = "phenix.phaser"
        spacegroups = [utils.sgNumNameTrans(number=sgnum)
                       for sgnum in self.get_params("space_group", value=True)]
        if self.get_param("sg_all", value=True) == "True":
            spacegroups.append("ALL")
        rmsds = self.get_params("rmsd", value=True)
        for pdbfile in self.get_params("PDBfile", value=True):
            for sg in spacegroups:
                for rmsd in rmsds:
                    parameters = self.getPhaserCommands(sg,
                                                        rmsd,
                                                        pdbfile)
                    output = pbs_head + pbs_commands
                    output += "echo -e \"" + parameters + "\"|" +\
                        phaser_command + " \n"
                    output += pbs_footer
                    jobfilename = pdbfile + "_" + sg + "_" + \
                        str(rmsd) + ".jobfile"
                    ofile = open(os.path.join(settings.STAGING_PATH,
                                              jobfilename), 'w')
                    ofile.write(output)
                    ofile.close()
                    utils.add_staged_file_to_dataset(
                        jobfilename,
                        self.dataset.id,
                        mimetype="application/x-shellscript")
                    self.new_param("jobscript", jobfilename)

    def parseResults(self):
        # example: SOLU SET RFZ=2.2 TFZ=3.5 PAK=0 LLG=-350 LLG=-349
        regexstring = "SOLU SET RFZ=[+-]?\d*\.\d+ TFZ=([+-]?\d*\.\d+)" +\
            " PAK=[+-]?\d*\d+ LLG=[+-]?\d*\d+ LLG=([+-]?\d*\d+)"
        parsesol = re.compile(regexstring)
        resultsArray = []

        def get_DF_by_name(name):
            return Dataset_File.objects.get(dataset=self.dataset,
                                            filename=name)
        # get basename from jobscript
        for job in self.get_params("jobscript", value=True):
            basename = job[:-8]
            pdb_file, spacegroup, rmsd = basename.split("_")
            mtzresultDF = get_DF_by_name(basename + "_result.1.mtz")
            pdbresultDF = get_DF_by_name(basename + "_result.1.pdb")
            solfileDF = get_DF_by_name(basename + "_result.sol")
            sumfileDF = get_DF_by_name(basename + "_result.sum")
            solfile = open(solfileDF.get_absolute_filepath(), 'r')
            sollines = solfile.readlines()
            solfile.close()
            solresults = parsesol.search(sollines[2])
            print sollines[2]
            print solresults
            zScore = solresults.group(1)
            LLG = solresults.group(2)
            resultsArray.append({'name': basename,
                                 'pdb_file': pdb_file,
                                 'spacegroup': spacegroup,
                                 'rmsd': rmsd,
                                 'mtzresult': mtzresultDF,
                                 'pdbresult': pdbresultDF,
                                 'solfile': solfileDF,
                                 'sumfile': sumfileDF,
                                 'zScore': zScore,
                                 'LLG': LLG,
                                 })
        return resultsArray

    @staticmethod
    def processMTZ(mtzfile):
        """
        static method to extract data from metadata block of mtz file
        based on http://www.ccp4.ac.uk/html/mtzformat.html#fileformat
        :param mtzfile: full path to mtz file
        :type mtzfile: string
        :returns: a dictionary with parameters/metadata
        """
        metadata = MRtask._extractMetaDataFromMTZFile(mtzfile)
        parameters = dict()
        parameters["f_values"] = []
        parameters["sigf_values"] = []
        for line in metadata:
            first_space = line.find(" ")
            if len(line) > first_space + 1 + 30 + 1 and line[
                first_space + 1 + 30 + 1] == "F":
                parameters["f_values"].append(
                    line[7:first_space + 1 + 30 + 1].strip())
            elif len(line) > first_space + 1 + 30 + 1 and line[
                first_space + 1 + 30 + 1] == "Q":
                parameters["sigf_values"].append(
                        line[7:first_space + 1 + 30 + 1].strip())
            elif line.startswith("SYMINF"):
                fields = line.split()
                #print fields[4]
                parameters["spacegroup_mtz"] = int(fields[4])
        return parameters

    @staticmethod
    def _extractMetaDataFromMTZFile(filepath):
        """
        static method that extracts meta data from end of MTZ file
        :param filepath: full filepath to MTZ file
        :type filepath: string
        :returns: a string with the metadata section of the MTZ file
        """
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
