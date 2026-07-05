# Let's Link — Project Memory

> Living document tracking all decisions, context, and architectural choices.

---

## 🧠 Project Context

| Field | Value |
|---|---|
| **Project Name** | Let's Link |
| **Type** | Hyperlocal gig-economy web application |
| **Start Date** | 2026-06-03 |
| **Developer Machine** | Lenovo Ideapad Gaming 3 (Windows) |
| **Why Web App** | Performance limitations with Android Studio on dev machine |

---

## 🏗️ Tech Stack Decisions

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | HTML + Vanilla CSS + JavaScript | Clean, professional, no framework overhead. Maximum control over design. |
| **Backend** | Python (FastAPI) | Modern, async-capable, auto-generates API docs, type-safe with Pydantic |
| **Database** | PostgreSQL + PostGIS | Relational data + geospatial queries for proximity-based matching |
| **Real-time** | WebSockets (FastAPI native) | Chat, notifications, live location |
| **ORM** | SQLAlchemy + Alembic | Industry-standard Python ORM with migrations |
| **Auth** | JWT tokens + OTP | Stateless auth, phone-first onboarding |
| **Payments** | Razorpay (Escrow + Split + UPI) | Best marketplace toolkit for India |
| **File Storage** | Local (MVP) → Cloudinary/S3 (Production) | Start simple, scale later |

---

## 📐 Architecture Decisions

### ADR-001: Python Backend over Node.js
- **Decision:** Use Python (FastAPI) instead of Node.js
- **Date:** 2026-06-03
- **Reason:** User preference. Python is also excellent for data processing, ML-based matching in future, and has strong PostgreSQL ecosystem.

### ADR-002: Vanilla Frontend over Framework
- **Decision:** Use plain HTML/CSS/JS instead of React/Next.js
- **Date:** 2026-06-03
- **Reason:** Simpler to develop and maintain. No build step needed. Professional design achievable with modern CSS (grid, flexbox, animations, custom properties).

### ADR-003: FastAPI over Flask/Django
- **Decision:** Use FastAPI as the Python web framework
- **Date:** 2026-06-03
- **Reason:** Native async support (critical for WebSockets/chat), automatic OpenAPI docs, Pydantic validation, better performance than Flask, lighter than Django.

---

## 🗂️ Project Structure

```
demoofletslink/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Environment configuration
│   ├── database.py             # Database connection & session
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── auth.py                 # JWT authentication utilities
│   ├── requirements.txt        # Python dependencies
│   └── routes/
│       ├── auth.py             # Login, register, OTP
│       ├── tasks.py            # Task CRUD, offers, status
│       ├── users.py            # Profile, skills, dashboard
│       ├── chat.py             # WebSocket chat
│       └── reviews.py          # Ratings & reviews
├── frontend/
│   ├── index.html              # Landing / Home page
│   ├── css/
│   │   └── styles.css          # Global styles & design system
│   ├── js/
│   │   ├── app.js              # Main application logic
│   │   ├── api.js              # API client utilities
│   │   ├── router.js           # Client-side routing (SPA)
│   │   └── components.js       # Reusable UI components
│   └── assets/
│       ├── icons/              # SVG icons
│       └── images/             # Static images
├── memory.md                   # This file — project context & decisions
├── summary.md                  # Workflow progress & session summaries
└── .env                        # Environment variables (not committed)
```

---

## 🎨 Design Decisions

| Decision | Choice |
|---|---|
| **Color Scheme** | Dark mode primary with electric purple (#6C5CE7) + teal cyan (#00CEC9) |
| **Typography** | Inter (headings) + system fonts (body) via Google Fonts |
| **Layout** | Mobile-first responsive, CSS Grid + Flexbox |
| **Icons** | Lucide Icons (lightweight SVG icon library) |
| **Animations** | CSS transitions + minimal JS animations for micro-interactions |

---

## 🔑 Key URLs & Resources

| Resource | URL |
|---|---|
| FastAPI Docs | https://fastapi.tiangolo.com/ |
| Razorpay API | https://razorpay.com/docs/api/ |
| PostGIS | https://postgis.net/documentation/ |
| Lucide Icons | https://lucide.dev/ |
| Google Fonts (Inter) | https://fonts.google.com/specimen/Inter |

---

## 📝 Notes & Reminders

- Start with mock data for MVP — no real payment gateway initially
- PWA manifest should be added early for installability
- Keep accessibility in mind: large touch targets, high contrast, voice support planned for Phase 3
- Test on low-end devices (target audience uses budget phones)
