"""Corners and junctions as graph entities shared by incident interfaces."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .contracts import CornerNode, GeometryPrimitive, InterfaceEdge
from .shape_models import primitive_points


def build_corner_graph(interfaces: tuple[InterfaceEdge, ...], *, merge_radius: float = 0.55
                       ) -> tuple[tuple[InterfaceEdge, ...], tuple[CornerNode, ...]]:
    endpoint_rows: list[tuple[np.ndarray, str, float]] = []
    for edge in interfaces:
        if not edge.geometry:
            continue
        for primitive in (edge.geometry[0], edge.geometry[-1]):
            points = primitive_points(primitive, 16)
            if len(points):
                confidence = float(np.mean(edge.confidence_profile)) if edge.confidence_profile else 1.0
                endpoint_rows.append((points[0] if primitive is edge.geometry[0] else points[-1], edge.id, confidence))
    clusters: list[list[tuple[np.ndarray, str, float]]] = []
    for row in endpoint_rows:
        target = None
        for cluster in clusters:
            center = np.mean([item[0] for item in cluster], axis=0)
            if np.linalg.norm(row[0] - center) <= merge_radius:
                target = cluster
                break
        if target is None:
            clusters.append([row])
        else:
            target.append(row)
    corners: list[CornerNode] = []
    interface_to_corners: dict[str, list[str]] = {edge.id: [] for edge in interfaces}
    for index, cluster in enumerate(clusters):
        if not cluster:
            continue
        weights = np.asarray([max(1e-3, item[2]) for item in cluster])
        points = np.asarray([item[0] for item in cluster])
        center = np.average(points, axis=0, weights=weights)
        delta = points - center
        covariance = np.cov(delta.T, aweights=weights) if len(points) > 1 else np.eye(2) * 0.04
        incident = tuple(sorted(set(item[1] for item in cluster)))
        role = "junction" if len(incident) >= 3 else ("corner" if len(incident) == 2 else "endpoint")
        continuity = "C0" if role in {"corner", "junction"} else "G1-unknown"
        corner_id = f"corner-{index}"
        corners.append(CornerNode(
            id=corner_id, position=(float(center[0]), float(center[1])),
            covariance=(float(covariance[0, 0]), float(covariance[0, 1]), float(covariance[1, 1])),
            incident_interfaces=incident, continuity=continuity, role=role,
            confidence=float(np.clip(np.mean(weights), 0.0, 1.0)),
        ))
        for edge_id in incident:
            interface_to_corners[edge_id].append(corner_id)
    updated = tuple(replace(edge, corner_nodes=tuple(interface_to_corners[edge.id]))
                    for edge in interfaces)
    return updated, tuple(corners)
