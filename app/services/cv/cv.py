import base64
import os
from weasyprint import HTML

# Resolve image path relative to cv.py
script_dir = os.path.dirname(os.path.abspath(__file__))
image_path = os.path.join(script_dir, "4x6-1.png")

if not os.path.exists(image_path):
    image_path = os.path.join(script_dir, "4x6.jpg")

avatar_b64 = ""
if os.path.exists(image_path):
    with open(image_path, "rb") as f:
        avatar_b64 = base64.b64encode(f.read()).decode("utf-8")
    print(f"Loaded avatar image directly from {image_path}")
else:
    print("Warning: Avatar image not found.")

def get_html_content(candidate_title="Frontend Engineer", ai_focus=False):
    if ai_focus:
        summary_text = (
            "Software Engineer with 3 years of experience building web and mobile applications using React.js, Next.js, "
            "TypeScript, and React Native, with backend proficiency in Python (FastAPI) and Node.js (Express). "
            "Experienced in integrating LLM APIs and computer vision pipelines (OpenCV, PyTorch), automated testing (Jest, Playwright), "
            "and leveraging AI-assisted developer workflows (Cursor, Copilot, DeepSeek) to accelerate feature delivery while maintaining clean code standards."
        )
    elif "Fullstack" in candidate_title or "Full-Stack" in candidate_title:
        summary_text = (
            "Software Engineer with 3 years of experience building web and mobile applications using React.js, Next.js, "
            "TypeScript, and React Native, with backend experience in Python (FastAPI), Node.js (Express), PostgreSQL, and Prisma ORM. "
            "Skilled in UI architecture, developing BFF services, writing automated tests (Jest, Playwright), "
            "and utilizing AI-assisted developer workflows (Cursor, Copilot, DeepSeek) to increase sprint velocity."
        )
    else:
        summary_text = (
            "Frontend Engineer with 3 years of experience building responsive web and mobile applications using React.js, "
            "Next.js, TypeScript, and React Native, with 1 year of backend experience in Python (FastAPI) and Node.js (Express). "
            "Skilled in UI architecture, developing BFF services, writing automated tests (Jest, Playwright), "
            "and leveraging AI-assisted developer workflows (Cursor, Copilot, DeepSeek) to accelerate feature delivery."
        )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Khong Vu Huy - Resume</title>
    <style>
        @page {{
            size: A4;
            margin: 8mm 12mm;
            @bottom-right {{
                content: counter(page) " / " counter(pages);
                font-family: Arial, Helvetica, sans-serif;
                font-size: 8pt;
                color: #64748b;
            }}
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif;
            color: #0f172a;
            font-size: 8.8pt;
            line-height: 1.35;
            margin: 0;
            padding: 0;
        }}
        
        /* HEADER SECTION */
        .header-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 8px;
            border-bottom: 2px solid #2563eb;
            padding-bottom: 6px;
        }}
        .header-main {{
            vertical-align: top;
        }}
        .header-avatar {{
            width: 95px;
            vertical-align: top;
            text-align: right;
        }}
        .avatar-img {{
            width: 85px;
            height: 110px;
            object-fit: cover;
            border-radius: 4px;
            border: 1px solid #cbd5e1;
        }}
        h1.candidate-name {{
            margin: 0 0 2px 0;
            font-size: 20pt;
            color: #0f172a;
            letter-spacing: 0.5px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .candidate-title {{
            margin: 0 0 5px 0;
            font-size: 11pt;
            color: #2563eb;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .contact-bar {{
            font-size: 8.5pt;
            color: #334155;
            line-height: 1.45;
        }}
        .contact-bar span {{
            font-weight: 600;
            color: #1e293b;
        }}
        .contact-sep {{
            color: #94a3b8;
            margin: 0 4px;
        }}

        /* SECTION TITLES */
        h2.section-title {{
            font-size: 10pt;
            color: #1e293b;
            text-transform: uppercase;
            border-bottom: 1.5px solid #2563eb;
            padding-bottom: 2px;
            margin-top: 8px;
            margin-bottom: 5px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        /* SUMMARY */
        .summary-block {{
            text-align: justify;
            margin-bottom: 6px;
            color: #334155;
            font-size: 8.8pt;
        }}

        /* SKILLS SECTION */
        .skills-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 6px;
        }}
        .skills-table td {{
            padding: 1.5px 0;
            vertical-align: top;
        }}
        .skill-category {{
            width: 125px;
            font-weight: 700;
            color: #1e293b;
            font-size: 8.8pt;
        }}
        .skill-values {{
            color: #334155;
            font-size: 8.8pt;
        }}

        /* COMPANY & EXPERIENCE SECTION */
        .company-header-box {{
            background-color: #f8fafc;
            border-left: 3px solid #2563eb;
            padding: 4px 8px;
            margin-bottom: 6px;
            border-radius: 0 4px 4px 0;
            page-break-inside: avoid;
        }}
        .company-title-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .company-name {{
            font-weight: 700;
            font-size: 9.8pt;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .company-date {{
            text-align: right;
            font-size: 8.5pt;
            font-weight: 700;
            color: #2563eb;
            white-space: nowrap;
        }}
        .company-role-line {{
            font-size: 8.8pt;
            font-weight: 600;
            color: #334155;
            margin-top: 1px;
        }}
        .company-summary {{
            font-size: 8.3pt;
            color: #475569;
            margin-top: 2px;
            font-style: italic;
        }}

        .exp-item {{
            margin-bottom: 6.5px;
            padding-left: 4px;
            page-break-inside: avoid;
        }}
        .exp-header-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1px;
        }}
        .exp-project {{
            font-weight: 700;
            font-size: 9.3pt;
            color: #0f172a;
            text-transform: uppercase;
        }}
        .exp-date {{
            text-align: right;
            font-size: 8.2pt;
            font-weight: 600;
            color: #475569;
            white-space: nowrap;
        }}
        .exp-role-line {{
            font-size: 8.6pt;
            font-weight: 600;
            color: #2563eb;
            margin-bottom: 1.5px;
        }}
        .exp-overview {{
            font-size: 8.2pt;
            color: #475569;
            margin-bottom: 2px;
            text-align: justify;
            font-style: italic;
        }}
        .exp-desc {{
            margin: 0;
            padding-left: 14px;
        }}
        .exp-desc li {{
            margin-bottom: 1.2px;
            color: #334155;
            font-size: 8.5pt;
        }}

        /* EDUCATION & CERTIFICATIONS & ACTIVITIES */
        .edu-item, .cert-item, .activity-item {{
            margin-bottom: 5px;
            page-break-inside: avoid;
        }}
        .edu-header-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .edu-school {{
            font-weight: 700;
            font-size: 9.2pt;
            color: #0f172a;
        }}
        .edu-date {{
            text-align: right;
            font-size: 8.3pt;
            color: #475569;
            font-weight: 600;
        }}
        .edu-details {{
            color: #334155;
            margin-top: 1px;
            font-size: 8.6pt;
        }}

        .bullet-list {{
            margin: 0;
            padding-left: 14px;
        }}
        .bullet-list li {{
            margin-bottom: 1.5px;
            color: #334155;
            font-size: 8.6pt;
        }}
    </style>
</head>
<body>

    <!-- HEADER SECTION -->
    <table class="header-table">
        <tr>
            <td class="header-main">
                <h1 class="candidate-name">KHONG VU HUY</h1>
                <div class="candidate-title">{candidate_title}</div>
                <div class="contact-bar">
                    <span>Phone:</span> 0965601872 <span class="contact-sep">|</span>
                    <span>Email:</span> huy.khmt.neu@gmail.com <span class="contact-sep">|</span>
                    <span>Location:</span> Hanoi, Vietnam<br>
                    <span>GitHub:</span> github.com/kohuyso
                </div>
            </td>
            {'<td class="header-avatar"><img src="data:image/png;base64,' + avatar_b64 + '" alt="Avatar" class="avatar-img"></td>' if avatar_b64 else ''}
        </tr>
    </table>

    <!-- PROFESSIONAL SUMMARY -->
    <h2 class="section-title">Professional Summary</h2>
    <div class="summary-block">
        {summary_text}
    </div>

    <!-- TECHNICAL SKILLS -->
    <h2 class="section-title">Technical Skills</h2>
    <table class="skills-table">
        <tr>
            <td class="skill-category">Frontend & Mobile:</td>
            <td class="skill-values">JavaScript, TypeScript, HTML, CSS, React.js, React Native (Expo, Expo Router, NativeWind), Next.js, Redux Toolkit, Jotai, Tailwind CSS, Radix UI, Material-UI (MUI), Highcharts, i18n</td>
        </tr>
        <tr>
            <td class="skill-category">Backend & APIs:</td>
            <td class="skill-values">Python, FastAPI, Node.js, Express.js, BFF Architecture, RESTful APIs, WordPress, Telegram Bot, JWT Authentication</td>
        </tr>
        <tr>
            <td class="skill-category">Database & Cache:</td>
            <td class="skill-values">PostgreSQL, SQL Server, MongoDB, Prisma ORM, Redis</td>
        </tr>
        <tr>
            <td class="skill-category">Web3 & DeFi:</td>
            <td class="skill-values">Decentralized Finance (DeFi), Solana, EVM (Ethers.js, Wagmi), Hardhat, IPFS</td>
        </tr>
        <tr>
            <td class="skill-category">Tools & DevOps:</td>
            <td class="skill-values">Git, Docker, CI/CD (Vercel), Firebase (FCM), Postman, Jest, Playwright, Scrum, Agile</td>
        </tr>
        <tr>
            <td class="skill-category">AI Workflows:</td>
            <td class="skill-values">Cursor IDE, GitHub Copilot, DeepSeek, Claude, Model Context Protocol (MCP), AI Agent Workflows</td>
        </tr>
    </table>

    <!-- WORK EXPERIENCE -->
    <h2 class="section-title">Work Experience</h2>

    <!-- MASTER COMPANY BLOCK -->
    <div class="company-header-box">
        <table class="company-title-table">
            <tr>
                <td class="company-name">SOFTWARE & TECHNOLOGY SOLUTIONS COMPANY</td>
                <td class="company-date">08/2023 – Present</td>
            </tr>
        </table>
        <div class="company-role-line">Frontend / Full-Stack Engineer | Hanoi, Vietnam (Full-time)</div>
        <div class="company-summary">
            Core frontend engineer responsible for UI architecture, state management, and developing backend/BFF services to integrate with frontend across the company's Web3 and AI products.
        </div>
    </div>

    <!-- PROJECT 1: FIT CHECK -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">FIT CHECK — Smart AI Fashion Assistant</td>
                <td class="exp-date">06/2026 – 08/2026</td>
            </tr>
        </table>
        <div class="exp-role-line">Full-Stack Mobile & AI Engineer | Solo Developer</div>
        <div class="exp-overview">
            AI-powered mobile fashion assistant and virtual outfit check application with Computer Vision and wardrobe recommendations.
        </div>
        <ul class="exp-desc">
            <li>Built a cross-platform mobile app using React Native, Expo (Expo Router), TypeScript, and NativeWind (Tailwind CSS).</li>
            <li>Developed AI backend services using Python, FastAPI, and PyTorch / OpenCV for image processing and outfit evaluation.</li>
            <li>Leveraged AI engineering workflows (Antigravity, Claude, MCP) to accelerate full-stack delivery and automated OpenAPI client generation (@hey-api/client-axios).</li>
            <li>Integrated camera capture (expo-camera, expo-image-picker), local offline storage (expo-sqlite, expo-secure-store), and React Hook Form.</li>
        </ul>
    </div>

    <!-- PROJECT 2: AIPAD -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">AIPAD — Innovation & Hackathon Platform</td>
                <td class="exp-date">02/2026 – 06/2026</td>
            </tr>
        </table>
        <div class="exp-role-line">Frontend Engineer | Team size: 6 (Sole Frontend Developer) | <span style="font-weight:normal;">aipad.vn</span></div>
        <div class="exp-overview">
            AI-driven platform for managing innovation programs, hackathons, startup competitions, and incubators.
        </div>
        <ul class="exp-desc">
            <li>Led frontend development as the sole frontend engineer, building responsive interfaces with Next.js, React.js, and Tailwind CSS.</li>
            <li>Managed app state and asynchronous data caching using Jotai and React Query.</li>
            <li>Integrated Radix UI primitives, Highcharts for program analytics, React Markdown, React PDF, and next-intl for multi-language support.</li>
            <li>Implemented real-time notifications using Firebase Cloud Messaging (FCM).</li>
        </ul>
    </div>

    <!-- PROJECT 3: ASTAR LANDING PAGE -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">ASTAR PLATFORM & LANDING PAGE</td>
                <td class="exp-date">02/2026 – 05/2026</td>
            </tr>
        </table>
        <div class="exp-role-line">Frontend Engineer (with BFF/Backend scope) | Team size: 2</div>
        <div class="exp-overview">
            High-performance landing page and web platform providing dynamic content publishing and SEO optimization.
        </div>
        <ul class="exp-desc">
            <li>Built a responsive, fast web platform using Next.js, TypeScript, and Prisma ORM.</li>
            <li>Built a BFF layer using Next.js API Routes and server-side functions with Prisma ORM for database access and WordPress integration.</li>
            <li>Applied SEO best practices (SSG/ISR rendering, metadata optimization, canonical tags, structured data) to improve page search rankings and performance.</li>
        </ul>
    </div>

    <!-- PROJECT 4: YIELDPLAY -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">YIELDPLAY — Web3 Gaming & DeFi Platform</td>
                <td class="exp-date">08/2025 – 01/2026</td>
            </tr>
        </table>
        <div class="exp-role-line">Frontend Engineer | Team size: 4 (Sole Frontend Developer)</div>
        <div class="exp-overview">
            Web3 gaming and DeFi platform introducing a "no-loss" staking model and B2B reward game solutions.
        </div>
        <ul class="exp-desc">
            <li>Developed the complete frontend using Next.js, React.js, and Tailwind CSS for consumer gaming and B2B partner portals.</li>
            <li>Integrated Solana wallet adapters for authentication and secure on-chain transactions.</li>
            <li>Managed application state and data fetching using Redux Toolkit and React Query; wrote end-to-end tests using Playwright.</li>
            <li>Integrated Radix UI, Highcharts data visualization, and Markdown rendering.</li>
        </ul>
    </div>

    <!-- PROJECT 5: LOOMIX -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">LOOMIX — AI-Driven Web3 Agent Platform</td>
                <td class="exp-date">12/2024 – 07/2025</td>
            </tr>
        </table>
        <div class="exp-role-line">Frontend / Fullstack Engineer | Team size: 4 (Sole Frontend Developer)</div>
        <div class="exp-overview">
            No-code AI-driven Web3 platform enabling users to build and manage AI agents for wallet tracking, token monitoring, and market signal analysis.
        </div>
        <ul class="exp-desc">
            <li>Developed core platform features using Next.js, React.js, and TypeScript.</li>
            <li>Built multi-agent dashboards using Jotai state management, Material-UI (MUI), Highcharts analytics, and EVM wallet login with JWT cookies.</li>
            <li>Built RESTful API endpoints in Node.js (Express.js) and a Telegram bot using Telegraf with MongoDB persistence.</li>
        </ul>
    </div>

    <!-- PROJECT 6: NEWS-AGGREGATOR -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">NEWS-AGGREGATOR — Crypto Market Intelligence</td>
                <td class="exp-date">07/2024 – 02/2025</td>
            </tr>
        </table>
        <div class="exp-role-line">Frontend Engineer | Team size: 3 (Sole Frontend Developer)</div>
        <div class="exp-overview">
            Web3 news aggregation platform that analyzes real-time market trends, social keywords, and signals to track crypto trends.
        </div>
        <ul class="exp-desc">
            <li>Developed a Web3 intelligence dashboard using Next.js, React.js, TypeScript, and Redux Toolkit.</li>
            <li>Built interactive dashboards with Material-UI (MUI) and Highcharts for keyword sentiment analysis and narrative tracking.</li>
            <li>Integrated EVM wallet authentication for user login.</li>
        </ul>
    </div>

    <!-- PROJECT 7: TRAVA GPT -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">TRAVA GPT — AI Conversational DeFi Assistant</td>
                <td class="exp-date">04/2024 – 11/2024</td>
            </tr>
        </table>
        <div class="exp-role-line">Frontend Engineer | Team size: 5 (2 Frontend Developers)</div>
        <div class="exp-overview">
            AI conversational platform powered by LLMs for the Trava DeFi ecosystem, interpreting user prompts to analyze on-chain data and execute UI actions.
        </div>
        <ul class="exp-desc">
            <li>Contributed to frontend development using Next.js, React.js, TypeScript, Redux Toolkit, and React Query.</li>
            <li>Built dynamic chat interfaces that allow users to execute swaps, staking, and asset management directly inside the chat.</li>
            <li>Integrated multi-EVM chain support using Ethers.js and wallet adapters.</li>
        </ul>
    </div>

    <!-- PROJECT 8: NFT MARKETPLACE - OASIS -->
    <div class="exp-item">
        <table class="exp-header-table">
            <tr>
                <td class="exp-project">NFT MARKETPLACE - OASIS</td>
                <td class="exp-date">07/2023 – 12/2023</td>
            </tr>
        </table>
        <div class="exp-role-line">Full-Stack Engineer</div>
        <div class="exp-overview">
            Full-stack NFT marketplace where users can create, mint, buy, sell, and auction digital assets.
        </div>
        <ul class="exp-desc">
            <li>Built the full-stack web application with Next.js and Material-UI (MUI) frontend connected to an ExpressJS backend and MongoDB database.</li>
            <li>Authored and deployed Ethereum smart contracts using Hardhat and IPFS storage.</li>
        </ul>
    </div>

    <!-- EDUCATION -->
    <h2 class="section-title">Education</h2>
    <div class="edu-item">
        <table class="edu-header-table">
            <tr>
                <td class="edu-school">National Economics University (NEU)</td>
                <td class="edu-date">2020 – 2024</td>
            </tr>
        </table>
        <div class="edu-details">
            Bachelor of Science in Computer Science | <strong>GPA: 3.55 / 4.0</strong><br>
            University Academic Excellence Scholarship (awarded 3 / 7 semesters)
        </div>
    </div>

    <!-- CERTIFICATIONS & HONORS -->
    <h2 class="section-title">Certifications & Honors</h2>
    <ul class="bullet-list">
        <li><strong>IELTS Academic:</strong> Overall Score 6.5</li>
        <li><strong>Third Prize:</strong> University Olympic Computer Science Competition (CS Major) – 2021</li>
        <li><strong>Third Prize:</strong> University Olympic Computer Science Competition (Non-CS Major) – 2021</li>
    </ul>

    <!-- ACTIVITIES & LEADERSHIP -->
    <h2 class="section-title">Activities & Leadership</h2>
    <div class="activity-item">
        <div class="edu-school">Information Technology Club - National Economics University (2020 – 2022)</div>
        <ul class="bullet-list" style="margin-top: 2px;">
            <li>Active member of Academic Department (completed C++, Algorithms, Java OOP).</li>
            <li>Instructor for Coding Fundamentals Workshop (2021).</li>
            <li>Organizer for Student Tech Talkshows ("Way to Enterprise", "Javawora - Bawave", "Software Engineering").</li>
        </ul>
    </div>

</body>
</html>
"""

versions = [
    ("Frontend Engineer", "KHONG-VU-HUY-CV-Frontend.pdf", "cv-frontend.html", False),
    ("Fullstack Engineer", "KHONG-VU-HUY-CV-Fullstack.pdf", "cv-fullstack.html", False),
    ("Fullstack / Frontend Engineer", "KHONG-VU-HUY-CV-Fullstack-Frontend.pdf", "cv-fullstack-frontend.html", False),
    ("Fullstack Engineer", "KHONG-VU-HUY-CV-Fullstack-AI.pdf", "cv-fullstack-ai.html", True),
]

for title, pdf_name, html_name, ai_focus in versions:
    html_str = get_html_content(title, ai_focus=ai_focus)
    html_path = os.path.join(script_dir, html_name)
    pdf_path = os.path.join(script_dir, pdf_name)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"HTML saved to {html_path}")
    HTML(html_path).write_pdf(pdf_path)
    label = f"{title} (AI/ML version)" if ai_focus else title
    print(f"PDF generated for '{label}': {pdf_path}")

# Default compatibility outputs (Frontend Engineer)
default_html_path = os.path.join(script_dir, "cv.html")
default_pdf_path = os.path.join(script_dir, "KHONG-VU-HUY-CV-ATS.pdf")
legacy_pdf_path = os.path.join(script_dir, "KHONG-VU-HUY-CV-Updated.pdf")

with open(default_html_path, "w", encoding="utf-8") as f:
    f.write(get_html_content("Frontend Engineer"))

HTML(default_html_path).write_pdf(default_pdf_path)
HTML(default_html_path).write_pdf(legacy_pdf_path)
print(f"Default ATS PDFs updated.")