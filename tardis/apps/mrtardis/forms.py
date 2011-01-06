from django import forms
import tardis.apps.mrtardis.utils as utils


class HPCSetupForm(forms.Form):
    hpc_username = forms.CharField(max_length=20)


class MRFileSelect(forms.Form):
    """
    Form to select dataset to run MR on.
    """
    dataset = forms.ChoiceField()

    def __init__(self, choices):
        super(MRFileSelect, self).__init__()
        self.fields['dataset'].choices = choices


# examples in comments
class MRForm(forms.Form):
    # "FP" single value or array. needs selector
    f_value = forms.ChoiceField(label="F value")
    # "SIGFP" same functionality as f_value
    sigf_value = forms.ChoiceField(label="SIGF value")
    mol_weight = forms.CharField(max_length=20,
                                 label="Molecular weight")  # "11807"
    # alternative to MW, calculate MW from sequence
    sequence = forms.CharField(max_length=2000,
                               label="Protein sequence, if MW is not known")
    # "SEKIIHLTDDSFDTDVLKADGAILVDFWAEWCGPCKMIAPILDEIADEYQGKLTVAKLNIDQNPGTAPKYG
    #  IRGIPTLLLFKNGEVAATKVGALSKGQLKEFLDANLA"
    num_in_asym = forms.CharField(max_length=20,
                                  label="Number of Molecules in ASU")  # "2"
    space_group = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        label="Space Groups you wish to use")
    # ["P6","P61"]
    rmsd = forms.CharField(max_length=20)  # "1.0"
    ensemble_number = forms.CharField(max_length=20)  # "1"
    packing = forms.CharField(max_length=20)  # "10"

    def __init__(self, f_choices, sigf_choices, sg_num):
        super(MRForm, self).__init__()
        self.fields['f_value'].choices = f_choices
        self.fields['sigf_value'].choices = sigf_choices
        sgroups = utils.getGroupNumbersFromNumber(sg_num)
        sg_choices = []
        for sg in sgroups:
            sg_choices.append((sg, utils.sgNumNameTrans(number=sg_num)))
        self.fields['space_group'].choices = sg_choices
        self.fields['space_group'].initial = \
            utils.sgNumNameTrans(number=sg_num)
