"""Standalone Construction Site Safety AI package.

Consolidates the former ``inference-service`` and ``video-service`` into a single
importable library. It is driven by the backend's multiprocessing camera
workers (one process per active camera) rather than running as an always-on
microservice.

Sub-packages
------------
- ``detection`` : YOLOv8 person + helmet detection
- ``tracking``  : ByteTrack worker-id assignment and alert cooldown
- ``zones``     : safety line configuration, helmet association, line crossing
- ``pipelines`` : the end-to-end :class:`SafetyPipeline`
"""

__version__ = "2.0.0"
