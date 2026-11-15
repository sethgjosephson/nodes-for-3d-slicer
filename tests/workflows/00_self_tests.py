# The module's own self-tests, as Reload & Test runs them.
import SlicerNodeEditor

tester = SlicerNodeEditor.SlicerNodeEditorTest()
tester.runTest()
print("self-tests completed")
