"""
LangGraph Customer Health Agent - 4-node workflow for Salesforce analysis
"""
import os
import json
from datetime import datetime
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph
import requests
import markdown

from config import Config
from tools import gather_account, gather_opportunities, gather_cases


class CustomerHealthState(TypedDict):
    """State schema for customer health analysis workflow"""
    account_name: str
    account_data: Optional[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]
    cases: List[Dict[str, Any]]
    health_score: str  # "Green", "Yellow", "Red"
    health_signals: Dict[str, Any]
    recommendations: str
    brief_path: str
    brief_content: str
    errors: List[str]


def gather_data(state: CustomerHealthState) -> CustomerHealthState:
    """Node 1: Gather account data from Salesforce via MCP"""
    print("[*] Gathering account data for:", state["account_name"])

    errors = state.get("errors", [])

    try:
        # Gather account details
        account_data = gather_account(state["account_name"])
        if not account_data:
            errors.append(f"Account '{state['account_name']}' not found in Salesforce")
            state["errors"] = errors
            return state

        state["account_data"] = account_data

        # Gather opportunities
        account_id = account_data.get("Id")
        opportunities = gather_opportunities(account_id) if account_id else []
        state["opportunities"] = opportunities

        # Gather cases
        cases = gather_cases(account_id) if account_id else []
        state["cases"] = cases

    except Exception as e:
        errors.append(f"Error gathering data: {str(e)}")
        state["errors"] = errors

    return state


def analyze_health(state: CustomerHealthState) -> CustomerHealthState:
    """Node 2: Analyze health signals and compute health score"""
    print("[+] Node: gather_data")

    errors = state.get("errors", [])

    # If errors from previous node, skip analysis
    if errors:
        state["errors"] = errors
        return state

    try:
        cases = state.get("cases", [])
        opportunities = state.get("opportunities", [])
        account_data = state.get("account_data", {})

        # Calculate health signals
        open_cases = len([c for c in cases if c.get("Status") != "Closed"])
        high_priority_cases = len([c for c in cases if c.get("Priority") == "High"])
        total_pipeline = sum(float(o.get("Amount", 0)) for o in opportunities if o.get("Amount"))

        # Last contact date (simplified - use account created date or contact date if available)
        last_contact = account_data.get("LastActivityDate", "Unknown")

        health_signals = {
            "open_cases": open_cases,
            "high_priority_cases": high_priority_cases,
            "total_pipeline": f"${total_pipeline:,.0f}",
            "last_contact": last_contact,
            "total_opportunities": len(opportunities),
            "total_cases": len(cases)
        }

        # Determine health score
        if high_priority_cases > 3 or open_cases > 10:
            health_score = "Red"
        elif high_priority_cases > 0 or open_cases > 5:
            health_score = "Yellow"
        else:
            health_score = "Green"

        state["health_signals"] = health_signals
        state["health_score"] = health_score

    except Exception as e:
        errors.append(f"Error analyzing health: {str(e)}")
        state["errors"] = errors

    return state


def generate_recommendations(state: CustomerHealthState) -> CustomerHealthState:
    """Node 3: Generate AI-powered recommendations using LLM"""
    print("[+] Node: analyze_health")

    errors = state.get("errors", [])

    # If errors from previous nodes, skip
    if errors:
        state["errors"] = errors
        return state

    try:
        # Prepare context for LLM
        account_data = state.get("account_data", {})
        health_signals = state.get("health_signals", {})
        health_score = state.get("health_score", "Unknown")

        prompt = f"""
You are a customer success analyst. Based on the following customer data, provide 3-5 concise, actionable recommendations.

Customer: {account_data.get('Name', 'Unknown')}
Industry: {account_data.get('Industry', 'Unknown')}
Annual Revenue: {account_data.get('AnnualRevenue', 'Unknown')}

Health Status: {health_score}
- Open Support Cases: {health_signals.get('open_cases', 0)}
- High Priority Cases: {health_signals.get('high_priority_cases', 0)}
- Total Pipeline: {health_signals.get('total_pipeline', 'Unknown')}
- Last Activity: {health_signals.get('last_contact', 'Unknown')}
- Active Opportunities: {health_signals.get('total_opportunities', 0)}

Provide recommendations in markdown format with concrete next steps for account management.
"""

        # Call LLM via OpenAI-compatible API
        try:
            import requests
            from config import Config
            api_key = Config.OPENAI_API_KEY

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": Config.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7
            }

            response = requests.post(
                Config.OPENAI_API_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            recommendations = response.json()["choices"][0]["message"]["content"]
        except Exception as llm_error:
            # Fallback if LLM call fails
            recommendations = """
## Recommendations

1. **Immediate Action - Support Escalation**: Monitor open cases closely and ensure timely resolution.
2. **Pipeline Growth**: Nurture existing opportunities and identify upsell potential.
3. **Relationship Check-in**: Schedule regular touchpoints to maintain account health.
4. **Industry Updates**: Share relevant solutions and best practices for their industry.
5. **Risk Mitigation**: Develop retention strategy if health score indicates risk.
"""

        state["recommendations"] = recommendations

    except Exception as e:
        errors.append(f"Error generating recommendations: {str(e)}")
        state["errors"] = errors

    return state


def create_brief(state: CustomerHealthState) -> CustomerHealthState:
    """Node 4: Assemble final markdown brief and save to output"""
    print("[+] Node: generate_recommendations")

    errors = state.get("errors", [])

    # If errors, create error brief instead
    if errors:
        brief_content = f"# Error Processing Account\n\n"
        for error in errors:
            brief_content += f"- {error}\n"
        state["brief_content"] = brief_content
        state["errors"] = errors
        return state

    try:
        account_data = state.get("account_data", {})
        health_signals = state.get("health_signals", {})
        health_score = state.get("health_score", "Unknown")
        recommendations = state.get("recommendations", "No recommendations generated.")

        # Build HTML brief
        health_class = "yellow" if health_score == "Yellow" else "green" if health_score == "Green" else "red"
        health_emoji = "[!]" if health_score == "Yellow" else "[OK]" if health_score == "Green" else "[X]"

        brief = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Customer Health Brief: {account_data.get('Name', 'Unknown')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 40px 20px; min-height: 100vh; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .health-score-section {{ padding: 40px; background: #f8f9fa; text-align: center; }}
        .health-score-badge {{ display: inline-block; padding: 20px 40px; border-radius: 12px; font-size: 2em; font-weight: 700; margin: 20px 0; }}
        .health-score-badge.yellow {{ background: linear-gradient(135deg, #ffd89b 0%, #ffa751 100%); color: #fff; }}
        .health-score-badge.green {{ background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%); color: #fff; }}
        .health-score-badge.red {{ background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: #fff; }}
        .content-section {{ padding: 40px; border-bottom: 1px solid #e9ecef; }}
        .content-section h2 {{ color: #2d3748; font-size: 1.8em; margin-bottom: 25px; }}
        .summary-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .summary-table th {{ background: #667eea; color: white; padding: 15px 20px; text-align: left; }}
        .summary-table td {{ padding: 15px 20px; border-bottom: 1px solid #e9ecef; }}
        .signals-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .signal-card {{ background: #f5f7fa; padding: 25px; border-radius: 10px; text-align: center; border-left: 4px solid #667eea; }}
        .signal-label {{ color: #666; font-size: 0.9em; margin-bottom: 8px; text-transform: uppercase; }}
        .signal-value {{ font-size: 2.5em; font-weight: 700; color: #2d3748; }}
        .recommendations-list {{ list-style: none; margin: 20px 0; }}
        .recommendations-list li {{ background: #f8f9fa; padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #667eea; line-height: 1.6; }}
        .footer {{ background: #f8f9fa; padding: 20px 40px; text-align: center; color: #999; border-top: 1px solid #e9ecef; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Customer Health Brief</h1>
            <div class="subtitle">{account_data.get('Name', 'Unknown')} &ndash; {account_data.get('Industry', 'Unknown')}</div>
        </div>

        <div class="health-score-section">
            <h2>Health Status</h2>
            <div class="health-score-badge {health_class}">{health_emoji} {health_score.upper()}</div>
        </div>

        <div class="content-section">
            <h2>Account Summary</h2>
            <table class="summary-table">
                <thead><tr><th>Field</th><th>Value</th></tr></thead>
                <tbody>
                    <tr><td>Account Name</td><td><strong>{account_data.get('Name', 'N/A')}</strong></td></tr>
                    <tr><td>Industry</td><td>{account_data.get('Industry', 'N/A')}</td></tr>
                    <tr><td>Annual Revenue</td><td><strong>${account_data.get('AnnualRevenue', 0):,}</strong></td></tr>
                    <tr><td>Employees</td><td>{account_data.get('NumberOfEmployees', 'N/A')}</td></tr>
                    <tr><td>Last Activity</td><td>{health_signals.get('last_contact', 'Unknown')}</td></tr>
                </tbody>
            </table>
        </div>

        <div class="content-section">
            <h2>Health Signals</h2>
            <div class="signals-grid">
                <div class="signal-card">
                    <div class="signal-label">Open Cases</div>
                    <div class="signal-value">{health_signals.get('open_cases', 0)}</div>
                </div>
                <div class="signal-card">
                    <div class="signal-label">High-Priority</div>
                    <div class="signal-value">{health_signals.get('high_priority_cases', 0)}</div>
                </div>
                <div class="signal-card">
                    <div class="signal-label">Pipeline Value</div>
                    <div class="signal-value">{health_signals.get('total_pipeline', 'N/A')}</div>
                </div>
                <div class="signal-card">
                    <div class="signal-label">Opportunities</div>
                    <div class="signal-value">{health_signals.get('total_opportunities', 0)}</div>
                </div>
            </div>
        </div>

        <div class="content-section">
            <h2>Recommendations</h2>
            <div style="line-height: 1.8; color: #333;">{markdown.markdown(recommendations)}</div>
        </div>

        <div class="footer">
            <p>Generated by LangGraph Customer Health Agent</p>
            <p><strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST</strong></p>
        </div>
    </div>
</body>
</html>"""

        # Save to output directory
        account_name_clean = state["account_name"].lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brief_filename = f"output/{timestamp}_{account_name_clean}_health_brief.html"

        os.makedirs("output", exist_ok=True)
        with open(brief_filename, "w", encoding="utf-8") as f:
            f.write(brief)

        state["brief_path"] = brief_filename
        state["brief_content"] = brief

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"Error creating brief: {str(e)}"]

    return state


def create_graph():
    """Create and compile the LangGraph workflow"""
    graph = StateGraph(CustomerHealthState)

    # Add nodes
    graph.add_node("gather_data", gather_data)
    graph.add_node("analyze_health", analyze_health)
    graph.add_node("generate_recommendations", generate_recommendations)
    graph.add_node("create_brief", create_brief)

    # Add edges
    graph.add_edge("gather_data", "analyze_health")
    graph.add_edge("analyze_health", "generate_recommendations")
    graph.add_edge("generate_recommendations", "create_brief")

    # Set entry point
    graph.set_entry_point("gather_data")

    # Compile
    return graph.compile()


def run_agent(account_name: str) -> str:
    """Run the customer health agent for a given account"""

    # Configuration is loaded from environment via Config class

    # Initialize state
    initial_state: CustomerHealthState = {
        "account_name": account_name,
        "account_data": None,
        "opportunities": [],
        "cases": [],
        "health_score": "Unknown",
        "health_signals": {},
        "recommendations": "",
        "brief_path": "",
        "brief_content": "",
        "errors": []
    }

    # Create and run graph
    graph = create_graph()
    result = graph.invoke(initial_state)

    print("[+] Node: create_brief")

    # Return results
    if result.get("errors"):
        print(f"\n[!] Errors occurred: {result['errors']}")
        return ""
    else:
        print(f"\n[RESULT] HEALTH BRIEF GENERATED")
        print(f"Health Score: {result.get('health_score', 'Unknown')}")
        print(f"Brief saved to: {result.get('brief_path', 'Unknown')}")
        return result.get("brief_content", "")


if __name__ == "__main__":
    # For testing only
    brief = run_agent("Burlington Textiles Corp of America")
    print(brief)
