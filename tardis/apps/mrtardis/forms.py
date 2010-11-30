from django import forms


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
    f_value = forms.CharField(max_length=20)  # "FP"
    sigf_value = forms.CharField(max_length=20)  # "SIGFP"
    space_group = None  # ["P6","P61"]
    mol_weight = forms.CharField(max_length=20)  # "11807"
    sequence = forms.CharField(max_length=5000)
    # "SEKIIHLTDDSFDTDVLKADGAILVDFWAEWCGPCKMIAPILDEIADEYQGKLTVAKLNIDQNPGTAPKYG
    #  IRGIPTLLLFKNGEVAATKVGALSKGQLKEFLDANLA"
    num_in_asym = forms.CharField(max_length=20)  # "2"
    rmsd = forms.CharField(max_length=20)  # "1.0"
    ensemble_number = forms.CharField(max_length=20)  # "1"
    packing = forms.CharField(max_length=20)  # "10"
