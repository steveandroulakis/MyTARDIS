"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase

class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.failUnlessEqual(1 + 1, 2)


import utils

class ExtractMetaDataFromMTZFileTestCase(TestCase):
    def testExtractMetaDataFromMTZFile(self):
        testfilepath = "apps/mrtardis/testfiles/2H74_structure_factors.mtz"
        expectedOutput = [
            'VERS MTZ:V1.1                                                                   ',
            'TITLE [No title given]                                                          ', 
            'NCOL        6        10218        0                                             ',
            'CELL   103.5000  103.5000   41.7800   90.0000   90.0000  120.0000               ',
            'SORT    1   2   3   0   0                                                       ', 
            "SYMINF   6  6 P   169                 'P 61'   PG6                              ", 
            'SYMM X,  Y,  Z                                                                  ', 
            'SYMM X-Y,  X,  Z+1/6                                                            ', 
            'SYMM -Y,  X-Y,  Z+1/3                                                           ', 
            'SYMM -X,  -Y,  Z+1/2                                                            ',
            'SYMM -X+Y,  -X,  Z+2/3                                                          ', 
            'SYMM Y,  -X+Y,  Z+5/6                                                           ', 
            'RESO 0.000124             0.173605                                              ', 
            'VALM NAN                                                                        ', 
            'COLUMN H                              H            0.0000           36.0000    0', 
            'COLUMN K                              H            0.0000           37.0000    0', 
            'COLUMN L                              H            0.0000           17.0000    0', 
            'COLUMN FREE                           I            0.0000            9.0000    1', 
            'COLUMN FP                             F            1.7000         1178.5000    1', 
            'COLUMN SIGFP                          Q            0.6000           21.5000    1', 
            'NDIF        2                                                                   ', 
            'PROJECT       0 HKL_base                                                        ', 
            'CRYSTAL       0 HKL_base                                                        ', 
            'DATASET       0 HKL_base                                                        ', 
            'DCELL         0   103.5000  103.5000   41.7800   90.0000   90.0000  120.0000    ', 
            'DWAVEL        0    0.00000                                                      ', 
            'PROJECT       1 h74                                                             ',
            'CRYSTAL       1 h74                                                             ', 
            'DATASET       1 h74                                                             ', 
            'DCELL         1   103.5000  103.5000   41.7800   90.0000   90.0000  120.0000    ', 
            'DWAVEL        1    0.00000                                                      ',
            'END                                                                             ', 
            'MTZHIST   7                                                                     ', 
            'From MTZUTILS 11/ 3/2008 16:29:10 after history:                                ',
            'From FREERFLAG 11/ 3/2008 16:29:09 with fraction  .100                          ', 
            'From cif2mtz 11/ 3/2008 16:29:05                                                ', 
            'data from CAD on 11/ 3/08                                                       ', 
            'From FREERFLAG 11/ 3/2008 16:29:09 with fraction  .100                          ', 
            'From cif2mtz 11/ 3/2008 16:29:05                                                ', 
            'data from CAD on 11/ 3/08                                                       ', 
            'MTZENDOFHEADERS'
            ]
        realoutput = utils.extractMetaDataFromMTZFile(testfilepath)
        self.assertEqual(realoutput,expectedOutput,"MTZ parser dysfunctional")


class SpacegroupNumberNameTranslationTestCase(TestCase):
    def testspacegroupNumberNameTranslation(self):
        self.assertEqual(utils.spacegroupNumberNameTranslation(number=1), 
                         "P1", "numbers don't translate")
        self.assertEqual(utils.spacegroupNumberNameTranslation(name="P213"), 
                         198, "strings don't translate")


class CalcMWTestCase(TestCase):
    def testCalcMW(self):
        testSequence = "SEKIIHLTDDSFDTDVLKADGAILVDFWAEWCGPCKMIAPILDEIADEYQGKL\
TVAKLNIDQNPGTAPKYGIRGIPTLLLFKNGEVAATKVGALSKGQLKEFLDANLA"
        self.assertAlmostEqual(utils.calcMW(testSequence), 11671.4421, 4,
                               "Molecular weights are calculated wrongly")


__test__ = {"doctest": """
Another way to test that 1 + 1 is equal to 2.

>>> 1 + 1 == 2
True
"""}

