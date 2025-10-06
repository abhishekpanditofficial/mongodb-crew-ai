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
        "Fetches MongoDB Atlas clusters and process performance measurements (CPU, IOPS, network, ops), "
        "Performance Advisor index suggestions, slow query logs, and index efficiency analysis. "
        "Returns suggested indexes with field names, slow queries with execution times, and scan ratios."
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
        performance_insights: Dict[str, Any] = {}

        for process in processes.get("results", []):
            hostname = process.get("hostname")
            port = process.get("port")
            if not hostname or not port:
                continue

            process_key = f"{hostname}:{port}"

            # Fetch standard performance metrics
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
                    "OPCOUNTER_QUERY",
                    "OPCOUNTER_INSERT",
                    "OPCOUNTER_UPDATE",
                    "OPCOUNTER_DELETE",
                    "QUERY_EXECUTOR_SCANNED",
                    "QUERY_EXECUTOR_SCANNED_OBJECTS",
                    "CONNECTIONS",
                    "CURSORS_TOTAL_OPEN",
                ],
            }

            try:
                res = requests.get(
                    metrics_url, auth=auth, headers=headers, params=params, timeout=60
                )
                res.raise_for_status()
                metrics_per_process[process_key] = res.json()
            except requests.RequestException as e:
                metrics_per_process[process_key] = {"error": str(e)}

            # Fetch performance advisor suggestions (index recommendations)
            try:
                advisor_url = (
                    f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/"
                    f"processes/{hostname}:{port}/performanceAdvisor/suggestedIndexes"
                )
                advisor_resp = requests.get(advisor_url, auth=auth, headers=headers, timeout=60)
                if advisor_resp.status_code == 200:
                    performance_insights[process_key] = {
                        "suggested_indexes": advisor_resp.json()
                    }
                else:
                    performance_insights[process_key] = {
                        "suggested_indexes": {"note": "Performance Advisor data not available or requires M10+ cluster"}
                    }
            except requests.RequestException:
                performance_insights[process_key] = {
                    "suggested_indexes": {"error": "Unable to fetch Performance Advisor data"}
                }

            # Fetch slow query logs (requires M10+ and profiling enabled)
            try:
                slow_query_url = (
                    f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/"
                    f"processes/{hostname}:{port}/performanceAdvisor/slowQueryLogs"
                )
                slow_query_resp = requests.get(slow_query_url, auth=auth, headers=headers, timeout=60)
                if slow_query_resp.status_code == 200:
                    slow_queries = slow_query_resp.json()
                    performance_insights[process_key]["slow_queries"] = slow_queries
                else:
                    performance_insights[process_key]["slow_queries"] = {
                        "note": "Slow query logs not available. Enable profiling on cluster."
                    }
            except requests.RequestException:
                performance_insights[process_key]["slow_queries"] = {
                    "error": "Unable to fetch slow query logs"
                }

        # Analyze index efficiency from metrics
        index_analysis = self._analyze_index_efficiency(metrics_per_process)

        return {
            "clusters": clusters,
            "processes": processes,
            "metrics": metrics_per_process,
            "performance_insights": performance_insights,
            "index_analysis": index_analysis,
            "window": {"start": start, "end": end, "hours": hours},
        }

    def _analyze_index_efficiency(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze index efficiency from query metrics"""
        analysis = {}
        
        for process_key, metric_data in metrics.items():
            if "error" in metric_data:
                continue
            
            measurements = metric_data.get("measurements", [])
            
            scanned_objects = None
            scanned_docs = None
            
            for m in measurements:
                if m["name"] == "QUERY_EXECUTOR_SCANNED_OBJECTS":
                    data_points = [dp["value"] for dp in m["dataPoints"] if dp["value"] is not None]
                    if data_points:
                        scanned_objects = sum(data_points) / len(data_points)
                
                if m["name"] == "QUERY_EXECUTOR_SCANNED":
                    data_points = [dp["value"] for dp in m["dataPoints"] if dp["value"] is not None]
                    if data_points:
                        scanned_docs = sum(data_points) / len(data_points)
            
            # Calculate index efficiency ratio
            if scanned_objects and scanned_docs:
                ratio = scanned_objects / scanned_docs if scanned_docs > 0 else 0
                
                analysis[process_key] = {
                    "avg_scanned_objects": round(scanned_objects, 2),
                    "avg_scanned_docs": round(scanned_docs, 2),
                    "scan_ratio": round(ratio, 2),
                    "efficiency": "Poor - Missing indexes likely" if ratio > 10 else 
                                 "Fair - Review query patterns" if ratio > 3 else 
                                 "Good - Indexes being used effectively"
                }
        
        return analysis


