"""
Runs one test script inside Slicer and exits.

Started by tests/run.sh as Slicer's --python-script.
Reads NODE_EDITOR_TEST (path of the script to run) and NODE_EDITOR_OUT (path of the log file) from the environment.
The script runs with `slicer`, `editor` (the Node Editor module widget) and the helpers from tests/graph_helpers.py in its namespace.
The log ends with a line "RESULT: PASS" or "RESULT: FAIL".
"""

import os
import sys
import traceback

import slicer

_test_path = os.environ['NODE_EDITOR_TEST']
_out_path = os.environ['NODE_EDITOR_OUT']
_log = open(_out_path, 'w', encoding='utf-8')


class _Tee:
    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        _log.write(text)
        _log.flush()
        try:
            self._stream.write(text)
        except Exception:
            pass

    def flush(self):
        _log.flush()


sys.stdout = _Tee(sys.stdout)
sys.stderr = _Tee(sys.stderr)

_ok = False
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    slicer.util.mainWindow().showMaximized()
    slicer.util.selectModule('SlicerNodeEditor')
    slicer.app.processEvents()
    editor = slicer.modules.SlicerNodeEditorWidget
    import graph_helpers
    namespace = {'__name__': '__main__', '__file__': _test_path,
                 'slicer': slicer, 'editor': editor}
    namespace.update({k: getattr(graph_helpers, k)
                      for k in graph_helpers.__all__})
    with open(_test_path, encoding='utf-8') as f:
        code = compile(f.read(), _test_path, 'exec')
    exec(code, namespace)
    _ok = True
except BaseException:
    traceback.print_exc()

print("RESULT: PASS" if _ok else "RESULT: FAIL")
_log.flush()
if os.environ.get('NODE_EDITOR_KEEP_OPEN', '') in ('', '0'):
    slicer.util.exit(0 if _ok else 1)
