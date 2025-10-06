from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Type

import requests
from requests.auth import HTTPDigestAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AtlasCostInput(BaseModel):
    project_id: Optional[str] = Field(
        default=None, description="MongoDB Atlas Project ID; falls back to env"
    )
    hours: int = Field(default=24, description="Hours of metrics to analyze for utilization")


class AtlasCostTool(BaseTool):
    name: str = "atlas_cost_tool"
    description: str = (
        "Fetches MongoDB Atlas cost-related data: cluster configurations (instance size, disk, "
        "autoscaling), backup settings, utilization metrics, and data transfer patterns to "
        "identify cost optimization opportunities."
    )
    args_schema: Type[BaseModel] = AtlasCostInput

    def _run(self, project_id: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        public_key = os.getenv("MONGODB_ATLAS_PUBLIC_KEY")
        private_key = os.getenv("MONGODB_ATLAS_PRIVATE_KEY")
        resolved_project_id = project_id or os.getenv("MONGODB_ATLAS_PROJECT_ID")

        if not all([public_key, private_key, resolved_project_id]):
            return {
                "error": "Missing MongoDB Atlas credentials. Set MONGODB_ATLAS_PUBLIC_KEY, "
                "MONGODB_ATLAS_PRIVATE_KEY, MONGODB_ATLAS_PROJECT_ID."
            }

        auth = HTTPDigestAuth(public_key, private_key)
        headers = {"Accept": "application/json"}

        result = {
            "project_id": resolved_project_id,
            "analysis_window_hours": hours,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # 1️⃣ Get Clusters with full configuration
        try:
            cluster_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/clusters"
            cluster_resp = requests.get(cluster_url, auth=auth, headers=headers, timeout=60)
            cluster_resp.raise_for_status()
            result["clusters"] = cluster_resp.json()
        except requests.RequestException as e:
            result["clusters"] = {"error": str(e)}

        # 2️⃣ Get Processes (for utilization metrics)
        try:
            processes_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/processes"
            processes_resp = requests.get(processes_url, auth=auth, headers=headers, timeout=60)
            processes_resp.raise_for_status()
            result["processes"] = processes_resp.json()
        except requests.RequestException as e:
            result["processes"] = {"error": str(e)}

        # 3️⃣ Get Process Metrics for utilization analysis
        now = datetime.utcnow()
        start = (now - timedelta(hours=hours)).isoformat() + "Z"
        end = now.isoformat() + "Z"

        processes_data = result.get("processes", {})
        if "results" in processes_data:
            result["utilization_metrics"] = {}
            
            for process in processes_data["results"]:
                hostname = process.get("hostname")
                port = process.get("port")
                if not hostname or not port:
                    continue

                process_key = f"{hostname}:{port}"
                
                # Fetch key cost-relevant metrics
                metrics_url = (
                    f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/processes/"
                    f"{hostname}:{port}/measurements"
                )
                
                params = {
                    "granularity": "PT1H",  # 1-hour granularity for 24h window
                    "period": f"PT{hours}H",
                    "start": start,
                    "end": end,
                    "m": [
                        "SYSTEM_CPU_USER",
                        "SYSTEM_CPU_STEAL",
                        "SYSTEM_MEMORY_AVAILABLE",
                        "CONNECTIONS",
                        "OPCOUNTER_CMD",
                        "OPCOUNTER_QUERY",
                        "OPCOUNTER_INSERT",
                        "OPCOUNTER_UPDATE",
                        "OPCOUNTER_DELETE",
                        "SYSTEM_NETWORK_IN",
                        "SYSTEM_NETWORK_OUT",
                        "DISK_PARTITION_UTILIZATION",
                    ],
                }

                try:
                    metrics_resp = requests.get(
                        metrics_url, auth=auth, headers=headers, params=params, timeout=60
                    )
                    metrics_resp.raise_for_status()
                    result["utilization_metrics"][process_key] = metrics_resp.json()
                except requests.RequestException as e:
                    result["utilization_metrics"][process_key] = {"error": str(e)}

        # 4️⃣ Get Backup Configuration
        try:
            # Note: Backup snapshots require cluster-specific endpoints
            result["backup_config"] = {}
            clusters_data = result.get("clusters", {})
            if "results" in clusters_data:
                for cluster in clusters_data["results"]:
                    cluster_name = cluster["name"]
                    result["backup_config"][cluster_name] = {
                        "backupEnabled": cluster.get("backupEnabled", False),
                        "providerBackupEnabled": cluster.get("providerBackupEnabled", False),
                        "pitEnabled": cluster.get("pitEnabled", False),
                    }
        except Exception as e:
            result["backup_config"] = {"error": str(e)}

        # 5️⃣ Get Disk Auto-Scaling and Current Disk Usage
        # Already included in cluster config, but we'll extract it for easier analysis
        result["disk_analysis"] = {}
        clusters_data = result.get("clusters", {})
        if "results" in clusters_data:
            for cluster in clusters_data["results"]:
                cluster_name = cluster["name"]
                result["disk_analysis"][cluster_name] = {
                    "diskSizeGB": cluster.get("diskSizeGB", 0),
                    "diskGBEnabled": cluster.get("autoScaling", {}).get("diskGBEnabled", False),
                    "diskIOPS": cluster.get("providerSettings", {}).get("diskIOPS", 0),
                    "volumeType": cluster.get("providerSettings", {}).get("volumeType", "STANDARD"),
                }

        # 6️⃣ Calculate cost-relevant configurations
        result["cost_factors"] = {}
        if "results" in clusters_data:
            for cluster in clusters_data["results"]:
                cluster_name = cluster["name"]
                provider_settings = cluster.get("providerSettings", {})
                auto_scaling = cluster.get("autoScaling", {}).get("compute", {})
                
                result["cost_factors"][cluster_name] = {
                    "instanceSize": provider_settings.get("instanceSizeName", "UNKNOWN"),
                    "numShards": cluster.get("numShards", 1),
                    "replicationFactor": cluster.get("replicationFactor", 3),
                    "providerName": provider_settings.get("providerName", "UNKNOWN"),
                    "regionName": provider_settings.get("regionName", "UNKNOWN"),
                    "paused": cluster.get("paused", False),
                    "autoScalingEnabled": auto_scaling.get("enabled", False),
                    "minInstanceSize": auto_scaling.get("minInstanceSize"),
                    "maxInstanceSize": auto_scaling.get("maxInstanceSize"),
                    "clusterType": cluster.get("clusterType", "UNKNOWN"),
                }

        return result

