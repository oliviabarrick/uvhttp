import uvhttp.utils
from nose.tools import *

def test_is_ip():
    assert_equal(uvhttp.utils.is_ip('127.0.0.1'), True)
    assert_equal(uvhttp.utils.is_ip('::1'), True)
    assert_equal(uvhttp.utils.is_ip('example'), False)
    assert_equal(uvhttp.utils.is_ip('256.0.0.0'), False)
