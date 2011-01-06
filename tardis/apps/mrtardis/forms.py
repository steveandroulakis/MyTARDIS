from django import forms
from django.forms.formsets import formset_factory
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
    f_value = forms.ChoiceField(label="F column")
    # "SIGFP" same functionality as f_value
    sigf_value = forms.ChoiceField(label="SIGF column")
    mol_weight = forms.DecimalField(
                                 label="Molecular weight")  # "11807"
    # alternative to MW, calculate MW from sequence
    sequence = forms.CharField(max_length=2000,
                               label="Protein sequence, if MW is not known",
                               widget=forms.Textarea(attrs={'cols': 40,
                                                            'rows': 4}))
    # "SEKIIHLTDDSFDTDVLKADGAILVDFWAEWCGPCKMIAPILDEIADEYQGKLTVAKLNIDQNPGTAPKYG
    #  IRGIPTLLLFKNGEVAATKVGALSKGQLKEFLDANLA"
    num_in_asym = forms.IntegerField(
                                  label="Number of Molecules in ASU")  # "2"
    space_group = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        label="Space Groups you wish to use")
    # ["P6","P61"]
    sg_all = forms.BooleanField(label="SG-alternative All",
                                help_text="Let Phaser determine point " +
                                "group and try all space groups of that " +
                                "point group in addition to space groups " +
                                "selected above",
                                initial=False)
    packing = forms.IntegerField(initial=10, label="Packing")  # "10"
    ensemble_number = forms.IntegerField(
        label="Number of copies to search for")
    # rmsd = forms.CharField(max_length=20)  # "1.0"

    def __init__(self, f_choices, sigf_choices, sg_num, *args, **kwargs):
        super(MRForm, self).__init__(*args, **kwargs)
        self.fields['f_value'].choices = f_choices
        self.fields['sigf_value'].choices = sigf_choices
        sgroups = utils.getGroupNumbersFromNumber(sg_num)
        sg_choices = []
        for sg in sgroups:
            sg_choices.append((sg, utils.sgNumNameTrans(number=sg)))
        self.fields['space_group'].choices = sg_choices
        self.fields['space_group'].initial = \
            (sg_num, utils.sgNumNameTrans(number=sg_num))

    def clean(self):
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
        return cleaned_data


class RmsdForm(forms.Form):
    rmsd = forms.DecimalField(min_value=0.8, max_value=2.6)

#RmsdFormset = formset_factory(RmsdForm)
#formset = RmsdFormset()
#for form in formset.forms:
