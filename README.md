# Farmit - Enterprise Multi-Tenant SaaS Farm Management Platform

> **A production-ready, scalable farm management platform with advanced data lifecycle management**

FarmIt is a comprehensive **multi-tenant SaaS platform** designed for modern farm operations. Manage animals, health records, breeding programs, feed inventory, and commercial activities with enterprise-grade security and performance.

##  What Makes FarmIt Unique

###  True Multi-Tenancy
- **Complete data isolation**: Each organization operates in a secure, isolated environment
- **Organization-based architecture**: Perfect for farm businesses of all sizes
- **Unlimited scalability**: Support thousands of customers on a single deployment
- **Zero cross-tenant data leakage**: Security validated at every query level

###  Flexible Subscription Management
- **Four pricing tiers**: From free trial to enterprise solutions
- **Automatic limit enforcement**: Resource usage controlled by subscription plan
- **Self-service upgrades**: Customers can upgrade anytime
- **Usage analytics**: Real-time monitoring of resource consumption

###  Intelligent Data Lifecycle Management

FarmIt implements a **two-tier data architecture** for optimal performance and cost efficiency:

#### Active Data Layer (Neon DB)
- **Primary database**: Current year operational data
- **High performance**: Serverless PostgreSQL with instant scaling
- **Real-time operations**: All daily farm activities run here
- **Auto-scaling**: Scales to zero when not in use, saving costs

#### Archive Layer (Supabase)
- **Long-term storage**: Historical data older than 1 year
- **Compressed format**: Data archived in optimized, compressed format
- **Cost-effective**: Significantly reduces database costs for historical data
- **Queryable archives**: Access historical data for analytics and compliance

#### Data Flow:
```
Year 1 (Active) → Neon DB (Full Access)
    ↓
Year 2+ (Archive) → Automatic Compression & Migration to Supabase
    ↓
Analytics Request → Smart Query (Neon + Supabase Combined View)
```

**Benefits**:
-  **Fast Performance**: Active data always in high-performance Neon DB
-  **Cost Savings**: Archive old data at fraction of the cost
-  **Complete Analytics**: Historical trends across all years
-  **Compliance Ready**: Long-term data retention for regulations
-  **Automatic**: Annual archival runs automatically

##  Core Features

### Farm Operations Management
- **Animal Management**: Complete lifecycle tracking from birth to sale
  - Tag numbers, breed information, pedigree tracking
  - Location management and movement history
  - Weight tracking and growth monitoring
  - Photo attachments and custom notes

- **Health Records**: Comprehensive veterinary care tracking
  - Vaccination schedules with automatic reminders
  - Treatment records and medication logs
  - Deworming schedules
  - Quarantine and illness management
  - Veterinarian notes and follow-ups

- **Breeding Management**: Optimize reproduction programs
  - Heat detection and mating records
  - Pregnancy tracking and status updates
  - Expected delivery date calculations
  - Kidding/calving records with complications tracking
  - AI (Artificial Insemination) vs natural breeding

- **Feed Inventory**: Never run out of feed supplies
  - Multi-feed type management
  - Stock level tracking with low-stock alerts
  - Consumption records by animal category
  - Supplier management
  - Cost tracking per feeding

- **Commercial Operations**: Complete financial tracking
  - Animal sales with buyer management
  - Expense categorization and tracking
  - Purchase orders and invoicing
  - Profit/loss analysis
  - Payment mode tracking

- **Staff Management**: Role-based team collaboration
  - Multiple farms per organization
  - Role-based access control (6 predefined roles)
  - Staff invitation system via email
  - Activity audit logs
  - Designation and joining date tracking

### Analytics & Reporting
- **Real-time Dashboard**: Key metrics at a glance
  - Total animals by gender and status
  - Upcoming vaccinations and treatments
  - Recent sales and expenses
  - Low stock alerts
  - Sick animal counts

- **Historical Analytics**: Multi-year insights
  - Current year from Neon DB (live data)
  - Historical years from Supabase (archived)
  - Combined view for trend analysis
  - Export capabilities for external analysis

##  Subscription Plans

###  Trial (14 Days Free)
Perfect for exploring the platform
- 1 farm
- 50 animals
- 3 staff members
- 100 MB storage
- All core features
- Email support

###  Starter - $29/month ($290/year)
Ideal for small family farms
- 1 farm
- 100 animals
- 5 staff members
- 500 MB storage
- **Mobile access**
- Sales & expense tracking
- Email support

###  Professional - $79/month ($790/year)
For growing farm businesses
- **3 farms**
- **500 animals**
- **15 staff members**
- 2 GB storage
- Mobile access
- **Advanced reports**
- **API access**
- Inventory management
- **Priority support**
- Custom fields

###  Enterprise - $199/month ($1,990/year)
Large-scale commercial operations
- **10 farms**
- **2,000 animals**
- **50 staff members**
- 10 GB storage
- Everything in Professional
- **White-labeling**
- **Dedicated support**
- **Custom integrations**
- **SLA guarantee**
- Unlimited API calls

##  Technology Stack

### Backend
- **Python 3.11+**: Modern, type-safe Python
- **Flask 3.x**: Lightweight, flexible web framework
- **SQLAlchemy 2.x**: Advanced ORM with async support
- **Flask-Login**: Secure session management
- **Flask-WTF**: Form validation with CSRF protection

### Databases
- **Neon DB (Primary)**: 
  - Serverless PostgreSQL
  - Auto-scaling, auto-suspend
  - Current year operational data
  - Sub-second query performance
  
- **Supabase (Archive)**: 
  - PostgreSQL-based storage
  - Compressed historical data (1+ years old)
  - Real-time API access
  - Built-in authentication support

### Frontend
- **Bootstrap 5**: Modern, responsive UI framework
- **Jinja2**: Template engine with inheritance
- **HTMX** (planned): Dynamic interactions without heavy JS

### Infrastructure
- **Gunicorn**: Production WSGI server
- **Redis**: Session storage and caching
- **Celery**: Background job processing
- **Nginx**: Reverse proxy and load balancing

##  Installation & Setup

### Prerequisites
```bash
- Python 3.11 or higher
- pip (Python package manager)
- Git
- Neon DB account (for production)
- Supabase account (for archival)
```

### Local Development Setup

1. **Clone the repository**:
```bash
git clone https://github.com/yourorg/farmit.git
cd farmit
```

2. **Create virtual environment**:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**:
```bash
# Create .env file
cp .env.example .env

# Edit .env with your settings
FLASK_CONFIG=development
SECRET_KEY=your-development-secret-key
NEON_DATABASE_URL=postgresql://user:pass@host/farmit_dev
```

5. **Initialize database**:
```bash
# First run automatically creates tables and seeds data
python run.py
```

6. **Access the application**:
- **Main App**: http://localhost:5000
- **Platform Admin**: http://localhost:5000/platform-admin/dashboard
- **API Docs**: http://localhost:5000/api/docs (coming soon)

### Production Deployment

#### Environment Variables
```bash
# Required
export FLASK_CONFIG=production
export SECRET_KEY=<strong-random-secret-minimum-32-chars>
export NEON_DATABASE_URL=postgresql://user:pass@neon-host/farmit_prod
export SUPABASE_DATABASE_URL=postgresql://user:pass@supabase-host/farmit_archive
export SUPABASE_KEY=<your-supabase-anon-key>

# Email (for invitations)
export MAIL_SERVER=smtp.gmail.com
export MAIL_PORT=587
export MAIL_USE_TLS=True
export MAIL_USERNAME=your-email@gmail.com
export MAIL_PASSWORD=your-app-password

# Redis (for caching and sessions)
export REDIS_URL=redis://localhost:6379/0

# Celery (for background jobs)
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Optional
export SENTRY_DSN=<your-sentry-dsn>
export LOG_LEVEL=INFO
```

#### Using Gunicorn
```bash
# Install production server
pip install gunicorn gevent

# Run with 4 workers
gunicorn -w 4 -k gevent --bind 0.0.0.0:8000 'app:create_app()' --timeout 120

# With Nginx reverse proxy (recommended)
gunicorn -w 4 -k gevent --bind 127.0.0.1:8000 'app:create_app()'
```

#### Background Worker (Celery)
```bash
# Terminal 1: Start Celery worker
celery -A app.celery worker --loglevel=info

# Terminal 2: Start Celery beat (for scheduled tasks)
celery -A app.celery beat --loglevel=info
```

#### Data Archival Cron Job
```bash
# Add to crontab for automatic yearly archival
# Runs on January 1st at 2 AM
0 2 1 1 * cd /path/to/farmit && venv/bin/python -m app.tasks.archive_data
```

##  User Access Levels

### Platform Administrator
**Access**: System-wide control
- Manage all organizations
- View platform analytics
- Extend trials, suspend accounts
- Manage subscription plans
- System health monitoring
- Revenue tracking

**Default Credentials** ( Change immediately!):
- Username: `platformadmin`
- Password: `ChangeMeInProduction123!`

### Organization Owner
**Access**: Full control over their organization
- Create and manage farms
- Invite team members
- Assign roles and permissions
- View usage statistics
- Manage subscription
- Access all data within organization

### Administrator
**Access**: Full farm management
- All farm operations
- Staff management (except owner)
- Financial records
- System settings
- Reports and analytics

### Farm Staff
**Access**: Day-to-day operations
- Add/edit animals
- Record health events
- Update breeding records
- Record feed consumption
- View dashboards

### Veterinary
**Access**: Health-focused
- View all animals
- Manage health records
- Treatments and vaccinations
- Deworming schedules
- View breeding info

### Inventory Manager
**Access**: Feed and supplies
- Manage feed inventory
- Record consumption
- Track stock levels
- Supplier management
- View expenses

### Accountant
**Access**: Financial records
- View/manage sales
- Track expenses
- Generate financial reports
- Customer management
- Payment tracking

##  Architecture Overview

### System Architecture
```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer (Nginx)                │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┴───────────────┐
     │                               │
┌────▼─────┐                   ┌────▼─────┐
│  Flask   │                   │  Flask   │
│ Instance │                   │ Instance │
│    #1    │                   │    #2    │
└────┬─────┘                   └────┬─────┘
     │                               │
     └───────────────┬───────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼────┐   ┌─────▼────┐   ┌─────▼─────┐
│ Neon DB │   │  Redis   │   │ Supabase  │
│ (Active)│   │ (Cache)  │   │ (Archive) │
└─────────┘   └──────────┘   └───────────┘
```

### Data Flow
```
User Request
    ↓
Authentication & Tenant Validation
    ↓
Check Subscription Status
    ↓
Enforce Resource Limits
    ↓
Query Active Data (Neon DB)
    ↓
If Historical Request → Query Archive (Supabase)
    ↓
Merge Results & Return
    ↓
Update Cache (Redis)
    ↓
Response to User
```

### Multi-Tenant Isolation
```
Organization A                Organization B
    ├── Farm 1                    ├── Farm 1
    │   ├── Animals               │   ├── Animals
    │   ├── Health Records        │   ├── Health Records
    │   └── Staff                 │   └── Staff
    └── Farm 2                    └── Farm 2

 No cross-organization access
 Complete data isolation
 Validated at query level
 Enforced by decorators
```

##  Security Features

### Authentication & Authorization
-  Password hashing with werkzeug (PBKDF2)
-  Session-based authentication
-  CSRF protection on all forms
-  Role-based access control (RBAC)
-  Organization-level isolation
-  Subscription validation on every request
-  Two-factor authentication (planned)
-  OAuth2 integration (planned)

### Data Protection
-  SQL injection prevention (SQLAlchemy ORM)
-  XSS protection (Jinja2 auto-escaping)
-  Secure password storage
-  Encrypted database connections
-  Audit logging for sensitive operations
-  Data encryption at rest (Neon/Supabase native)
-  Field-level encryption for PII

### Infrastructure Security
-  Environment-based configuration
-  Secret key management
-  Rate limiting (planned with Flask-Limiter)
-  IP whitelisting for admin panel
-  Security headers (CSP, HSTS, etc.)
-  Regular dependency updates
-  Vulnerability scanning

##  Performance Optimization

### Database Optimization
- Indexed columns: `organization_id`, `farm_id`, `created_at`
- Connection pooling with SQLAlchemy
- Query result caching with Redis
- Lazy loading for relationships
- Batch operations for bulk inserts
- Annual data archival to Supabase

### Caching Strategy
- **Session data**: Redis-backed sessions
- **Subscription status**: 5-minute cache
- **User permissions**: Per-request cache
- **Dashboard stats**: 1-hour cache
- **Static assets**: CDN + browser cache

### Background Processing
- Email sending (Celery)
- Data archival (scheduled task)
- Usage statistics calculation
- Subscription renewal checks
- Notification generation

##  Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

##  API Documentation

REST API available for Professional and Enterprise plans.

**Base URL**: `https://api.farmit.com/v1`

**Authentication**: API Key (Bearer token)

**Endpoints**:
```
GET    /api/v1/animals              # List animals
POST   /api/v1/animals              # Create animal
GET    /api/v1/animals/{id}         # Get animal details
PUT    /api/v1/animals/{id}         # Update animal
DELETE /api/v1/animals/{id}         # Delete animal

GET    /api/v1/health/vaccinations  # List vaccinations
POST   /api/v1/health/vaccinations  # Record vaccination

GET    /api/v1/breeding             # List breeding records
POST   /api/v1/breeding             # Create breeding record

# More endpoints documented at /api/docs
```

##  Roadmap

###  Phase 1: Foundation (Completed)
- [x] Multi-tenant architecture
- [x] Subscription management
- [x] Organization signup & onboarding
- [x] User invitation system
- [x] Platform admin dashboard
- [x] Core farm operations (animals, health, breeding, feed, commercial)
- [x] Role-based access control
- [x] Neon DB + Supabase integration

###  Phase 2: Enhancement (In Progress - Q4 2026)
- [ ] Email notification system
- [ ] Payment gateway (Stripe integration)
- [ ] Mobile-responsive templates
- [ ] REST API with OpenAPI docs
- [ ] Data archival automation
- [ ] Advanced analytics dashboard
- [ ] Export functionality (PDF, Excel)

###  Phase 3: Scale (Q1-Q2 2027)
- [ ] Mobile apps (iOS & Android)
- [ ] Real-time notifications (WebSocket)
- [ ] Webhook system for integrations
- [ ] Custom report builder
- [ ] Multi-language support (i18n)
- [ ] Two-factor authentication
- [ ] OAuth2 provider integration

###  Phase 4: Enterprise (Q3-Q4 2027)
- [ ] White-labeling support
- [ ] Custom domain per organization
- [ ] Advanced AI insights
- [ ] IoT device integration (sensors, scales)
- [ ] Blockchain for supply chain
- [ ] Marketplace for third-party apps
- [ ] GraphQL API

##  Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

##  License

**Proprietary License** - All rights reserved.

This software is licensed for commercial use only. Unauthorized copying, modification, or distribution is prohibited.

##  Support & Contact

### Support Channels
- **Trial/Starter**: Email support (support@farmit.example.com)
- **Professional**: Priority email + chat support
- **Enterprise**: Dedicated support team + phone support

### Response Times
- Trial/Starter: 48 hours
- Professional: 12 hours
- Enterprise: 2 hours (SLA guaranteed)

### Resources
- Documentation: https://docs.farmit.example.com
- Status Page: https://status.farmit.example.com
- Community Forum: https://community.farmit.example.com

---

##  Why Choose FarmIt?

 **Production-Ready**: Built with enterprise standards from day one  
 **Secure by Design**: Multi-layered security with complete tenant isolation  
 **Scalable**: Handles 1 customer or 10,000 customers  
 **Cost-Effective**: Smart data archival reduces infrastructure costs  
 **Modern Stack**: Latest technologies for performance and reliability  
 **Global Ready**: Multi-currency, multi-language support (coming soon)  
 **Analytics-First**: Make data-driven decisions with comprehensive reports  
 **Customer-Centric**: Self-service platform with guided onboarding  

---

**Version**: 2.0.0 (SaaS Multi-Tenant with Data Lifecycle Management)  
**Last Updated**: September 2026  
**Built with**: ❤️ by the FarmIt Team

**Powered by**: Flask • SQLAlchemy • Neon DB • Supabase • PostgreSQL
