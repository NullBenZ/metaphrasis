import tempfile
import unittest
from pathlib import Path
from metagraph.api_validation import validate_source
class ApiValidationCases(unittest.TestCase):
    def test_only_indexed_devito_names_pass(self):
        allowed={'Grid','TimeFunction','Eq','Operator','forward'}
        source='from devito import Grid, TimeFunction, Eq, Operator\ngrid=Grid(shape=(8,))\nu=TimeFunction(name="u",grid=grid)\neq=Eq(u.forward,u)\nOperator(eq)\n'
        self.assertEqual(validate_source(source,allowed),[])
        self.assertTrue(any('NotIndexed' in e for e in validate_source(source.replace('Grid','NotIndexed'),allowed)))
    def test_devito_object_attributes_are_checked(self):
        result=validate_source('from devito import TimeFunction\nu=TimeFunction(name="u",grid=None)\nx=u.backward\n',{'TimeFunction'})
        self.assertTrue(any('backward' in e for e in result))
if __name__=='__main__':unittest.main()
