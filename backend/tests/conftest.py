import os
import tempfile
os.environ['STORAGE_DIR'] = tempfile.mkdtemp(prefix='liveclip-tests-')
