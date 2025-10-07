#!/usr/bin/env python
"""
Quick test of LLM HTML generation
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ai_latest_development.tools.llm_html_generator import LLMHTMLGeneratorTool

load_dotenv()

def main():
    print("Testing LLM HTML Generator Tool...")
    print("="*60)
    
    tool = LLMHTMLGeneratorTool()
    result = tool._run()
    
    print("\n" + "="*60)
    print("TOOL OUTPUT:")
    print("="*60)
    print(result[:1000])
    print("\n... (truncated)")
    print("="*60)
    print("\n💡 This output will be given to the LLM agent")
    print("   The agent will then generate the complete HTML")

if __name__ == "__main__":
    main()

