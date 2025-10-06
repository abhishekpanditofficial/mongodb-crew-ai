from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from .tools.atlas_performance_tool import AtlasPerformanceTool
from .tools.atlas_security_tool import AtlasSecurityTool
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

load_dotenv()


@CrewBase
class AiLatestDevelopment():
    """AiLatestDevelopment crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

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

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def performance_task(self) -> Task:
        return Task(
            config=self.tasks_config['performance_task'], # type: ignore[index]
            output_file='report.md'
        )

    @task
    def security_task(self) -> Task:
        return Task(
            config=self.tasks_config['security_task'], # type: ignore[index]
            output_file='report.md'
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
