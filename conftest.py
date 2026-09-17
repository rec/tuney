import os
from tempfile import TemporaryDirectory


_test_home = TemporaryDirectory(prefix='tuney-tests-')
os.environ['HOME'] = _test_home.name
os.environ['XDG_CONFIG_HOME'] = _test_home.name
os.environ['XDG_STATE_HOME'] = _test_home.name
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest_plugins = ['reccy.pytest_plugin']
