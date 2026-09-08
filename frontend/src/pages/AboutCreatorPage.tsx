import React, { useState } from 'react'
import clsx from 'clsx'
import {
  ChevronDown, ChevronUp, ExternalLink, Mail, Phone,
  MapPin, GraduationCap, Briefcase, Code2, Cpu,
  Globe, GitBranch, Star, Users, Zap, Award,
} from 'lucide-react'

// ─── Skill chip ───────────────────────────────────────────────────────────────

function SkillChip({ label, tier = 'default' }: { label: string; tier?: 'core' | 'default' }) {
  return (
    <span className={clsx(
      'inline-flex items-center rounded-xs border px-2.5 py-1 text-[11px] font-medium',
      tier === 'core'
        ? 'border-ink/20 bg-ink text-canvas'
        : 'border-hairline bg-stone text-slate',
    )}>
      {label}
    </span>
  )
}

// ─── Expandable card (Experience / Project) ───────────────────────────────────

interface CardSection {
  label: string
  content: React.ReactNode
}

function ExpandableCard({
  badge, title, subtitle, period, location, summary, tags, sections,
}: {
  badge: string
  title: string
  subtitle: string
  period: string
  location?: string
  summary: string
  tags: string[]
  sections: CardSection[]
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-sm border border-hairline bg-canvas overflow-hidden transition-shadow hover:shadow-sm">
      {/* Header (always visible) */}
      <button
        className="w-full text-left px-5 py-4"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="rounded-xs border border-hairline bg-stone px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-muted">
                {badge}
              </span>
              <span className="font-mono text-[10px] text-muted">{period}</span>
              {location && (
                <span className="font-mono text-[10px] text-muted flex items-center gap-1">
                  <MapPin className="h-2.5 w-2.5" />{location}
                </span>
              )}
            </div>
            <h3 className="text-base font-semibold text-ink leading-tight">{title}</h3>
            <p className="text-sm text-slate mt-0.5">{subtitle}</p>
            <p className="mt-2 text-xs text-body-muted leading-relaxed line-clamp-2">{summary}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {tags.map(t => (
                <span key={t} className="rounded-xs border border-hairline bg-stone px-2 py-0.5 font-mono text-[10px] text-slate">
                  {t}
                </span>
              ))}
            </div>
          </div>
          <div className="shrink-0 mt-1 text-muted">
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </div>
      </button>

      {/* Expanded body */}
      {open && (
        <div className="border-t border-hairline bg-stone/20">
          {sections.map((s, i) => (
            <div key={i} className={clsx('px-5 py-4', i > 0 && 'border-t border-hairline')}>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">{s.label}</p>
              <div className="text-sm text-body-muted leading-relaxed">{s.content}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Stat chip ────────────────────────────────────────────────────────────────

function StatChip({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-sm border border-hairline bg-canvas px-4 py-3">
      <div className="flex h-7 w-7 items-center justify-center rounded-xs bg-stone">
        <Icon className="h-3.5 w-3.5 text-slate" />
      </div>
      <div>
        <p className="text-sm font-semibold text-ink">{value}</p>
        <p className="font-mono text-[9px] uppercase tracking-wider text-muted">{label}</p>
      </div>
    </div>
  )
}

// ─── Bullet list ─────────────────────────────────────────────────────────────

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function AboutCreatorPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-12 pb-20">

      {/* ── Hero / Profile ── */}
      <div className="rounded-sm border border-hairline bg-canvas overflow-hidden">
        <div className="px-8 pt-8 pb-6 border-b border-hairline">
          {/* Avatar placeholder + name */}
          <div className="flex items-start gap-5">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-sm bg-ink text-2xl font-bold text-canvas select-none">
              N
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-ink">Nikhil Menariya</h1>
              <p className="text-sm text-slate mt-0.5">Software Engineer Intern · AI Agents · Python / TypeScript · Shipped Products</p>
              <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
                <a href="mailto:nikhilmenariya78@gmail.com" className="flex items-center gap-1.5 hover:text-ink transition-colors">
                  <Mail className="h-3.5 w-3.5" /> nikhilmenariya78@gmail.com
                </a>
                <span className="flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5" /> +91 9119347437
                </span>
                <span className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5" /> Surat, Gujarat
                </span>
                <a href="https://github.com" target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-ink transition-colors">
                  <GitBranch className="h-3.5 w-3.5" /> GitHub
                </a>
                <a href="https://linkedin.com" target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-ink transition-colors">
                  <ExternalLink className="h-3.5 w-3.5" /> LinkedIn
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Education + stats */}
        <div className="px-8 py-5 border-b border-hairline">
          <div className="flex items-center gap-3">
            <GraduationCap className="h-4 w-4 text-muted shrink-0" />
            <div>
              <p className="text-sm font-medium text-ink">
                Vellore Institute of Technology, Chennai
              </p>
              <p className="text-xs text-muted">B.Tech Computer Science Engineering · 2023 – 2027 · CGPA 9.10 / 10</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
          <StatChip icon={Briefcase} label="Internships" value="2" />
          <StatChip icon={Code2}     label="Projects shipped" value="4+" />
          <StatChip icon={Users}     label="Daily users" value="200–500" />
          <StatChip icon={Star}      label="CGPA" value="9.10 / 10" />
        </div>
      </div>

      {/* ── Skills ── */}
      <div>
        <h2 className="mb-5 text-xl font-semibold tracking-tight text-ink">Skills</h2>
        <div className="space-y-4">
          {[
            {
              category: 'AI / LLM Engineering',
              icon: Cpu,
              core: true,
              chips: [
                'LangGraph', 'LangChain', 'Agentic AI', 'RAG', 'Knowledge Graphs',
                'Prompt Engineering', 'Tool Use / Function Calling', 'Evaluation Pipelines',
                'Human-in-the-loop', 'Vector Retrieval', 'LLM Failure Handling',
              ],
            },
            {
              category: 'Languages',
              icon: Code2,
              chips: ['Python', 'TypeScript', 'JavaScript', 'Java', 'C++'],
            },
            {
              category: 'Backend & Data',
              icon: Zap,
              chips: [
                'FastAPI', 'Node.js', 'REST APIs', 'Data Pipelines',
                'Data Extraction & Cleansing', 'Unstructured Data Processing',
                'Celery', 'Redis', 'MySQL', 'PostgreSQL', 'MongoDB',
              ],
            },
            {
              category: 'Frontend',
              icon: Globe,
              chips: ['React.js', 'Next.js', 'Tailwind CSS', 'Vite'],
            },
            {
              category: 'Finance-Adjacent',
              icon: Award,
              chips: ['GST', 'Income Tax', 'TDS', 'ROC', 'Data Validation & Reconciliation', 'Financial Compliance'],
            },
            {
              category: 'Cloud & Infrastructure',
              icon: GitBranch,
              chips: ['AWS', 'Docker', 'CI/CD', 'Git', 'Lightsail', 'S3', 'Amplify', 'API Gateway'],
            },
          ].map(group => (
            <div key={group.category} className="rounded-sm border border-hairline bg-canvas p-4">
              <div className="mb-3 flex items-center gap-2">
                <group.icon className="h-3.5 w-3.5 text-muted" />
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted">{group.category}</p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {group.chips.map(c => (
                  <SkillChip key={c} label={c} tier={group.core ? 'core' : 'default'} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Experience ── */}
      <div>
        <h2 className="mb-5 text-xl font-semibold tracking-tight text-ink">Experience</h2>
        <div className="space-y-3">

          <ExpandableCard
            badge="Internship"
            title="TheTaxpert (TEKSTRATA Pvt. Ltd.)"
            subtitle="Full Stack Developer Intern"
            period="May 2026 – Present"
            location="Remote, Hyderabad"
            summary="Owned end-to-end development of thetaxpert.com — a live tax and financial document processing platform that parses GST, TDS, and ROC filings. Now serving 200–500 daily users."
            tags={['React', 'Node.js', 'FastAPI', 'MySQL', 'Razorpay', 'AWS S3', 'Lightsail', 'Amplify']}
            sections={[
              {
                label: 'What is TheTaxpert?',
                content: (
                  <p>A live tax and financial-document processing platform where clients submit dense semi-structured documents (GST, TDS, ROC filings) that are parsed, validated, and processed. The platform handled 300+ clients during the ITR season and runs with 200–500 daily users.</p>
                ),
              },
              {
                label: 'What I built',
                content: (
                  <BulletList items={[
                    'Owned the entire pipeline solo — backend APIs, frontend, database, payments, cloud deployment.',
                    'Built data validation and reconciliation logic: instead of blindly trusting extracted values, related fields are cross-checked against each other before reaching production.',
                    'Designed a microservices architecture: Node.js for application APIs, FastAPI for Python-based document processing services.',
                    'Integrated Razorpay for payments. Fixed a production issue where a successful Razorpay event did not update the application payment state — separated Payment State from Filing State to prevent duplicate or missed payment processing.',
                    'Implemented an admin-controlled fallback payment system (UPI scanner → team verification → admin panel) so the business could accept payments even when the automated payment gateway was unavailable.',
                    'Set up CI/CD so changes go live quickly with iteration on real user feedback.',
                  ]} />
                ),
              },
              {
                label: 'Architecture',
                content: (
                  <div className="font-mono text-[11px] bg-stone rounded-xs p-3 text-slate leading-relaxed">
                    {'React Frontend → Node.js APIs → PostgreSQL\n                          ↓\n                       FastAPI\n                          ↓\n              Document Processing (GST/TDS/ROC)\n                       ↑    ↓\n                    S3 (file storage)'}
                  </div>
                ),
              },
              {
                label: 'Key outcome',
                content: <p>Platform is live and used by real users daily. This was my first experience owning a production system end-to-end — including deployment, failure handling, database consistency, and maintaining a running application under real load.</p>,
              },
            ]}
          />

          <ExpandableCard
            badge="Internship"
            title="Hypercaller (Leknology Labs Pvt. Ltd.)"
            subtitle="AI Engineering Intern — Agent Orchestration"
            period="May 2026 – Aug 2026"
            location="Remote"
            summary="Built AI agents in Python (LangGraph) that reason over a domain-specific Knowledge Graph, combining prompting and tool use to resolve queries. Integrated voice AI, background processing, and a human-in-the-loop feedback system."
            tags={['Python', 'LangGraph', 'LangChain', 'Knowledge Graph', 'Deepgram', 'Kokoro TTS', 'Celery', 'Redis', 'Docker', 'AWS']}
            sections={[
              {
                label: 'What is Hypercaller?',
                content: <p>An AI sales platform and multi-tenant CRM where AI agents understand a company's products and interact with customers using company-specific knowledge — grounded in a domain Knowledge Graph, not the LLM's general training data.</p>,
              },
              {
                label: 'Data ingestion & Knowledge Graph',
                content: (
                  <BulletList items={[
                    'Built a crawler/ingestion pipeline: Raw Data → Extraction → Entity Identification → Relationship Mapping → Deduplication → Knowledge Graph.',
                    'The graph captures Company → Product → Feature relationships, enabling the agent to recommend the right product for each customer need.',
                    'Applied entity extraction, relationship mapping, and deduplication standards to keep the system grounded and reliable.',
                  ]} />
                ),
              },
              {
                label: 'LangGraph agent architecture',
                content: (
                  <div>
                    <p className="mb-2">Used LangGraph because the workflow is a graph, not a linear chain: User → Agent → Understand Intent → Retrieve Information → Use Tools → Reason → Generate Response. Different nodes execute depending on the situation.</p>
                    <BulletList items={[
                      'Wired in Deepgram STT and Kokoro TTS so agents handle real voice input — closing the loop from raw audio signal to spoken response.',
                      'Integrated tool use so the agent can call Knowledge Graph queries, product lookup tools, and external APIs mid-conversation.',
                    ]} />
                  </div>
                ),
              },
              {
                label: 'Human-in-the-loop feedback system',
                content: (
                  <div>
                    <p className="mb-2">Built a feedback loop to catch agent errors that "sound correct" — the hardest class of LLM failures:</p>
                    <BulletList items={[
                      'Logged full conversation transcripts, retrieved vector chunks, products surfaced, and KG context for each interaction.',
                      'A human reviewer provides natural-language feedback (e.g. "Should have recommended Product A, not B, because the customer is a small business").',
                      'A feedback agent processes the feedback and updates the relevant knowledge — not just as a comment, but as re-embeddable corrections that improve future retrieval.',
                      'Outcome: actual production failures become corrections to the system\'s knowledge base.',
                    ]} />
                  </div>
                ),
              },
              {
                label: 'Background processing',
                content: (
                  <BulletList items={[
                    'Crawling and processing pipelines run as background jobs via Celery workers backed by Redis queues — preventing long-running tasks from blocking API requests.',
                    'Redis also used for caching and supporting the async architecture.',
                    'Deployed services via Docker on AWS Lightsail Container Service, API Gateway, and S3.',
                  ]} />
                ),
              },
            ]}
          />

        </div>
      </div>

      {/* ── Projects ── */}
      <div>
        <h2 className="mb-5 text-xl font-semibold tracking-tight text-ink">Projects</h2>
        <p className="mb-4 text-xs text-muted italic">Shipped outside coursework, with real users — not sandbox projects.</p>
        <div className="space-y-3">

          <ExpandableCard
            badge="Project"
            title="Resum.AI — AI-Powered Resume Generator"
            subtitle="Agentic pipeline for ATS-optimized resume generation with eval loop"
            period="Personal project"
            summary="Agentic LangGraph pipeline that reads unstructured resume content, retrieves relevant experience against a JD via RAG, generates ATS-optimized LaTeX output, and evaluates it in a loop — hitting 85–95% benchmark consistently."
            tags={['Python', 'FastAPI', 'LangGraph', 'RAG', 'Redis', 'MongoDB', 'LaTeX']}
            sections={[
              {
                label: 'Problem',
                content: <p>Every new job application required manually re-explaining all projects to an AI, deciding which experience was relevant, modifying the resume, and checking quality. Resum.AI automates this entire workflow end-to-end.</p>,
              },
              {
                label: 'Architecture',
                content: (
                  <BulletList items={[
                    'User uploads resume/experience → stored in a RAG Knowledge Base.',
                    'User inputs a job description → system retrieves the most relevant projects, skills, and experience chunks.',
                    'LangGraph agent selects relevant content, generates ATS-friendly resume in LaTeX, compiles to PDF.',
                    'Evaluation loop: generated PDF is parsed and scored against the JD requirements. Issues are identified and the agent iterates until hitting the quality threshold.',
                    'Reverse direction: web-scraping agent finds relevant jobs based on the user\'s profile (Resume → Understand Candidate → Find Jobs → Rank Opportunities).',
                  ]} />
                ),
              },
              {
                label: 'Key outcome',
                content: <p>Consistently achieved 85–95% benchmark score in self-evaluation. First project where I implemented agentic evaluation and iterative generation-evaluate-improve loops.</p>,
              },
            ]}
          />

          <ExpandableCard
            badge="Project"
            title="GrabPic — AI Event Photo Retrieval"
            subtitle="Face recognition + vector search over 10,000+ event photos"
            period="Personal project"
            summary="A user uploads a selfie and the system returns all photos from the event where their face appears — using InsightFace embeddings and ChromaDB vector search with sub-second API response times."
            tags={['Python', 'FastAPI', 'InsightFace', 'ChromaDB', 'AWS', 'Docker', 'Redis']}
            sections={[
              {
                label: 'Problem',
                content: <p>A college photographer takes 10,000 photos at an event. Finding your own pictures in a gallery that size is impractical manually. GrabPic solves this with face-recognition-powered retrieval.</p>,
              },
              {
                label: 'How it works',
                content: (
                  <BulletList items={[
                    'Event organiser creates a private event and uploads photos. Each face is detected, converted to an embedding via InsightFace/Buffalo, and stored in ChromaDB.',
                    'Attendee uploads a selfie → face embedding generated → vector similarity search against the event\'s face database → matching photos returned.',
                    'Background processing via Redis handles image embedding jobs asynchronously — image processing never blocks the API.',
                    'Designed for 10,000+ images with sub-second response on the search path.',
                  ]} />
                ),
              },
              {
                label: 'Key insight',
                content: <p>The retrieval pattern (Embeddings → Vector Store → Similarity Search → Ranked Results) is the same underlying pattern as modern RAG systems — applied here to faces rather than text.</p>,
              },
            ]}
          />

          <ExpandableCard
            badge="Project · Team Lead"
            title="VLabs — Lab Management System"
            subtitle="Production full-stack system used daily across multiple VIT Chennai labs"
            period="Team project · VIT Chennai"
            summary="Led a 5-member team to build and ship a full-stack lab management platform now used daily by students and faculty at VIT Chennai. ACID-compliant transaction design, real users, real bug reports."
            tags={['Node.js', 'React', 'MongoDB', 'AWS', 'Docker']}
            sections={[
              {
                label: 'What I built',
                content: (
                  <BulletList items={[
                    'Led a 5-member team — owned technical architecture and backend/database design.',
                    'Built with ACID-compliant transaction logic: operations requiring multiple database changes either complete fully or roll back — no partial updates.',
                    'Shipped to production. Real users, real edge cases, real bug reports.',
                    'Experience managing a team rather than only building solo — delegating, code reviewing, and coordinating delivery.',
                  ]} />
                ),
              },
              {
                label: 'Key outcome',
                content: <p>Used daily across multiple labs at VIT Chennai. First project where I experienced what it means to maintain a system after shipping — handling bug reports, iterating on feedback, and keeping the system reliable for real users.</p>,
              },
            ]}
          />

        </div>
      </div>

      {/* ── Certifications ── */}
      <div>
        <h2 className="mb-4 text-xl font-semibold tracking-tight text-ink">Certifications</h2>
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-3 rounded-sm border border-hairline bg-canvas px-4 py-3">
            <Award className="h-4 w-4 text-muted" />
            <div>
              <p className="text-sm font-medium text-ink">DevOps Fundamentals</p>
              <p className="text-xs text-muted">IBM</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Experience map ── */}
      <div>
        <h2 className="mb-5 text-xl font-semibold tracking-tight text-ink">How it all connects</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              label: 'Traditional Software Engineering',
              color: 'border-hairline',
              items: ['React / APIs', 'Databases (SQL + NoSQL)', 'REST architecture', 'Payments & auth', 'CI/CD + deployment', 'AWS + Docker', 'Production monitoring', 'Failure handling'],
              from: 'TheTaxpert · VLabs',
            },
            {
              label: 'Agentic AI Engineering',
              color: 'border-action-blue/30',
              items: ['LangChain / LangGraph', 'RAG & Knowledge Graphs', 'Tool use & function calling', 'Agent orchestration', 'Human-in-the-loop', 'Evaluation pipelines', 'LLM failure handling', 'Vector retrieval'],
              from: 'Hypercaller · Resum.AI · FKL',
            },
            {
              label: 'Applied AI',
              color: 'border-deep-green/30',
              items: ['Computer vision', 'Face recognition', 'Embeddings', 'Vector search', 'Large-scale image retrieval', 'Background processing'],
              from: 'GrabPic',
            },
          ].map(area => (
            <div key={area.label} className={clsx('rounded-sm border bg-canvas p-5', area.color)}>
              <p className="mb-1 text-sm font-semibold text-ink">{area.label}</p>
              <p className="mb-3 font-mono text-[9px] uppercase tracking-wider text-muted">{area.from}</p>
              <ul className="space-y-1">
                {area.items.map(i => (
                  <li key={i} className="flex items-center gap-1.5 text-xs text-body-muted">
                    <span className="h-1 w-1 shrink-0 rounded-full bg-muted" />
                    {i}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
