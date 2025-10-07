#!/usr/bin/env python
"""
MongoDB Atlas AI Ops Multi-Agent System - Main Entry Point

This module serves as the entry point for the CrewAI multi-agent system.
It initializes and executes the 5-agent workflow for MongoDB Atlas analysis.

Usage:
    Direct execution:
        $ python -m ai_latest_development.main
    
    Via installed script:
        $ run_crew
    
    Programmatic:
        from ai_latest_development.main import run
        run()

Environment Requirements:
    Required environment variables in .env file:
    - MONGODB_ATLAS_PUBLIC_KEY: Atlas API public key
    - MONGODB_ATLAS_PRIVATE_KEY: Atlas API private key
    - MONGODB_ATLAS_PROJECT_ID: Atlas project ID to analyze
    - MONGODB_ATLAS_ORG_ID: Atlas organization ID
    - OPENAI_API_KEY: OpenAI API key for LLM access
    - MONGODB_CONNECTION_STRING: MongoDB connection string (for schema analysis)
    - MONGODB_DATABASE: Database name to analyze

Outputs:
    - report.md: Comprehensive markdown report (3000-5000 words)
    - mongodb_atlas_report.html: Interactive HTML report with charts
    
Agent Execution Order:
    1. PerformanceAgent - Analyzes metrics, indexes, slow queries
    2. SecurityAgent - Audits security and compliance
    3. CostAgent - Identifies cost optimization opportunities
    4. SchemaAgent - Analyzes data models and schemas
    5. ReportSynthesizer - Consolidates findings and calculates health scores
    6. HTMLGeneratorAgent - Creates interactive HTML report

Average Execution Time: 5-15 minutes (depending on cluster size and API responses)
"""
import sys
import warnings
import os
from datetime import datetime

from .crew import AiLatestDevelopment

# Suppress pysbd syntax warnings from CrewAI dependencies
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """
    Execute the MongoDB Atlas AI Ops multi-agent analysis workflow.
    
    This function:
    1. Initializes input parameters for the crew
    2. Instantiates the AiLatestDevelopment crew
    3. Kicks off sequential agent execution
    4. Handles errors gracefully with detailed messages
    
    The crew will:
    - Create report.md with header (via @before_kickoff)
    - Run 6 agents sequentially, each appending to report.md
    - Generate mongodb_atlas_report.html with visualizations
    
    Returns:
        None: Results are written to report.md and mongodb_atlas_report.html
        
    Raises:
        Exception: If crew execution fails due to:
            - Missing environment variables
            - Invalid MongoDB Atlas credentials
            - API rate limits or connectivity issues
            - Invalid MongoDB connection string
            - OpenAI API errors
    
    Example:
        >>> from ai_latest_development.main import run
        >>> run()
        # Executes full analysis and generates reports
    """
    # Input parameters passed to all tasks (available for interpolation)
    inputs = {
        'current_year': str(datetime.now().year)
    }
    
    try:
        # Instantiate crew and execute workflow
        AiLatestDevelopment().crew().kickoff(inputs=inputs)
    except Exception as e:
        # Re-raise with contextual error message
        raise Exception(f"An error occurred while running the crew: {e}")


# Auto-execute when run as script (not when imported)
run()