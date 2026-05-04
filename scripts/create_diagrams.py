import os

def create_svg_1():
    lines = []
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 700" width="960" height="700">')
    lines.append('  <style>')
    lines.append("    text { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }")
    lines.append('  </style>')
    lines.append('  <defs>')
    lines.append('    <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#dc2626"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-purple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#9333ea"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#6b7280"/>')
    lines.append('    </marker>')
    lines.append('  </defs>')
    lines.append('  <rect width="960" height="700" fill="#ffffff"/>')
    
    # Title
    lines.append('  <text x="480" y="30" fill="#111827" font-size="20" font-weight="600" text-anchor="middle">InsureVN Multi-Agent Platform - Core Architecture</text>')

    # Nodes function
    def rect(x, y, w, h, fill, stroke, rx="8"):
        lines.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    
    def text(x, y, s, size=14, color="#111827", weight="400"):
        lines.append(f'  <text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="middle">{s}</text>')

    # Layers / Containers
    lines.append('  <!-- Evidence Layer Container -->')
    lines.append('  <rect x="130" y="210" width="700" height="150" rx="8" fill="none" stroke="#d1d5db" stroke-width="1.5" stroke-dasharray="6,4"/>')
    text(140, 230, "Parallel Evidence Gathering", 12, "#6b7280", "600")
    lines.append('  <rect x="130" y="370" width="600" height="130" rx="8" fill="none" stroke="#d1d5db" stroke-width="1.5" stroke-dasharray="6,4"/>')
    text(140, 390, "Specialist Workflows", 12, "#6b7280", "600")

    # 1. User
    rect(400, 50, 160, 40, "#ffffff", "#d1d5db", "20")
    text(480, 75, "User / Scenario", 14, "#111827", "600")

    # 2. Supervisor
    rect(380, 120, 200, 60, "#faf5ff", "#c084fc") # purple tint
    text(480, 145, "SupervisorAgent", 15, "#111827", "600")
    text(480, 165, "Classify &amp; Route", 12, "#6b7280")

    # 3. Evidence sources
    rect(150, 250, 140, 50, "#eff6ff", "#bfdbfe")
    text(220, 275, "Ensemble Retriever", 12, "#111827", "600")
    text(220, 290, "(Vector+BM25+Graph)", 10, "#6b7280")

    rect(320, 250, 140, 50, "#eff6ff", "#bfdbfe")
    text(390, 275, "DatabaseAgent", 13, "#111827", "600")
    text(390, 290, "SQLite MCP", 11, "#6b7280")

    rect(490, 250, 140, 50, "#eff6ff", "#bfdbfe")
    text(560, 275, "Profile Store", 13, "#111827", "600")
    text(560, 290, "Synthetic Data", 11, "#6b7280")

    rect(660, 250, 140, 50, "#eff6ff", "#bfdbfe")
    text(730, 275, "OCR DocumentAgent", 12, "#111827", "600")
    text(730, 290, "User Evidence", 11, "#6b7280")

    rect(380, 320, 200, 30, "#ffffff", "#d1d5db", "15")
    text(480, 340, "Evidence Merger", 12, "#111827", "600")

    # 4. Specialists
    rect(150, 410, 160, 50, "#f0fdf4", "#86efac") # green tint
    text(230, 435, "PolicyAgent", 14, "#111827", "600")
    text(230, 450, "Explain Policy", 11, "#6b7280")

    rect(360, 410, 180, 50, "#f0fdf4", "#86efac")
    text(450, 435, "ComparisonAdvisorAgent", 13, "#111827", "600")
    text(450, 450, "Compare/Rank", 11, "#6b7280")

    rect(580, 410, 130, 50, "#f0fdf4", "#86efac")
    text(645, 435, "ClaimAgent", 14, "#111827", "600")
    text(645, 450, "Draft Decision", 11, "#6b7280")

    rect(740, 390, 140, 40, "#fef2f2", "#fca5a5") # red tint
    text(810, 415, "ValidationAgent", 12, "#111827", "600")

    rect(740, 450, 140, 40, "#ffffff", "#d1d5db") 
    text(810, 475, "CalculationAgent", 12, "#111827", "600")

    # 5. Verifier
    rect(400, 530, 160, 50, "#faf5ff", "#c084fc")
    text(480, 555, "VerifierAgent", 14, "#111827", "600")
    text(480, 570, "Check Citations &amp; Risk", 11, "#6b7280")

    # 6. Output
    rect(250, 620, 180, 50, "#fff7ed", "#fdba74") # orange tint
    text(340, 645, "Customer Input", 14, "#111827", "600")
    text(340, 660, "Confirm Facts", 11, "#6b7280")

    rect(530, 620, 180, 50, "#fff7ed", "#fdba74")
    text(620, 645, "Employee Review", 14, "#111827", "600")
    text(620, 660, "Approve Decision", 11, "#6b7280")

    # Arrows function
    def arrow(path, color="#2563eb", marker="arrow-blue", dash="none"):
        lines.append(f'  <path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="{dash}" marker-end="url(#{marker})"/>')
    def arrow_label(x, y, text_str):
        lines.append(f'  <rect x="{x-40}" y="{y-10}" width="80" height="20" fill="#ffffff" opacity="0.95"/>')
        lines.append(f'  <text x="{x}" y="{y+4}" fill="#6b7280" font-size="11" text-anchor="middle">{text_str}</text>')

    # User -> Supervisor
    arrow("M480,90 L480,120")
    
    # Supervisor -> Evidence
    arrow("M440,180 L440,210 L220,210 L220,250", "#9333ea", "arrow-purple")
    arrow("M460,180 L460,200 L390,200 L390,250", "#9333ea", "arrow-purple")
    arrow("M500,180 L500,200 L560,200 L560,250", "#9333ea", "arrow-purple")
    arrow("M520,180 L520,210 L730,210 L730,250", "#9333ea", "arrow-purple")

    arrow_label(580, 210, "Gather Evidence")

    # Evidence -> Merger
    arrow("M220,300 L220,335 L380,335", "#6b7280", "arrow-gray")
    arrow("M390,300 L390,320", "#6b7280", "arrow-gray")
    arrow("M560,300 L560,320", "#6b7280", "arrow-gray")
    arrow("M730,300 L730,335 L580,335", "#6b7280", "arrow-gray")

    # Merger -> Specialists
    arrow("M420,350 L420,380 L230,380 L230,410")
    arrow("M480,350 L480,410")
    arrow("M540,350 L540,380 L645,380 L645,410")

    # ClaimAgent <-> Validation
    arrow("M710,420 L740,420")
    arrow("M740,410 L710,410", "#dc2626", "arrow-red", "4,2")
    
    # ClaimAgent -> Calculation
    arrow("M645,460 L645,470 L740,470", "#6b7280", "arrow-gray")

    # Specialists -> Verifier
    arrow("M230,460 L230,500 L440,500 L440,530")
    arrow("M450,460 L450,530")
    arrow("M645,460 L645,500 L520,500 L520,530")

    # Verifier -> Customer Confirm
    arrow("M440,580 L440,600 L340,600 L340,620")
    
    # Verifier -> Employee Approve
    arrow("M520,580 L520,600 L620,600 L620,620")
    arrow_label(620, 600, "Review Packet")

    # Customer Confirm -> Employee
    arrow("M430,645 L530,645")

    lines.append('</svg>')
    
    with open('./output/arch1.svg', 'w') as f:
        f.write('\n'.join(lines))
    print("SVG 1 generated.")


def create_svg_2():
    lines = []
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 700" width="960" height="700">')
    lines.append('  <style>')
    lines.append("    text { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }")
    lines.append('  </style>')
    lines.append('  <defs>')
    lines.append('    <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#dc2626"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-purple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#9333ea"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#6b7280"/>')
    lines.append('    </marker>')
    lines.append('  </defs>')
    lines.append('  <rect width="960" height="700" fill="#ffffff"/>')

    # Title
    lines.append('  <text x="480" y="30" fill="#111827" font-size="20" font-weight="600" text-anchor="middle">Quad-Retrieval RAG Architecture</text>')

    def rect(x, y, w, h, fill, stroke, rx="8"):
        lines.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    def text(x, y, s, size=14, color="#111827", weight="400"):
        lines.append(f'  <text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="middle">{s}</text>')
    def arrow(path, color="#2563eb", marker="arrow-blue", dash="none"):
        lines.append(f'  <path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="{dash}" marker-end="url(#{marker})"/>')
    def arrow_label(x, y, text_str):
        lines.append(f'  <rect x="{x-50}" y="{y-10}" width="100" height="20" fill="#ffffff" opacity="0.95"/>')
        lines.append(f'  <text x="{x}" y="{y+4}" fill="#6b7280" font-size="11" text-anchor="middle">{text_str}</text>')

    # Background container for lanes
    lines.append('  <rect x="80" y="200" width="800" height="220" rx="8" fill="none" stroke="#d1d5db" stroke-width="1.5" stroke-dasharray="6,4"/>')
    text(90, 220, "Retrieval Lanes", 12, "#6b7280", "600")

    # Start
    rect(430, 60, 100, 30, "#ffffff", "#d1d5db", "15")
    text(480, 80, "START", 12, "#111827", "600")

    # Supervisor
    rect(380, 120, 200, 50, "#faf5ff", "#c084fc")
    text(480, 145, "Supervisor Node", 14, "#111827", "600")
    text(480, 160, "Extracts Intent &amp; Entities", 11, "#6b7280")

    # Lanes
    rect(100, 230, 180, 50, "#eff6ff", "#bfdbfe")
    text(190, 255, "Fast Lane", 14, "#111827", "600")
    text(190, 270, "(Simple Q&amp;A)", 11, "#6b7280")

    rect(390, 230, 180, 50, "#eff6ff", "#bfdbfe")
    text(480, 255, "Verified Lane", 14, "#111827", "600")
    text(480, 270, "(Comparison/Rules)", 11, "#6b7280")

    rect(680, 230, 180, 50, "#fef2f2", "#fca5a5")
    text(770, 255, "High-Risk Lane", 14, "#111827", "600")
    text(770, 270, "(Claims)", 11, "#6b7280")

    # Retrievers
    # Retrievers
    rect(240, 330, 200, 50, "#ffffff", "#d1d5db")
    text(340, 355, "Ensemble Retriever", 13, "#111827", "600")
    text(340, 370, "(Vector + BM25 + Graph)", 11, "#6b7280")

    rect(520, 330, 200, 50, "#ffffff", "#d1d5db")
    text(620, 355, "DatabaseAgent", 13, "#111827", "600")
    text(620, 370, "(SQLite MCP)", 11, "#6b7280")

    # Merge
    rect(390, 440, 180, 40, "#ffffff", "#d1d5db", "15")
    text(480, 465, "Merge &amp; Rerank", 13, "#111827", "600")

    # Synthesizer
    rect(380, 530, 200, 50, "#f0fdf4", "#86efac")
    text(480, 555, "Synthesizer Node", 14, "#111827", "600")
    text(480, 570, "Response &amp; Citations", 11, "#6b7280")

    # END
    rect(430, 620, 100, 30, "#ffffff", "#d1d5db", "15")
    text(480, 640, "END", 12, "#111827", "600")

    # Arrows
    arrow("M480,90 L480,120")
    
    # Supervisor -> Lanes
    arrow("M440,170 L440,200 L190,200 L190,230", "#9333ea", "arrow-purple")
    arrow("M480,170 L480,230", "#9333ea", "arrow-purple")
    arrow("M520,170 L520,200 L770,200 L770,230", "#9333ea", "arrow-purple")
    
    arrow_label(190, 200, "Hard Filters")

    # Lanes -> Retrievers
    # Fast Lane -> Ensemble
    arrow("M190,280 L190,305 L340,305 L340,330", "#3b82f6", "arrow-blue")
    
    # Verified Lane -> Ensemble and DB
    arrow("M480,280 L480,305 L360,305 L360,330", "#3b82f6", "arrow-blue")
    arrow("M480,280 L480,305 L600,305 L600,330", "#3b82f6", "arrow-blue")

    # High-Risk Lane -> Ensemble and DB
    arrow("M770,280 L770,305 L380,305 L380,330", "#3b82f6", "arrow-blue")
    arrow("M770,280 L770,305 L640,305 L640,330", "#3b82f6", "arrow-blue")

    # Retrievers -> Merge/Synthesizer
    arrow("M340,380 L340,410 L450,410 L450,440", "#6b7280", "arrow-gray")
    arrow("M620,380 L620,410 L510,410 L510,440", "#6b7280", "arrow-gray")
    
    arrow("M480,480 L480,530", "#2563eb", "arrow-blue")

    # Synthesizer -> END
    arrow("M480,580 L480,620")

    lines.append('</svg>')
    
    with open('./output/arch2.svg', 'w') as f:
        f.write('\n'.join(lines))
    print("SVG 2 generated.")

def create_svg_3():
    lines = []
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 750" width="1000" height="750">')
    lines.append('  <style>')
    lines.append("    text { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }")
    lines.append('  </style>')
    lines.append('  <defs>')
    lines.append('    <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#dc2626"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-purple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#9333ea"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#10b981"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#6b7280"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-orange" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#d97706"/>')
    lines.append('    </marker>')
    lines.append('    <marker id="arrow-dark" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#4b5563"/>')
    lines.append('    </marker>')
    lines.append('  </defs>')
    lines.append('  <rect width="1000" height="750" fill="#f8fafc"/>')

    # Title
    lines.append('  <text x="500" y="30" fill="#111827" font-size="20" font-weight="600" text-anchor="middle">InsureVN Unified Master Architecture</text>')

    def rect(x, y, w, h, fill, stroke, rx="8"):
        lines.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    def text(x, y, s, size=14, color="#111827", weight="400"):
        lines.append(f'  <text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="middle">{s}</text>')
    def arrow(path, color="#2563eb", marker="arrow-blue", dash="none"):
        lines.append(f'  <path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="{dash}" marker-end="url(#{marker})"/>')
    
    # 1. User Input
    rect(420, 40, 160, 40, "#ffffff", "#d1d5db", "20")
    text(500, 65, "User / Scenario", 14, "#111827", "600")

    arrow("M500,80 L500,110", "#9333ea", "arrow-purple")

    # 2. Supervisor
    rect(400, 110, 200, 50, "#f3e8ff", "#d8b4fe")
    text(500, 135, "SupervisorAgent", 14, "#7e22ce", "bold")
    text(500, 150, "Intent &amp; Routing", 11, "#9333ea")

    arrow("M450,160 L450,180 L210,180 L210,200", "#9333ea", "arrow-purple")
    arrow("M500,160 L500,200", "#9333ea", "arrow-purple")
    arrow("M550,160 L550,180 L780,180 L780,200", "#9333ea", "arrow-purple")

    # 3. Routing Lanes
    rect(110, 200, 200, 40, "#eff6ff", "#3b82f6")
    text(210, 225, "Fast Lane (Q&amp;A)", 13, "#1e40af", "600")

    rect(400, 200, 200, 40, "#ecfdf5", "#10b981")
    text(500, 225, "Verified Lane (Advisor)", 13, "#065f46", "600")

    rect(680, 200, 200, 40, "#fef2f2", "#ef4444")
    text(780, 225, "High-Risk Lane (Claim)", 13, "#991b1b", "600")

    # Routing Arrows -> Evidence
    # Fast Lane -> Ensemble (Blue)
    arrow("M210,240 L210,290", "#3b82f6", "arrow-blue")
    
    # Verified Lane -> Ensemble, DB, Profile (Green)
    arrow("M500,240 L500,255 L210,255 L210,290", "#10b981", "arrow-green")
    arrow("M500,240 L500,255 L400,255 L400,290", "#10b981", "arrow-green")
    arrow("M500,240 L500,255 L590,255 L590,290", "#10b981", "arrow-green")

    # High-Risk Lane -> Ensemble, DB, Profile, OCR (Red/Orange)
    arrow("M780,240 L780,275 L210,275 L210,290", "#ef4444", "arrow-red")
    arrow("M780,240 L780,275 L400,275 L400,290", "#ef4444", "arrow-red")
    arrow("M780,240 L780,275 L590,275 L590,290", "#ef4444", "arrow-red")
    arrow("M780,240 L780,290", "#ef4444", "arrow-red")

    # 4. Evidence Layer
    rect(130, 290, 160, 50, "#eff6ff", "#bfdbfe")
    text(210, 315, "Ensemble Retriever", 13, "#111827", "600")
    text(210, 330, "(Vector+BM25+Graph)", 10, "#6b7280")

    rect(320, 290, 160, 50, "#eff6ff", "#bfdbfe")
    text(400, 315, "DatabaseAgent", 13, "#111827", "600")
    text(400, 330, "(SQLite MCP)", 11, "#6b7280")

    rect(510, 290, 160, 50, "#eff6ff", "#bfdbfe")
    text(590, 315, "Profile Store", 13, "#111827", "600")
    text(590, 330, "(Synthetic Data)", 11, "#6b7280")

    rect(700, 290, 160, 50, "#eff6ff", "#bfdbfe")
    text(780, 315, "OCR DocumentAgent", 12, "#111827", "600")
    text(780, 330, "(User Evidence)", 11, "#6b7280")

    # Evidence -> Merger
    arrow("M210,340 L210,360 L390,360 L390,380", "#3b82f6", "arrow-blue") 
    arrow("M400,340 L400,380", "#6b7280", "arrow-gray")
    arrow("M590,340 L590,380", "#6b7280", "arrow-gray")
    arrow("M780,340 L780,360 L610,360 L610,380", "#6b7280", "arrow-gray")

    # 5. Evidence Merger
    rect(380, 380, 240, 30, "#ffffff", "#d1d5db", "15")
    text(500, 400, "Merge &amp; Rerank Evidence", 13, "#111827", "600")

    arrow("M450,410 L450,440 L210,440 L210,460", "#3b82f6", "arrow-blue")
    arrow("M500,410 L500,460", "#10b981", "arrow-green")
    arrow("M550,410 L550,440 L780,440 L780,460", "#ef4444", "arrow-red")

    # 6. Specialists (Synthesizers)
    rect(110, 460, 200, 50, "#eff6ff", "#3b82f6")
    text(210, 485, "PolicyAgent", 14, "#1e40af", "600")
    text(210, 500, "Explain &amp; Quote", 11, "#3b82f6")

    rect(400, 460, 200, 50, "#ecfdf5", "#10b981")
    text(500, 485, "ComparisonAdvisorAgent", 14, "#065f46", "600")
    text(500, 500, "Recommend &amp; Compare", 11, "#059669")

    rect(680, 460, 200, 50, "#fef2f2", "#ef4444")
    text(780, 485, "ClaimAgent", 14, "#991b1b", "600")
    text(780, 500, "Evaluate &amp; Payout", 11, "#dc2626")

    # 7. Validation
    rect(890, 460, 90, 25, "#fef2f2", "#fecaca")
    text(935, 477, "Validation", 11, "#991b1b")
    arrow("M880,468 L890,468", "#991b1b", "arrow-red")
    arrow("M890,477 L880,477", "#991b1b", "arrow-red", "4,2")

    rect(890, 490, 90, 25, "#fef2f2", "#fecaca")
    text(935, 507, "Calculation", 11, "#991b1b")
    arrow("M880,502 L890,502", "#991b1b", "arrow-red")

    # Specialists -> Verifier
    arrow("M210,510 L210,550 L450,550 L450,570", "#d97706", "arrow-orange")
    arrow("M500,510 L500,570", "#d97706", "arrow-orange")
    arrow("M780,510 L780,550 L550,550 L550,570", "#d97706", "arrow-orange")

    # 8. Verifier
    rect(400, 570, 200, 50, "#f3e8ff", "#d8b4fe")
    text(500, 595, "VerifierAgent", 14, "#7e22ce", "bold")
    text(500, 610, "Safety &amp; Compliance", 11, "#9333ea")

    arrow("M450,620 L450,650 L360,650 L360,670", "#9333ea", "arrow-purple")
    arrow("M550,620 L550,650 L640,650 L640,670", "#9333ea", "arrow-purple")

    # 9. Outputs
    rect(260, 670, 200, 50, "#ffffff", "#9ca3af", "10")
    text(360, 695, "Customer Confirm", 13, "#111827", "600")

    rect(540, 670, 200, 50, "#ffffff", "#9ca3af", "10")
    text(640, 695, "Employee Approve", 13, "#111827", "600")

    arrow("M460,695 L540,695", "#6b7280", "arrow-gray")

    lines.append('</svg>')
    
    with open('./output/arch_master.svg', 'w') as f:
        f.write('\n'.join(lines))
    print("SVG 3 generated.")

os.makedirs('./output', exist_ok=True)
create_svg_1()
create_svg_2()
create_svg_3()
