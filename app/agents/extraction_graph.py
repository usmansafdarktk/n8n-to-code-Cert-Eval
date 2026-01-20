
from typing import TypedDict, List, Dict, Any, Optional
import json
from langgraph.graph import StateGraph, END
from loguru import logger

from app.services.certificate_extraction import CertificateExtractionService

# 1. Define State
class ExtractionState(TypedDict):
    # Inputs
    pages: List[Dict[str, Any]]
    bidder_name: str
    certificate_types: List[Dict[str, Any]]
    rfp_number: str
    
    # Outputs/Updates
    extraction_result: Optional[Dict[str, Any]]
    attempts: int
    is_valid: bool
    errors: List[str]

# 2. Define Nodes

class ExtractionAgent:
    def __init__(self):
        self.extraction_service = CertificateExtractionService()

    async def call_extraction(self, state: ExtractionState) -> Dict:
        """Node: Calls the AI Service (Mock or Real)"""
        logger.info(f"Agent executing extraction (Attempt {state.get('attempts', 0) + 1})")
        
        try:
            results = await self.extraction_service.extract_from_pages(
                state["pages"], 
                state["bidder_name"], 
                state["certificate_types"], 
                state["rfp_number"]
            )
            # Service returns a list, we take the first item for this single-cert agent
            result = results[0] if results else {}
            
            return {
                "extraction_result": result,
                "attempts": state.get("attempts", 0) + 1
            }
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "errors": [str(e)], 
                "attempts": state.get("attempts", 0) + 1
            }

    def critique_result(self, state: ExtractionState) -> Dict:
        """Node: Reflexion / Critique"""
        result = state.get("extraction_result", {})
        errors = []
        
        if not result:
            errors.append("Empty extraction result")
        
        # Check critical keys
        required_keys = ["isCertificate", "extractedEntityName", "certificateType"]
        for key in required_keys:
            if key not in result:
                errors.append(f"Missing key: {key}")
                
        # Hallucination Check (Basic) - Bidder Name
        # If passed match, but names are totally different (Logic check)
        # Note: This is where we'd add complex self-correction logic
        
        is_valid = len(errors) == 0
        logger.info(f"Critique complete. Valid: {is_valid}. Errors: {errors}")
        
        return {"is_valid": is_valid, "errors": errors}

# 3. Build Graph

def build_extraction_graph():
    agent = ExtractionAgent()
    
    workflow = StateGraph(ExtractionState)
    
    # Add Nodes
    workflow.add_node("extract", agent.call_extraction)
    workflow.add_node("critique", agent.critique_result)
    
    # Entry
    workflow.set_entry_point("extract")
    
    # Conditional Edge
    def should_continue(state: ExtractionState):
        if state["is_valid"]:
            return "end"
        if state["attempts"] >= 3:
            logger.warning("Max retries reached, accepting imperfect result")
            return "end" # Giving up after 3 tries
        return "retry"

    workflow.add_edge("extract", "critique")
    
    workflow.add_conditional_edges(
        "critique",
        should_continue,
        {
            "end": END,
            "retry": "extract"
        }
    )
    
    return workflow.compile()

# Singleton
extraction_graph = build_extraction_graph()
