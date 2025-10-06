from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff
from dotenv import load_dotenv
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from datetime import datetime
import os
from .tools.atlas_performance_tool import AtlasPerformanceTool
from .tools.atlas_security_tool import AtlasSecurityTool
from .tools.atlas_cost_tool import AtlasCostTool

load_dotenv()


@CrewBase
class AiLatestDevelopment():
    """AiLatestDevelopment crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @before_kickoff
    def initialize_report(self, inputs):
        """Initialize the report file with header before crew starts"""
        report_file = 'report.md'
        with open(report_file, 'w') as f:
            f.write(f"# MongoDB Atlas AI Ops Analysis Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Project ID:** {os.getenv('MONGODB_ATLAS_PROJECT_ID', 'N/A')}\n\n")
            f.write("---\n\n")
        return inputs

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    @agent
    def performance_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['performance_agent'], # type: ignore[index]
            tools=[AtlasPerformanceTool()],
            verbose=True
        )

    @agent
    def security_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['security_agent'], # type: ignore[index]
            tools=[AtlasSecurityTool()],
            verbose=True
        )

    @agent
    def cost_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['cost_agent'], # type: ignore[index]
            tools=[AtlasCostTool()],
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    
    def _append_to_report(self, output, section_title):
        """Helper to append task output to report"""
        with open('report.md', 'a') as f:
            f.write(f"## {section_title}\n\n")
            f.write(str(output.raw) + "\n\n")
            f.write("---\n\n")
    
    @task
    def performance_task(self) -> Task:
        return Task(
            config=self.tasks_config['performance_task'], # type: ignore[index]
            callback=lambda output: self._append_to_report(output, "⚡ Performance Analysis")
        )

    @task
    def security_task(self) -> Task:
        return Task(
            config=self.tasks_config['security_task'], # type: ignore[index]
            callback=lambda output: self._append_to_report(output, "🔒 Security Audit")
        )

    @task
    def cost_task(self) -> Task:
        return Task(
            config=self.tasks_config['cost_task'], # type: ignore[index]
            callback=lambda output: self._append_to_report(output, "💰 Cost Optimization Analysis")
        )

    @crew
    def crew(self) -> Crew:
        """Creates the AiLatestDevelopment crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
