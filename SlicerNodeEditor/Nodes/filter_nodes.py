"""Image filter nodes: threshold, smooth, etc."""

import slicer
import sitkUtils
import SimpleITK as sitk
from NodeGraph.node import SlicerBaseNode


class ThresholdNode(SlicerBaseNode):
    __identifier__ = "slicer.filters"
    NODE_NAME = "Threshold"
    NODE_COLOR = (100, 130, 80)

    INPUT_PORTS = [("volume_in", "Volume")]
    OUTPUT_PORTS = [("volume_out", "Volume")]

    def __init__(self):
        super().__init__()
        self.add_float_input("lower", "Lower", value=100.0)
        self.add_float_input("upper", "Upper", value=500.0)

    def execute(self, inputs: dict) -> dict:
        node = inputs.get("volume_in")
        if node is None:
            raise ValueError("Threshold: no input volume connected.")

        lower = self.get_property("lower")
        upper = self.get_property("upper")

        image = sitkUtils.PullVolumeFromSlicer(node)
        result = sitk.BinaryThreshold(image, lowerThreshold=lower, upperThreshold=upper)

        output_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        output_node.SetName(f"{node.GetName()}_threshold")
        sitkUtils.PushVolumeToSlicer(result, output_node)
        return {"volume_out": output_node}


class GaussianSmoothNode(SlicerBaseNode):
    __identifier__ = "slicer.filters"
    NODE_NAME = "Gaussian Smooth"
    NODE_COLOR = (100, 130, 80)

    INPUT_PORTS = [("volume_in", "Volume")]
    OUTPUT_PORTS = [("volume_out", "Volume")]

    def __init__(self):
        super().__init__()
        self.add_float_input("sigma", "Sigma (mm)", value=1.0)

    def execute(self, inputs: dict) -> dict:
        node = inputs.get("volume_in")
        if node is None:
            raise ValueError("Gaussian Smooth: no input volume connected.")

        sigma = self.get_property("sigma")

        image = sitkUtils.PullVolumeFromSlicer(node)
        result = sitk.SmoothingRecursiveGaussian(image, sigma=sigma)

        output_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        output_node.SetName(f"{node.GetName()}_smoothed")
        sitkUtils.PushVolumeToSlicer(result, output_node)
        return {"volume_out": output_node}
