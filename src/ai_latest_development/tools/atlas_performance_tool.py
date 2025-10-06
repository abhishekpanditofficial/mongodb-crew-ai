from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

import requests
from requests.auth import HTTPDigestAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AtlasMetricsInput(BaseModel):
    project_id: Optional[str] = Field(
        default=None, description="MongoDB Atlas Project ID; falls back to env"
    )
    hours: int = Field(default=6, description="How many hours back to fetch")


class AtlasPerformanceTool(BaseTool):
    name: str = "atlas_performance_tool"
    description: str = (
        "Fetches MongoDB Atlas clusters and process performance measurements (CPU, IOPS, network, ops)."
    )
    args_schema: Type[BaseModel] = AtlasMetricsInput

    def _run(self, project_id: Optional[str] = None, hours: int = 6) -> Dict[str, Any]:
        public_key = os.getenv("MONGODB_ATLAS_PUBLIC_KEY")
        private_key = os.getenv("MONGODB_ATLAS_PRIVATE_KEY")
        resolved_project_id = project_id or os.getenv("MONGODB_ATLAS_PROJECT_ID")

        if not all([public_key, private_key, resolved_project_id]):
            return {
                "error": "Missing MongoDB Atlas credentials. Set MONGODB_ATLAS_PUBLIC_KEY, MONGODB_ATLAS_PRIVATE_KEY, MONGODB_ATLAS_PROJECT_ID."
            }

        auth = HTTPDigestAuth(public_key, private_key)
        headers = {"Accept": "application/json"}

        clusters_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/clusters"
        clusters_resp = requests.get(clusters_url, auth=auth, headers=headers, timeout=60)
        clusters_resp.raise_for_status()
        clusters = clusters_resp.json()

        processes_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/processes"
        processes_resp = requests.get(processes_url, auth=auth, headers=headers, timeout=60)
        processes_resp.raise_for_status()
        processes = processes_resp.json()

        now = datetime.utcnow()
        start = (now - timedelta(hours=hours)).isoformat() + "Z"
        end = now.isoformat() + "Z"

        metrics_per_process: Dict[str, Any] = {}

        for process in processes.get("results", []):
            hostname = process.get("hostname")
            port = process.get("port")
            if not hostname or not port:
                continue

            metrics_url = (
                f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/processes/"
                f"{hostname}:{port}/measurements"
            )
            params = {
                "granularity": "PT5M",
                "period": f"PT{hours}H",
                "start": start,
                "end": end,
                "m": [
                    "PROCESS_CPU_USER",
                    "DISK_PARTITION_IOPS_TOTAL",
                    "SYSTEM_NETWORK_BYTES_IN",
                    "SYSTEM_NETWORK_BYTES_OUT",
                    "OPCOUNTER_CMD",
                ],
            }

            try:
                res = requests.get(
                    metrics_url, auth=auth, headers=headers, params=params, timeout=60
                )
                res.raise_for_status()
                metrics_per_process[f"{hostname}:{port}"] = res.json()
            except requests.RequestException as e:
                metrics_per_process[f"{hostname}:{port}"] = {"error": str(e)}

        return {
            "clusters": clusters,
            "processes": processes,
            "metrics": metrics_per_process,
            "window": {"start": start, "end": end, "hours": hours},
        }


