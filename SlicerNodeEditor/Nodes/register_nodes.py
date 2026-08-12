"""Registration nodes."""

import slicer
from .base_node import (SlicerBaseNode, LinkedModuleNode, VOLUME, TRANSFORM,
                         _mark_ephemeral)


class RegistrationNode(SlicerBaseNode):
    NODE_NAME    = "Registration"
    CATEGORY     = "Registration"
    # BRAINSFit runs for minutes; keep it out of the auto-rerun loop.
    AUTO_EXECUTE = False

    INPUT_PORTS  = [
        ("fixed_in",  "Fixed Volume",  VOLUME),
        ("moving_in", "Moving Volume", VOLUME),
    ]
    OUTPUT_PORTS = [
        ("registered_out", "Registered", VOLUME),
        ("transform_out",  "Transform",  TRANSFORM),
    ]

    PROPERTIES = [
        {'name': 'type', 'label': 'Registration Type', 'type': 'enum',
         'default': 'Rigid',
         'items': ['Rigid', 'Affine', 'BSpline']},
        {'name': 'sampling', 'label': 'Sampling %', 'type': 'float',
         'default': 0.2, 'min': 0.01, 'max': 1.0},
        {'name': 'init_mode', 'label': 'Initialisation', 'type': 'enum',
         'default': 'useGeometryAlign',
         'items': ['useGeometryAlign', 'useCenterOfHeadAlign',
                   'useMomentsAlign', 'Off']},
    ]

    def execute(self, inputs):
        fixed  = inputs.get('fixed_in')
        moving = inputs.get('moving_in')
        if fixed is None or moving is None:
            raise ValueError("Registration: both Fixed and Moving volumes must be connected.")

        reg_type  = self.get_property('type')
        sampling  = self.get_property('sampling')
        init_mode = self.get_property('init_mode')

        # Reuse the MRML nodes WE own (passthrough may have written
        # upstream refs into _cache, so read from _owned_outputs).
        xfm = self._owned_outputs.get('transform_out')
        if xfm is None or not slicer.mrmlScene.GetNodeByID(xfm.GetID()):
            xfm = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
            xfm.SetName(f"{moving.GetName()}_to_{fixed.GetName()}_xfm")
            _mark_ephemeral(xfm)
            self._owned_outputs['transform_out'] = xfm

        reg_vol = self._owned_outputs.get('registered_out')
        if reg_vol is None or not slicer.mrmlScene.GetNodeByID(reg_vol.GetID()):
            reg_vol = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
            reg_vol.SetName(f"{moving.GetName()}_registered")
            reg_vol.CreateDefaultDisplayNodes()
            _mark_ephemeral(reg_vol)
            self._owned_outputs['registered_out'] = reg_vol

        params = {
            'fixedVolume':           fixed,
            'movingVolume':          moving,
            'outputTransform':       xfm,
            'outputVolume':          reg_vol,
            'transformType':         reg_type,
            'initializeTransformMode': init_mode,
            'samplingPercentage':    sampling,
        }

        # Cancel any previous in-flight run (e.g. user re-pressed 1
        # before the last registration finished) so we don't end up
        # with two BRAINSFit processes writing to the same nodes.
        prev_cli = getattr(self, '_async_cli_node', None)
        if prev_cli is not None:
            try:
                prev_cli.Cancel()
            except Exception:
                pass

        # Run async.  BRAINSFit can take minutes; with wait_for_completion
        # =False the canvas stays interactive.  Output nodes exist now and
        # are empty / stale until the CLI finishes; downstream observers
        # added by Phase B.1 will see their ModifiedEvent and mark
        # downstream nodes dirty automatically when the data arrives.
        self._async_pending = True
        cli_node = slicer.cli.run(
            slicer.modules.brainsfit, None, params,
            wait_for_completion=False)
        self._async_cli_node = cli_node

        if cli_node is not None:
            # The CLI node itself is a transient MRML node; keep it out
            # of .mrb saves and group it with the rest of the graph's
            # auto-created nodes.
            _mark_ephemeral(cli_node)
            node_item = getattr(self, '_executing_node_item', None)
            cli_node.AddObserver(
                slicer.vtkMRMLCommandLineModuleNode.StatusModifiedEvent,
                lambda caller, event, ni=node_item:
                    self._on_cli_status_changed(caller, ni))

        return {'registered_out': reg_vol, 'transform_out': xfm}

    def _on_cli_status_changed(self, cli_node, node_item):
        """Observer fired whenever the BRAINSFit CLI changes status.
        On terminal statuses, hand off to _notify_async_complete, which
        marks this node clean, dirties downstream (the executor blocked
        descendants while we were pending), and re-cooks the active
        viewer slot."""
        try:
            status = cli_node.GetStatus()
        except Exception:
            return
        terminal = (cli_node.Completed,
                    cli_node.CompletedWithErrors,
                    cli_node.Cancelled)
        if status not in terminal:
            return  # still running
        self._async_cli_node = None

        if status == cli_node.Completed:
            self._notify_async_complete(True)
            return

        if status == cli_node.Cancelled:
            # Superseded by a newer run (cancel-on-rerun) or user cancel:
            # stay dirty, no error badge, just clear the computing dot.
            self._async_pending = False
            if node_item is not None:
                try:
                    node_item.update()
                except Exception:
                    pass
            return

        self._notify_async_complete(
            False, "BRAINSFit completed with errors.")
        try:
            slicer.util.errorDisplay(
                "Registration: BRAINSFit completed with errors. "
                "Check the Error Log for details.")
        except Exception:
            pass

    def route_to_viewer(self):
        node = self._cache.get('registered_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


class ApplyTransformNode(SlicerBaseNode):
    NODE_NAME    = "Apply Transform"
    CATEGORY     = "Registration"

    INPUT_PORTS  = [
        ("volume_in",    "Volume",    VOLUME),
        ("transform_in", "Transform", TRANSFORM),
    ]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'harden', 'label': 'Harden Transform', 'type': 'bool',
         'default': False},
    ]

    def execute(self, inputs):
        vol = inputs.get('volume_in')
        xfm = inputs.get('transform_in')
        if vol is None:
            raise ValueError("Apply Transform: no volume connected.")
        if xfm is None:
            raise ValueError("Apply Transform: no transform connected.")

        # Work on a copy we own. Transforming the upstream volume in
        # place would leak the transform to every other consumer of that
        # volume (any branch off the same source), and harden mode would
        # destructively resample shared data.
        out = self._get_or_create_output('volume_out',
                                         vol.GetName() + '_xformed')
        out.SetName(vol.GetName() + '_xformed')
        out.CopyContent(vol)
        out.SetAndObserveTransformNodeID(xfm.GetID())

        if self.get_property('harden'):
            import slicer
            slicer.vtkSlicerTransformLogic().hardenTransform(out)

        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


# ---------------------------------------------------------------------------
# Transforms — linked to Slicer's "Transforms" module
# ---------------------------------------------------------------------------

class TransformsNode(LinkedModuleNode):
    """View / edit a transform's matrix via Slicer's Transforms module."""

    NODE_NAME     = "Transforms"
    CATEGORY      = "Registration"
    LINKED_MODULE = "Transforms"

    INPUT_PORTS   = [("transform_in",  "Transform", TRANSFORM)]
    OUTPUT_PORTS  = [("transform_out", "Transform", TRANSFORM)]
    INPUT_SETTERS = {'transform_in': ('setMRMLTransformNode', 'setMRMLNode')}
