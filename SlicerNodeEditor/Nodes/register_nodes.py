"""Registration nodes."""

import slicer
from NodeGraph.node import SlicerBaseNode


class RegistrationNode(SlicerBaseNode):
    __identifier__ = "slicer.register"
    NODE_NAME = "Registration"
    NODE_COLOR = (130, 110, 60)

    INPUT_PORTS = [
        ("fixed_volume", "Fixed Volume"),
        ("moving_volume", "Moving Volume"),
    ]
    OUTPUT_PORTS = [
        ("registered_volume", "Registered Volume"),
        ("transform_out", "Transform"),
    ]

    def __init__(self):
        super().__init__()
        self.add_combo_menu("type", "Registration Type", items=["Rigid", "Affine", "BSpline"])

    def execute(self, inputs: dict) -> dict:
        fixed = inputs.get("fixed_volume")
        moving = inputs.get("moving_volume")
        if fixed is None or moving is None:
            raise ValueError("Registration: both Fixed and Moving volumes must be connected.")

        reg_type = self.get_property("type")

        transform_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode")
        transform_node.SetName(f"{moving.GetName()}_to_{fixed.GetName()}_xfm")

        output_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        output_node.SetName(f"{moving.GetName()}_registered")

        params = {
            "fixedVolume": fixed,
            "movingVolume": moving,
            "outputTransform": transform_node,
            "outputVolume": output_node,
            "transformType": reg_type,
            "initializeTransformMode": "useGeometryAlign",
        }
        slicer.cli.run(
            slicer.modules.brainsfit, None, params, wait_for_completion=True
        )

        return {
            "registered_volume": output_node,
            "transform_out": transform_node,
        }
