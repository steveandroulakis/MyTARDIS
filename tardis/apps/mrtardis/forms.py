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
forms.py

.. moduleauthor::  Grischa Meyer <grischa.meyer@monash.edu>

"""

from django import forms
import tardis.apps.mrtardis.utils as utils
from tardis.tardis_portal.logger import logger


class HPCSetupForm(forms.Form):
    """
    HPCSetupForm is a :class:`django.forms.Form` subclass that
    takes the HPC username.
    :attribute hpc_username: the HPC username
    """
    hpc_username = forms.CharField(max_length=30)


# examples in comments
class ParamForm(forms.Form):
    """
    ParamForm is a :class:`django.forms.Form` subclass. It displays
    existing/already extracted
    phaser parameters and asks the user for the remaining ones.
    :attribute f_value: the F column
    :attribute sigf_value: the SIGF column
    :attribute mol_weight: the molecular weight
    :attribute sequence: the protein sequence - optional
    :attribute num_in_asym: number of proteins in asymmetric unit
    :attribute space_group: a selection of valid space groups
    :attribute sg_all: whether phaser should try all valid space groups
    :attribute packing: packing cutoff, default = 10
    :attribute ensemble_number: Number of copies
    """
    # "FP" single value or array. needs selector
    f_value = forms.ChoiceField(label="F column", required=False)
    # "SIGFP" same functionality as f_value
    sigf_value = forms.ChoiceField(label="SIGF column", required=False)
    mol_weight = forms.FloatField(
                                 label="Molecular weight",
                                 required=False)  # "11807"
    # alternative to MW, calculate MW from sequence
    sequence = forms.CharField(max_length=2000, required=False,
                               label="Protein sequence, if MW is not known",
                               widget=forms.Textarea(attrs={'cols': 40,
                                                            'rows': 4}))
    # "SEKIIHLTDDSFDTDVLKADGAILVDFWAEWCGPCKMIAPILDEIADEYQGKLTVAKLNIDQNPGTAPKYG
    #  IRGIPTLLLFKNGEVAATKVGALSKGQLKEFLDANLA"
    num_in_asym = forms.IntegerField(
                                  label="Number of Molecules in ASU",
                                  required=False)  # "2"
    space_group = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        label="Space Groups you wish to use", required=False)
    # ["P6","P61"]
    sg_all = forms.BooleanField(label="SG-alternative All", required=False,
                                help_text="Let Phaser determine point " +
                                "group and try all space groups of that " +
                                "point group in addition to space groups " +
                                "selected above",
                                initial=False)
    packing = forms.IntegerField(initial=10, label="Packing cutoff")  # "10"
    ensemble_number = forms.IntegerField(
        label="Number of copies to search for", required=False)
    # rmsd = forms.CharField(max_length=20)  # "1.0"

    def __init__(self,
                 f_choices,
                 sigf_choices,
                 sg_num,
                 *args, **kwargs):
        """
        A custom initialiser which translates between spacegroup numbers
        and names, and sets up choices for F and SIGF columns.
        :param f_choices: list of choices for the F column
            as taken from MTZ parser.
        :type f_choices: list of strings
        :param sigf_choices: list of choices for the SIGF column
            as taken from MTZ parser.
        :type sigf_choices: list of strings
        :param sg_num: space group number taken from the MTZ parser
        :type sg_num: integer
        """
        super(ParamForm, self).__init__(*args, **kwargs)
        self.fields['f_value'].choices = f_choices
        self.fields['sigf_value'].choices = sigf_choices
        sgroups = utils.getGroupNumbersFromNumber(sg_num)
        sg_choices = [(sg, utils.sgNumNameTrans(number=sg))
                      for sg in sgroups]
        self.fields['space_group'].choices = sg_choices

    def clean(self):
        """
        A custom clean function that translates sequence information to
        molecular weight.
        """
        logger.debug("starting to clean MRparam form")
        cleaned_data = self.cleaned_data
        mol_weight = cleaned_data.get("mol_weight")

        if not mol_weight:
            sequence = cleaned_data.get("sequence")
            if sequence:
                mol_weight = utils.calcMW(sequence)
                cleaned_data["mol_weight"] = mol_weight
            else:
                raise forms.ValidationError("Please enter either a " +
                    "number for the molecular weight or an amino acid " +
                                            "sequence for your input data.")
        logger.debug(repr(self._errors))
        logger.debug("ending to clean MRparam form")
        return cleaned_data


class RmsdForm(forms.Form):
    """
    RMSD entry :class:`django.forms.Form` subclass
    :attribute rmsd: RMSD float field. min=0.8, max=2.6
    """
    rmsd = forms.FloatField(min_value=0.8, max_value=2.6, required=False)


class selectDSForm(forms.Form):
    """
    Dataset selection form.
    :attribute dataset: Dataset selection
    """
    dataset = forms.ChoiceField()

    def __init__(self, choices):
        """
        custom init for dynamic choices
        :param choices: choices for datasets
        :type choices: list of integer/dataset ids
        """
        super(selectDSForm, self).__init__()
        self.fields['dataset'].choices = choices


class DatasetDescriptionForm(forms.Form):
    """
    Form to set a description for a new dataset
    :attribute description: description string
    """
    description = forms.CharField(widget=forms.TextInput(attrs={'size': '40'}))
