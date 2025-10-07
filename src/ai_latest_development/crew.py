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
from .tools.report_synthesis_tool import ReportSynthesisTool
from .tools.mongodb_schema_tool import MongoDBSchemaTool
from .tools.mongodb_compliance_tool import MongoDBComplianceTool
from .tools.llm_html_generator import LLMHTMLGeneratorTool

load_dotenv()


@CrewBase
class AiLatestDevelopment():
    """
    MongoDB Atlas AI Ops Multi-Agent System using CrewAI
    
    This class orchestrates a 5-agent system for comprehensive MongoDB Atlas analysis:
    - PerformanceAgent: Analyzes performance metrics, indexes, and slow queries
    - SecurityAgent: Audits security config and scans for compliance violations
    - CostAgent: Identifies cost optimization opportunities
    - SchemaAgent: Analyzes data models and provides schema recommendations
    - ReportSynthesizer: Consolidates findings and calculates health scores
    - HTMLGeneratorAgent: Creates interactive HTML reports with visualizations
    
    The agents run sequentially, each appending to a shared report.md file,
    enabling downstream agents to access upstream findings.
    
    Attributes:
        agents (List[BaseAgent]): List of all agent instances
        tasks (List[Task]): List of all task instances in execution order
    """

    agents: List[BaseAgent]
    tasks: List[Task]

    @before_kickoff
    def initialize_report(self, inputs):
        """
        Initialize the shared report.md file before crew execution starts.
        
        This callback runs before any agents execute, creating a fresh report
        with header information. Each agent will append its findings to this file.
        
        Args:
            inputs (dict): Input parameters passed to crew.kickoff()
            
        Returns:
            dict: Unmodified inputs for downstream tasks
            
        Side Effects:
            - Creates/overwrites report.md in the current working directory
            - Writes report header with timestamp and project ID
        """
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
            tools=[AtlasSecurityTool(), MongoDBComplianceTool()],
            verbose=True
        )

    @agent
    def cost_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['cost_agent'], # type: ignore[index]
            tools=[AtlasCostTool()],
            verbose=True
        )

    @agent
    def report_synthesizer(self) -> Agent:
        return Agent(
            config=self.agents_config['report_synthesizer'], # type: ignore[index]
            tools=[ReportSynthesisTool()],
            verbose=True
        )

    @agent
    def schema_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['schema_agent'], # type: ignore[index]
            tools=[MongoDBSchemaTool()],
            verbose=True
        )

    @agent
    def html_generator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['html_generator_agent'], # type: ignore[index]
            tools=[LLMHTMLGeneratorTool()],
            verbose=True,
            allow_delegation=False
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    
    def _append_to_report(self, output, section_title):
        """
        Append a task's output to the shared report.md file.
        
        This callback function is invoked by CrewAI after each task completes,
        enabling incremental report building where each agent adds its section.
        
        Args:
            output: TaskOutput object containing the agent's analysis
            section_title (str): Formatted section header (e.g., "⚡ Performance Analysis")
            
        Side Effects:
            - Appends section to report.md (does not overwrite)
            - Adds markdown formatting (## header, horizontal rule)
            - Preserves all previous sections from upstream agents
        """
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

    @task
    def schema_task(self) -> Task:
        return Task(
            config=self.tasks_config['schema_task'], # type: ignore[index]
            callback=lambda output: self._append_to_report(output, "📐 MongoDB Schema Analysis & Modeling Recommendations")
        )

    @task
    def synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['synthesis_task'], # type: ignore[index]
            context=[self.performance_task(), self.security_task(), self.cost_task(), self.schema_task()],
            callback=lambda output: self._append_to_report(output, "📊 Executive Summary & Health Assessment")
        )

    @task
    def html_generation_task(self) -> Task:
        return Task(
            config=self.tasks_config['html_generation_task'], # type: ignore[index]
            context=[self.synthesis_task()],
            callback=lambda output: self._save_html_report(output)
        )

    def _save_html_report(self, output):
        """
        Extract and save the LLM-generated HTML report from agent output.
        
        This callback processes the HTMLGeneratorAgent's output, which should
        contain complete HTML markup with embedded CSS and JavaScript.
        
        The function:
        1. Extracts HTML content from agent response
        2. Validates HTML structure (<!DOCTYPE html> to </html>)
        3. Saves to mongodb_atlas_report.html
        4. Displays success message with file path
        
        Args:
            output: TaskOutput object containing HTML markup in raw field
            
        Side Effects:
            - Creates mongodb_atlas_report.html in current directory
            - Prints success/error message to console
            
        Error Handling:
            - Gracefully handles malformed HTML
            - Prints diagnostic info if save fails
        """
        try:
            html_content = str(output.raw)
            
            # Extract HTML from the output (agent might wrap it in explanatory text)
            if '<!DOCTYPE html>' in html_content:
                start_idx = html_content.index('<!DOCTYPE html>')
                end_idx = html_content.rindex('</html>') + 7
                html_content = html_content[start_idx:end_idx]
            
            # Save HTML file with UTF-8 encoding for international characters
            with open('mongodb_atlas_report.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Display success message with file details
            abs_path = os.path.abspath('mongodb_atlas_report.html')
            file_size = os.path.getsize('mongodb_atlas_report.html')
            
            print("\n" + "="*60)
            print("✅ HTML REPORT GENERATED SUCCESSFULLY!")
            print("="*60)
            print(f"📄 File: {abs_path}")
            print(f"📏 Size: {round(file_size / 1024, 2)} KB")
            print(f"🌐 Open in browser: file://{abs_path}")
            print("\n💡 Tip: Use 'Print to PDF' in your browser to convert to PDF")
            print("="*60)
            
        except Exception as e:
            print(f"\n⚠️  Error saving HTML report: {str(e)}")
            print("   The agent's response might not contain valid HTML")
            print(f"   Raw output length: {len(str(output.raw))} characters")

    @crew
    def crew(self) -> Crew:
        """Creates the AiLatestDevelopment crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
