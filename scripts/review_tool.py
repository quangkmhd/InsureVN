import os
import glob
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI(title="InsureVN AI Output Reviewer")

DATA_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_extracted/aia.com.vn/2601-TCB-BH-SucKhoeTronDoi-brochure.pdf.coredownload.inline"

class FilePair(BaseModel):
    name: str
    md_exists: bool
    png_exists: bool

@app.get("/api/files", response_model=List[FilePair])
async def get_files():
    md_files = glob.glob(os.path.join(DATA_DIR, "*.md"))
    png_files = glob.glob(os.path.join(DATA_DIR, "*.png"))
    
    md_names = {os.path.splitext(os.path.basename(f))[0] for f in md_files}
    png_names = {os.path.splitext(os.path.basename(f))[0] for f in png_files}
    
    all_names = sorted(list(md_names | png_names))
    
    return [
        FilePair(
            name=name,
            md_exists=name in md_names,
            png_exists=name in png_names
        )
        for name in all_names
    ]

@app.get("/api/md/{name}")
async def get_md(name: str):
    path = os.path.join(DATA_DIR, f"{name}.md")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="MD file not found")
    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@app.get("/api/img/{name}")
async def get_img(name: str):
    path = os.path.join(DATA_DIR, f"{name}.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(path)

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InsureVN | AI Review Tool</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --accent: #38bdf8;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
            --sidebar-width: 320px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            height: 100vh;
            overflow: hidden;
            display: flex;
        }

        /* Sidebar */
        #sidebar {
            width: var(--sidebar-width);
            background-color: var(--bg-card);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            transition: all 0.3s ease;
        }

        .sidebar-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border);
        }

        .sidebar-header h1 {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--accent);
            letter-spacing: -0.025em;
        }

        .file-list {
            flex: 1;
            overflow-y: auto;
            padding: 0.75rem;
        }

        .file-item {
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            margin-bottom: 0.25rem;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            font-size: 0.875rem;
            color: var(--text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .file-item:hover {
            background-color: #334155;
            color: var(--text-main);
        }

        .file-item.active {
            background-color: rgba(56, 189, 248, 0.1);
            border-color: var(--accent);
            color: var(--accent);
            font-weight: 500;
        }

        /* Main Content */
        #main {
            flex: 1;
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        header {
            height: 64px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 2rem;
            background-color: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(8px);
            z-index: 10;
        }

        .status-bar {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .nav-btns {
            display: flex;
            gap: 0.5rem;
        }

        button {
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 0.5rem 1rem;
            border-radius: 0.4rem;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        button:hover {
            background: #334155;
            border-color: var(--text-muted);
        }

        button.primary {
            background: var(--accent);
            color: var(--bg-dark);
            border-color: var(--accent);
        }

        button.primary:hover {
            background: #7dd3fc;
        }

        .viewer-container {
            flex: 1;
            display: flex;
            overflow: hidden;
        }

        .pane {
            flex: 1;
            overflow-y: auto;
            padding: 2rem;
            position: relative;
        }

        .pane-label {
            position: sticky;
            top: 0;
            right: 0;
            background: var(--accent);
            color: var(--bg-dark);
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 0 0 0 0.5rem;
            z-index: 5;
            float: right;
            margin-top: -2rem;
            margin-right: -2rem;
        }

        #md-pane {
            border-right: 1px solid var(--border);
            background-color: #0f172a;
        }

        #img-pane {
            background-color: #1e293b;
            display: flex;
            justify-content: center;
            align-items: flex-start;
        }

        /* Markdown Styling */
        .markdown-body {
            line-height: 1.6;
            color: #e2e8f0;
        }

        .markdown-body h1, .markdown-body h2, .markdown-body h3 {
            margin-top: 1.5rem;
            margin-bottom: 1rem;
            color: var(--accent);
        }

        .markdown-body p { margin-bottom: 1rem; }

        .markdown-body table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1rem;
        }

        .markdown-body th, .markdown-body td {
            border: 1px solid var(--border);
            padding: 0.5rem;
            text-align: left;
        }

        .markdown-body th { background-color: #334155; }

        /* Image Styling */
        #review-image {
            max-width: 100%;
            height: auto;
            border-radius: 0.5rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            transition: transform 0.3s ease;
            cursor: zoom-in;
        }

        #review-image.zoomed {
            transform: scale(1.5);
            cursor: zoom-out;
        }

        /* Keyboard Shortcuts Help */
        .shortcuts-hint {
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            background: rgba(30, 41, 59, 0.9);
            padding: 0.75rem 1rem;
            border-radius: 0.75rem;
            border: 1px solid var(--border);
            font-size: 0.75rem;
            color: var(--text-muted);
            pointer-events: none;
            backdrop-filter: blur(4px);
        }

        .key {
            background: #334155;
            color: var(--text-main);
            padding: 0.1rem 0.4rem;
            border-radius: 0.2rem;
            font-family: monospace;
            margin: 0 0.2rem;
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <div class="sidebar-header">
            <h1>InsureVN</h1>
            <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 0.5rem;">AI EXTRACTION REVIEWER</div>
        </div>
        <div class="file-list" id="file-list">
            <!-- Files injected here -->
        </div>
    </div>

    <div id="main">
        <header>
            <div class="status-bar">
                <span id="current-filename" style="font-weight: 600;">Loading...</span>
                <span id="progress-text" style="font-size: 0.8rem; color: var(--text-muted);">0 / 0</span>
            </div>
            <div class="nav-btns">
                <button id="prev-btn"><span class="key">←</span> Prev</button>
                <button id="next-btn">Next <span class="key">→</span></button>
                <button class="primary" id="done-btn">Approve <span class="key">Space</span></button>
            </div>
        </header>

        <div class="viewer-container">
            <div class="pane" id="md-pane">
                <div class="pane-label">MARKDOWN OUTPUT</div>
                <div id="md-content" class="markdown-body"></div>
            </div>
            <div class="pane" id="img-pane">
                <div class="pane-label">ORIGINAL IMAGE</div>
                <img id="review-image" src="" alt="Review original">
            </div>
        </div>
    </div>

    <div class="shortcuts-hint">
        <span class="key">↑</span><span class="key">↓</span> Navigate &bull; 
        <span class="key">J</span><span class="key">K</span> Navigate &bull; 
        <span class="key">Space</span> Approve
    </div>

    <script>
        let files = [];
        let currentIndex = 0;

        async function loadFiles() {
            const res = await fetch('/api/files');
            files = await res.json();
            renderFileList();
            if (files.length > 0) {
                loadPair(0);
            }
        }

        function renderFileList() {
            const list = document.getElementById('file-list');
            list.innerHTML = files.map((f, i) => `
                <div class="file-item ${i === currentIndex ? 'active' : ''}" onclick="loadPair(${i})">
                    ${f.name}
                </div>
            `).join('');
            document.getElementById('progress-text').innerText = `${currentIndex + 1} / ${files.length}`;
        }

        async function loadPair(index) {
            currentIndex = index;
            const file = files[index];
            
            document.getElementById('current-filename').innerText = file.name;
            
            // Update active state in sidebar
            document.querySelectorAll('.file-item').forEach((el, i) => {
                el.classList.toggle('active', i === index);
            });
            
            // Scroll sidebar item into view
            const activeItem = document.querySelector('.file-item.active');
            if (activeItem) activeItem.scrollIntoView({ block: 'nearest' });

            // Load MD
            if (file.md_exists) {
                const mdRes = await fetch(`/api/md/${file.name}`);
                const mdData = await mdRes.json();
                document.getElementById('md-content').innerHTML = marked.parse(mdData.content);
            } else {
                document.getElementById('md-content').innerHTML = '<p style="color:red">No Markdown file found</p>';
            }

            // Load Image
            if (file.png_exists) {
                document.getElementById('review-image').src = `/api/img/${file.name}`;
            } else {
                document.getElementById('review-image').src = '';
                alert('No PNG file found for ' + file.name);
            }
            
            document.getElementById('progress-text').innerText = `${currentIndex + 1} / ${files.length}`;
            
            // Reset zoom
            document.getElementById('review-image').classList.remove('zoomed');
            
            // Reset scroll positions
            document.getElementById('md-pane').scrollTop = 0;
            document.getElementById('img-pane').scrollTop = 0;
        }

        function next() {
            if (currentIndex < files.length - 1) loadPair(currentIndex + 1);
        }

        function prev() {
            if (currentIndex > 0) loadPair(currentIndex - 1);
        }

        document.getElementById('next-btn').onclick = next;
        document.getElementById('prev-btn').onclick = prev;
        document.getElementById('done-btn').onclick = () => {
            // In a real app, we might save the approval status
            // For now, just go to next
            next();
        };

        document.getElementById('review-image').onclick = (e) => {
            e.target.classList.toggle('zoomed');
        };

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown' || e.key === 'j' || e.key === 'J') {
                next();
            } else if (e.key === 'ArrowUp' || e.key === 'k' || e.key === 'K') {
                prev();
            } else if (e.key === ' ') {
                e.preventDefault();
                next();
            }
        });

        loadFiles();
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    print(f"Starting review tool... Data directory: {DATA_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
