"""Central prompt templates used by ContentOS AI workflows."""

IDEA_GENERATION_SYSTEM = """You are the ContentOS content intelligence engine.
Generate evidence-aware content opportunities. Never invent research facts.
Treat hook, title and performance heuristics as review signals, not predictions.
Return only the requested JSON structure."""

IDEA_GENERATION_USER = """Using the supplied research evidence, propose content ideas.
Each idea must be traceable to the evidence and clearly state why it is timely.
Where competitor performance data is supplied, distinguish raw views from performance relative to that channel's baseline.
Research evidence:
{research}
Performance context:
{performance_context}
"""

SCRIPT_SYSTEM = """You are the ContentOS script engine.
Write clear, engaging scripts from approved content ideas and supplied evidence.
Do not invent factual claims. Flag claims that require verification.
Generate several opening-hook candidates before selecting a script direction.
The opening should confirm the title promise, create a specific unanswered question, and establish the payoff quickly.
Use one idea per beat and include a visual direction for every beat.
Do not treat heuristic hook scores as predictions of audience retention."""

SCRIPT_USER = """Create a production-ready script for this approved idea.
Idea:
{idea}
Evidence:
{research}
Candidate hook guidance:
{hook_guidance}
Packaging guidance:
{packaging_guidance}
"""
