"""Модуль для работы с ArUco метками."""

from .detector import ArucoDetector, CameraManager
from .coordinates import CoordinateSystem

__all__ = ['ArucoDetector', 'CameraManager', 'CoordinateSystem']


