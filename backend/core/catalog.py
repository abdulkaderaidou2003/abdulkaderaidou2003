"""Static module catalog returned by GET /api/modules."""

MODULE_CATALOG = [
    {"category": "People", "modules": [
        {"id": "hr", "name": "Human Resources", "icon": "users", "desc": "Records, recruiting, onboarding"},
        {"id": "payroll", "name": "Payroll", "icon": "credit-card", "desc": "Pay stubs, deductions, T4"},
        {"id": "schedule", "name": "Workforce", "icon": "calendar", "desc": "Shifts & attendance"},
        {"id": "training", "name": "Training", "icon": "book-open", "desc": "Courses & certifications"},
        {"id": "recognition", "name": "Recognition", "icon": "award", "desc": "Employee awards"},
        {"id": "labour", "name": "Labour Relations", "icon": "shield", "desc": "Unions & grievances"},
    ]},
    {"category": "Finance", "modules": [
        {"id": "accounting", "name": "Accounting", "icon": "bar-chart-2", "desc": "GL, AP/AR"},
        {"id": "tax", "name": "Tax", "icon": "file-text", "desc": "HST/GST, corp tax"},
        {"id": "insurance", "name": "Insurance", "icon": "umbrella", "desc": "Claims & renewals"},
        {"id": "treasury", "name": "Treasury", "icon": "trending-up", "desc": "Banking & loans"},
        {"id": "billing", "name": "Billing", "icon": "dollar-sign", "desc": "Invoices & payments"},
        {"id": "procurement", "name": "Procurement", "icon": "shopping-cart", "desc": "Purchase orders"},
    ]},
    {"category": "Sales & Customers", "modules": [
        {"id": "crm", "name": "CRM", "icon": "user-check", "desc": "Customer records"},
        {"id": "sales", "name": "Sales", "icon": "trending-up", "desc": "Pipeline & leads"},
        {"id": "pos", "name": "Point of Sale", "icon": "shopping-bag", "desc": "Retail & restaurant"},
        {"id": "marketing", "name": "Marketing", "icon": "send", "desc": "Campaigns & reviews"},
        {"id": "portal", "name": "Customer Portal", "icon": "globe", "desc": "Self-serve access"},
        {"id": "events", "name": "Events", "icon": "calendar", "desc": "Bookings & catering"},
    ]},
    {"category": "Operations", "modules": [
        {"id": "tickets", "name": "Job Tickets", "icon": "clipboard", "desc": "Work orders"},
        {"id": "inventory", "name": "Inventory", "icon": "package", "desc": "Stock & barcodes"},
        {"id": "fleet", "name": "Fleet", "icon": "truck", "desc": "GPS, fuel, drivers"},
        {"id": "projects", "name": "Projects", "icon": "git-branch", "desc": "Gantt & milestones"},
        {"id": "facilities", "name": "Facilities", "icon": "home", "desc": "Assets & maintenance"},
        {"id": "isp", "name": "ISP Ops", "icon": "wifi", "desc": "Provisioning & outages"},
        {"id": "property", "name": "Property Mgmt", "icon": "key", "desc": "Tenants & leases"},
        {"id": "repair", "name": "Repair Shop", "icon": "tool", "desc": "Device intake & parts"},
        {"id": "drone", "name": "Drone Ops", "icon": "navigation", "desc": "Flights & missions"},
    ]},
    {"category": "Compliance & Safety", "modules": [
        {"id": "safety", "name": "Health & Safety", "icon": "alert-triangle", "desc": "Incidents & PPE"},
        {"id": "legal", "name": "Legal", "icon": "book", "desc": "Contracts & cases"},
        {"id": "govt", "name": "Govt Compliance", "icon": "flag", "desc": "Federal & provincial"},
        {"id": "emergency", "name": "Emergency", "icon": "alert-octagon", "desc": "Crisis & continuity"},
        {"id": "soc", "name": "Security Ops", "icon": "video", "desc": "Cameras & access"},
        {"id": "documents", "name": "Documents", "icon": "folder", "desc": "Contracts & files"},
    ]},
    {"category": "Communications", "modules": [
        {"id": "chat", "name": "Chat", "icon": "message-circle", "desc": "Team & announcements"},
        {"id": "knowledge", "name": "Knowledge Base", "icon": "book-open", "desc": "SOPs & wiki"},
        {"id": "vendor", "name": "Vendor Portal", "icon": "briefcase", "desc": "Contractors & suppliers"},
    ]},
    {"category": "Intelligence", "modules": [
        {"id": "bi", "name": "Business Intel", "icon": "pie-chart", "desc": "KPIs & forecasts"},
        {"id": "gis", "name": "GIS & Maps", "icon": "map", "desc": "Routes & coverage"},
        {"id": "ai", "name": "AI Command", "icon": "cpu", "desc": "AI assistants"},
    ]},
    {"category": "IT & Future", "modules": [
        {"id": "it", "name": "IT & Cloud", "icon": "server", "desc": "Devices & backups"},
        {"id": "security", "name": "Cybersecurity", "icon": "lock", "desc": "MFA & audit"},
        {"id": "iot", "name": "IoT", "icon": "radio", "desc": "Smart sensors"},
        {"id": "wallet", "name": "Digital Wallet", "icon": "credit-card", "desc": "Employee IDs"},
    ]},
]
