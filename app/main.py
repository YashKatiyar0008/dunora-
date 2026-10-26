"""Dunora MVP: tenant-scoped accounts receivable workflows.

Note: billing/email integrations require secrets. Demo-only events are never passed
as a real payment or email delivery. Money is represented in minor units (paise).
"""
import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent
DB_URL = os.getenv('DATABASE_URL', 'sqlite:///./dunora.db')
if DB_URL.startswith('postgres://'):
    DB_URL = 'postgresql+psycopg://' + DB_URL[len('postgres://'):]
if DB_URL.startswith('postgresql://'):
    DB_URL = 'postgresql+psycopg://' + DB_URL[len('postgresql://'):]
engine = create_engine(DB_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite') else {})
DB = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Org(Base):
    __tablename__ = 'orgs'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    plan: Mapped[str] = mapped_column(String(20), default='starter')
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seeded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('orgs.id'), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default='owner')

class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Customer(Base):
    __tablename__ = 'customers'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('orgs.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254))
    __table_args__ = (UniqueConstraint('org_id', 'email', name='uq_org_customer_email'),)

class Invoice(Base):
    __tablename__ = 'invoices'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('orgs.id'), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    number: Mapped[str] = mapped_column(String(90))
    amount_minor: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    issued_date: Mapped[date] = mapped_column(Date)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('org_id', 'number', name='uq_org_invoice_number'),)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('orgs.id'), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'))
    amount_minor: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(140))
    paid_on: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(30), default='manual')
    __table_args__ = (UniqueConstraint('org_id', 'reference', name='uq_org_payment_ref'),)

class Draft(Base):
    __tablename__ = 'drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('orgs.id'), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'))
    subject: Mapped[str] = mapped_column(String(220))
    body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(25), default='draft')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Audit(Base):
    __tablename__ = 'audits'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('orgs.id'), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)
app = FastAPI(title='Dunora API', version='1.0.0', docs_url='/api/docs', redoc_url=None)
COOKIE = 'dunora_session'
HTTPS_ONLY = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
APP_URL = (os.getenv('APP_URL') or os.getenv('RENDER_EXTERNAL_URL', '')).rstrip('/')

@app.middleware('http')
async def same_origin_guard(request: Request, call_next):
    if request.url.path.startswith('/api/') and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        origin = request.headers.get('origin')
        if origin:
            # Match scheme and host, or a configured canonical domain.
            expected = APP_URL or str(request.base_url).rstrip('/')
            if origin.rstrip('/') != expected:
                return PlainTextResponse('Cross-origin write rejected', status_code=403)
    return await call_next(request)

@app.middleware('http')
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response

def get_db():
    with DB() as db:
        yield db

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240_000)
    return f'{salt.hex()}:{digest.hex()}'

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(':')
        calculated = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 240_000)
        return hmac.compare_digest(calculated, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def session_user(request: Request, db: Session = Depends(get_db)) -> User:
    cookie = request.cookies.get(COOKIE)
    if not cookie:
        raise HTTPException(401, 'Please sign in')
    sess = db.scalar(select(LoginSession).where(LoginSession.token_hash == hashlib.sha256(cookie.encode()).hexdigest(), LoginSession.expires_at > datetime.utcnow()))
    if not sess:
        raise HTTPException(401, 'Session expired')
    user = db.get(User, sess.user_id)
    if not user:
        raise HTTPException(401, 'User not found')
    return user

def login_user(response: Response, db: Session, user: User):
    token = secrets.token_urlsafe(36)
    db.add(LoginSession(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.utcnow() + timedelta(days=7)))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=HTTPS_ONLY, samesite='strict', max_age=604800, path='/')

def log(db: Session, user: User, action: str, detail: str):
    db.add(Audit(org_id=user.org_id, user_id=user.id, action=action, detail=detail[:1000]))

def cents(value: str | int | Decimal) -> int:
    try:
        amt = Decimal(str(value))
        if not amt.is_finite() or amt <= 0 or amt > 1_000_000_000:
            raise ValueError('Amount must be positive and finite')
        minor = amt * 100
        if minor != minor.quantize(Decimal('1')):
            raise ValueError('Use at most two decimal places')
        return int(minor)
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid monetary amount')

def customer_for(db: Session, org_id: int, name: str, email: str) -> Customer:
    email = email.strip().lower()
    customer = db.scalar(select(Customer).where(Customer.org_id == org_id, Customer.email == email))
    if not customer:
        customer = Customer(org_id=org_id, name=name.strip(), email=email)
        db.add(customer)
        db.flush()
    return customer

def invoice_for(db: Session, user: User, invoice_id: int) -> Invoice:
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == user.org_id))
    if not invoice:
        raise HTTPException(404, 'Invoice not found')
    return invoice

def paid_map(db: Session, org_id: int):
    rows = db.execute(select(Payment.invoice_id, func.sum(Payment.amount_minor)).where(Payment.org_id == org_id).group_by(Payment.invoice_id)).all()
    return {i: int(v) for i, v in rows}

def calculate_risk(invoice: Invoice, outstanding: int, today=None) -> dict:
    today = today or date.today()
    days_late = (today - invoice.due_date).days
    if outstanding <= 0:
        return {'score': 0, 'level': 'settled', 'factors': ['Fully paid'], 'days_late': max(days_late, 0)}
    if invoice.disputed:
        return {'score': 0, 'level': 'disputed', 'factors': ['Collection paused: invoice disputed'], 'days_late': max(days_late, 0)}
    score = 12
    factors = ['Open balance is unpaid']
    if days_late > 0:
        score += min(50, days_late * 2)
        factors.append(f'{days_late} day(s) past due')
    if outstanding >= 100_000_00:
        score += 20
        factors.append('Large outstanding balance (₹1,00,000+)')
    elif outstanding >= 25_000_00:
        score += 10
        factors.append('Significant balance (₹25,000+)')
    if days_late <= 0:
        factors.append(f'Due in {abs(days_late)} day(s)' if days_late < 0 else 'Due today')
    score = min(score, 100)
    return {'score': score, 'level': 'critical' if score >= 70 else 'high' if score >= 45 else 'watch' if score >= 25 else 'low', 'factors': factors, 'days_late': max(days_late, 0)}

def serialized_invoice(db: Session, invoice: Invoice, paid: dict):
    customer = db.get(Customer, invoice.customer_id)
    paid_minor = paid.get(invoice.id, 0)
    outstanding = max(0, invoice.amount_minor - paid_minor)
    return {'id': invoice.id, 'number': invoice.number, 'customer': customer.name, 'email': customer.email,
            'amount_minor': invoice.amount_minor, 'paid_minor': paid_minor, 'outstanding_minor': outstanding,
            'issued_date': invoice.issued_date.isoformat(), 'due_date': invoice.due_date.isoformat(),
            'disputed': invoice.disputed, 'note': invoice.note,
            'status': 'paid' if outstanding == 0 else 'disputed' if invoice.disputed else 'overdue' if invoice.due_date < date.today() else 'open',
            'risk': calculate_risk(invoice, outstanding)}

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class Register(Credentials):
    company: str = Field(min_length=2, max_length=160)

@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'dunora', 'version': '1.0.0'}

@app.post('/api/auth/register')
def register(data: Register, response: Response, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'Email already registered')
    org = Org(name=data.company.strip(), plan='starter')
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    login_user(response, db, user)
    return {'ok': True, 'company': org.name}

@app.post('/api/auth/login')
def login(data: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, 'Invalid email or password')
    login_user(response, db, user)
    return {'ok': True}

@app.post('/api/auth/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    cookie = request.cookies.get(COOKIE)
    if cookie:
        current = db.scalar(select(LoginSession).where(LoginSession.token_hash == hashlib.sha256(cookie.encode()).hexdigest()))
        if current:
            db.delete(current)
            db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}

@app.get('/api/me')
def me(user: User = Depends(session_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    return {'email': user.email, 'role': user.role, 'company': org.name, 'plan': org.plan, 'org_id': user.org_id, 'seeded': org.seeded}

class InvoiceIn(BaseModel):
    number: str = Field(min_length=2, max_length=90)
    customer: str = Field(min_length=2, max_length=160)
    email: EmailStr
    amount: str
    due_date: date
    issued_date: date | None = None

@app.post('/api/invoices')
def add_invoice(data: InvoiceIn, user: User = Depends(session_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    if org.plan == 'starter' and (db.scalar(select(func.count(Invoice.id)).where(Invoice.org_id == user.org_id)) or 0) >= 25:
        raise HTTPException(403, 'Starter plan supports up to 25 invoices. Upgrade to continue.')
    if db.scalar(select(Invoice.id).where(Invoice.org_id == user.org_id, Invoice.number == data.number.strip())):
        raise HTTPException(409, 'Invoice number already exists')
    try:
        amount_minor = cents(data.amount)
    except ValueError as error:
        raise HTTPException(422, str(error))
    issued = data.issued_date or date.today()
    if data.due_date < issued - timedelta(days=3650):
        raise HTTPException(422, 'Invalid date range')
    customer = customer_for(db, user.org_id, data.customer, str(data.email))
    inv = Invoice(org_id=user.org_id, customer_id=customer.id, number=data.number.strip(), amount_minor=amount_minor, due_date=data.due_date, issued_date=issued)
    db.add(inv)
    db.flush()
    log(db, user, 'invoice.created', f'{inv.number} for {customer.name}, ₹{amount_minor / 100:.2f}')
    db.commit()
    return {'ok': True, 'id': inv.id}

@app.get('/api/invoices')
def invoices(user: User = Depends(session_user), db: Session = Depends(get_db)):
    invs = db.scalars(select(Invoice).where(Invoice.org_id == user.org_id).order_by(Invoice.due_date.asc(), Invoice.id.desc())).all()
    paid = paid_map(db, user.org_id)
    return [serialized_invoice(db, i, paid) for i in invs]

@app.get('/api/invoices/{invoice_id}')
def invoice_detail(invoice_id: int, user: User = Depends(session_user), db: Session = Depends(get_db)):
    inv = invoice_for(db, user, invoice_id)
    payments = db.scalars(select(Payment).where(Payment.org_id == user.org_id, Payment.invoice_id == invoice_id).order_by(Payment.id.desc())).all()
    drafts = db.scalars(select(Draft).where(Draft.org_id == user.org_id, Draft.invoice_id == invoice_id).order_by(Draft.id.desc())).all()
    return {'invoice': serialized_invoice(db, inv, paid_map(db, user.org_id)),
            'payments': [{'id': p.id, 'amount_minor': p.amount_minor, 'reference': p.reference, 'paid_on': p.paid_on.isoformat(), 'source': p.source} for p in payments],
            'drafts': [{'id': d.id, 'subject': d.subject, 'body': d.body, 'state': d.state} for d in drafts]}

class PaymentIn(BaseModel):
    amount: str
    reference: str = Field(min_length=2, max_length=140)
    paid_on: date | None = None

@app.post('/api/invoices/{invoice_id}/payments')
def record_payment(invoice_id: int, data: PaymentIn, user: User = Depends(session_user), db: Session = Depends(get_db)):
    inv = invoice_for(db, user, invoice_id)
    try:
        amount = cents(data.amount)
    except ValueError as error:
        raise HTTPException(422, str(error))
    if db.scalar(select(Payment.id).where(Payment.org_id == user.org_id, Payment.reference == data.reference.strip())):
        raise HTTPException(409, 'Payment reference already recorded')
    outstanding = inv.amount_minor - paid_map(db, user.org_id).get(inv.id, 0)
    if amount > outstanding:
        raise HTTPException(422, 'Payment exceeds outstanding balance')
    db.add(Payment(org_id=user.org_id, invoice_id=inv.id, amount_minor=amount, reference=data.reference.strip(), paid_on=data.paid_on or date.today(), source='manual'))
    log(db, user, 'payment.recorded', f'{inv.number}: ₹{amount / 100:.2f}, reference {data.reference.strip()}')
    db.commit()
    return {'ok': True, 'remaining_minor': outstanding - amount}

class DisputeIn(BaseModel):
    disputed: bool
    note: str = Field(default='', max_length=1000)

@app.post('/api/invoices/{invoice_id}/dispute')
def mark_dispute(invoice_id: int, data: DisputeIn, user: User = Depends(session_user), db: Session = Depends(get_db)):
    inv = invoice_for(db, user, invoice_id)
    inv.disputed = data.disputed
    inv.note = data.note
    log(db, user, 'invoice.dispute_changed', f'{inv.number}: disputed={data.disputed}; note={data.note[:150]}')
    db.commit()
    return {'ok': True}

@app.post('/api/invoices/import')
async def import_csv(file: UploadFile = File(...), user: User = Depends(session_user), db: Session = Depends(get_db)):
    raw = await file.read(1_500_001)
    if len(raw) > 1_500_000:
        raise HTTPException(413, 'CSV exceeds 1.5MB limit')
    try:
        content = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        required = {'number', 'customer', 'email', 'amount', 'due_date'}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise HTTPException(422, 'Expected CSV headers: number,customer,email,amount,due_date[,issued_date]')
        rows = list(reader)
        if not rows or len(rows) > 500:
            raise HTTPException(422, 'CSV must contain 1–500 rows')
        results = []
        for row_no, row in enumerate(rows, start=2):
            try:
                parsed = InvoiceIn(**{k: (v or '').strip() for k, v in row.items() if k})
                number = parsed.number.strip()
                if db.get(Org, user.org_id).plan == 'starter' and (db.scalar(select(func.count(Invoice.id)).where(Invoice.org_id == user.org_id)) or 0) >= 25:
                    raise ValueError('Starter plan invoice limit reached (25)')
                if db.scalar(select(Invoice.id).where(Invoice.org_id == user.org_id, Invoice.number == number)):
                    raise ValueError('Duplicate invoice number')
                amount = cents(parsed.amount)
                customer = customer_for(db, user.org_id, parsed.customer, str(parsed.email))
                db.add(Invoice(org_id=user.org_id, customer_id=customer.id, number=number, amount_minor=amount, due_date=parsed.due_date, issued_date=parsed.issued_date or date.today()))
                db.flush()
                results.append({'row': row_no, 'status': 'imported'})
            except Exception as ex:
                results.append({'row': row_no, 'status': 'skipped', 'reason': str(ex)[:180]})
        imported = sum(1 for r in results if r['status'] == 'imported')
        log(db, user, 'invoice.csv_imported', f'Imported {imported} of {len(rows)} rows')
        db.commit()
        return {'imported': imported, 'skipped': len(rows) - imported, 'results': results}
    except UnicodeDecodeError:
        raise HTTPException(422, 'CSV must be UTF-8')

@app.get('/api/summary')
def summary(user: User = Depends(session_user), db: Session = Depends(get_db)):
    invs = db.scalars(select(Invoice).where(Invoice.org_id == user.org_id)).all()
    paid = paid_map(db, user.org_id)
    mapped = [serialized_invoice(db, i, paid) for i in invs]
    open_invoices = [i for i in mapped if i['outstanding_minor'] > 0]
    overdue = [i for i in open_invoices if i['status'] == 'overdue']
    potential = sorted([i for i in open_invoices if not i['disputed']], key=lambda i: (i['risk']['score'], i['outstanding_minor']), reverse=True)
    payments = db.scalars(select(Payment).where(Payment.org_id == user.org_id)).all()
    months = []
    current = date.today()
    for delta in reversed(range(6)):
        yy = current.year
        mm = current.month - delta
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append({'label': date(yy, mm, 1).strftime('%b'), 'year': yy, 'month': mm,
                       'amount_minor': sum(p.amount_minor for p in payments if p.paid_on.year == yy and p.paid_on.month == mm)})
    return {'outstanding_minor': sum(i['outstanding_minor'] for i in mapped),
            'overdue_minor': sum(i['outstanding_minor'] for i in overdue),
            'collected_minor': sum(p.amount_minor for p in payments),
            'at_risk_minor': sum(i['outstanding_minor'] for i in open_invoices if i['risk']['score'] >= 45),
            'open_count': len(open_invoices), 'overdue_count': len(overdue),
            'disputed_count': sum(i['disputed'] for i in open_invoices),
            'priority': potential[:5], 'months': months}

def reminder_for(invoice: Invoice, customer: Customer, remaining: int):
    overdue = (date.today() - invoice.due_date).days
    if overdue > 0:
        subject = f'Friendly follow-up · Invoice {invoice.number}'
        body = (f'Hello {customer.name},\n\nI hope you are well. This is a friendly follow-up about invoice {invoice.number}, '
                f'which was due on {invoice.due_date.isoformat()}. Our records show an outstanding balance of '
                f'INR {remaining / 100:,.2f}.\n\nCould you confirm the expected payment date or let us know if '
                'there is any issue we can help resolve?\n\nThank you,\nAccounts team')
    else:
        subject = f'Upcoming due date · Invoice {invoice.number}'
        body = (f'Hello {customer.name},\n\nA quick note that invoice {invoice.number} for INR {remaining / 100:,.2f} '
                f'is due on {invoice.due_date.isoformat()}. Please let us know if you need any information.\n\nThank you,\nAccounts team')
    return subject, body

@app.get('/api/workbench')
def workbench(user: User = Depends(session_user), db: Session = Depends(get_db)):
    invs = db.scalars(select(Invoice).where(Invoice.org_id == user.org_id)).all()
    paid = paid_map(db, user.org_id)
    results = [serialized_invoice(db, inv, paid) for inv in invs if inv.amount_minor > paid.get(inv.id, 0) and not inv.disputed]
    results.sort(key=lambda i: (i['risk']['score'], i['outstanding_minor']), reverse=True)
    drafts = db.scalars(select(Draft).where(Draft.org_id == user.org_id).order_by(Draft.id.desc())).all()
    return {'recommendations': results, 'drafts': [{'id': d.id, 'invoice_id': d.invoice_id, 'subject': d.subject, 'body': d.body, 'state': d.state, 'created_at': d.created_at.isoformat()} for d in drafts]}

@app.post('/api/invoices/{invoice_id}/draft')
def create_draft(invoice_id: int, user: User = Depends(session_user), db: Session = Depends(get_db)):
    inv = invoice_for(db, user, invoice_id)
    remaining = inv.amount_minor - paid_map(db, user.org_id).get(inv.id, 0)
    if remaining <= 0 or inv.disputed:
        raise HTTPException(422, 'Paid or disputed invoices are not eligible for reminders')
    customer = db.get(Customer, inv.customer_id)
    subject, body = reminder_for(inv, customer, remaining)
    draft = Draft(org_id=user.org_id, invoice_id=inv.id, subject=subject, body=body)
    db.add(draft)
    db.flush()
    log(db, user, 'reminder.drafted', f'{inv.number}: draft #{draft.id} awaiting human approval')
    db.commit()
    return {'id': draft.id, 'subject': subject, 'body': body, 'state': draft.state}

class DraftEdit(BaseModel):
    subject: str = Field(min_length=3, max_length=220)
    body: str = Field(min_length=10, max_length=5000)

@app.post('/api/drafts/{draft_id}/edit')
def edit_draft(draft_id: int, data: DraftEdit, user: User = Depends(session_user), db: Session = Depends(get_db)):
    draft = db.scalar(select(Draft).where(Draft.id == draft_id, Draft.org_id == user.org_id))
    if not draft: raise HTTPException(404, 'Draft not found')
    if draft.state != 'draft': raise HTTPException(409, 'Only drafts can be edited')
    draft.subject, draft.body = data.subject, data.body
    log(db, user, 'reminder.edited', f'draft #{draft.id}')
    db.commit()
    return {'ok': True}

@app.post('/api/drafts/{draft_id}/send')
def send_draft(draft_id: int, user: User = Depends(session_user), db: Session = Depends(get_db)):
    draft = db.scalar(select(Draft).where(Draft.id == draft_id, Draft.org_id == user.org_id))
    if not draft: raise HTTPException(404, 'Draft not found')
    if draft.state != 'draft': raise HTTPException(409, 'Draft already processed')
    inv = invoice_for(db, user, draft.invoice_id)
    if inv.disputed or inv.amount_minor <= paid_map(db, user.org_id).get(inv.id, 0):
        raise HTTPException(422, 'Invoice is no longer eligible for a reminder')
    customer = db.get(Customer, inv.customer_id)
    host = os.getenv('SMTP_HOST')
    sender = os.getenv('SMTP_FROM')
    if host and sender:
        message = EmailMessage()
        message['From'], message['To'], message['Subject'] = sender, customer.email, draft.subject
        message.set_content(draft.body)
        try:
            with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=12) as smtp:
                smtp.starttls()
                smtp.login(os.getenv('SMTP_USER', ''), os.getenv('SMTP_PASSWORD', ''))
                smtp.send_message(message)
        except Exception:
            raise HTTPException(502, 'SMTP delivery failed; draft remains unsent')
        draft.state = 'sent'
    else:
        draft.state = 'simulated'  # never represented as actual delivery
    log(db, user, 'reminder.' + draft.state, f'{inv.number} -> {customer.email}; draft #{draft.id}')
    db.commit()
    return {'ok': True, 'state': draft.state, 'email': customer.email}

@app.get('/api/audit')
def audit(user: User = Depends(session_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Audit).where(Audit.org_id == user.org_id).order_by(Audit.id.desc()).limit(100)).all()
    return [{'id': a.id, 'action': a.action, 'detail': a.detail, 'created_at': a.created_at.isoformat() + 'Z'} for a in rows]

@app.get('/api/audit/export')
def audit_export(user: User = Depends(session_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Audit).where(Audit.org_id == user.org_id).order_by(Audit.id)).all()
    buff = io.StringIO()
    writer = csv.writer(buff)
    writer.writerow(['event_id', 'utc_timestamp', 'action', 'detail'])
    for a in rows:
        # csv injection guard for spreadsheet viewers
        detail = a.detail
        if detail.lstrip().startswith(('=', '+', '-', '@')): detail = "'" + detail
        writer.writerow([a.id, a.created_at.isoformat(), a.action, detail])
    return Response(buff.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="dunora-audit.csv"'})

@app.post('/api/demo/seed')
def seed_demo(user: User = Depends(session_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    if org.seeded or db.scalar(select(Invoice.id).where(Invoice.org_id == user.org_id)):
        raise HTTPException(409, 'Demo data can only be loaded into an empty workspace once')
    today = date.today()
    demo = [
        ('INV-1001', 'Northstar Creative', 'finance@northstar.example', '145000.00', -35, '18000.00'),
        ('INV-1002', 'Atlas Components', 'accounts@atlas.example', '87000.00', -22, '0'),
        ('INV-1003', 'Meridian Works', 'billing@meridian.example', '62000.00', -8, '12000.00'),
        ('INV-1004', 'Bluehaven Studio', 'payables@bluehaven.example', '124000.00', 10, '0'),
        ('INV-1005', 'Aster Retail', 'billing@aster.example', '36500.00', -18, '36500.00'),
        ('INV-1006', 'Summit Logistics', 'accounts@summit.example', '220000.00', -49, '40000.00'),
        ('INV-1007', 'Copperline Labs', 'finance@copperline.example', '28500.00', 6, '0'),
        ('INV-1008', 'Crescent Foods', 'ap@crescent.example', '97500.00', -5, '0'),
    ]
    for number, name, email, amount, offset, paid in demo:
        customer = customer_for(db, user.org_id, name, email)
        invoice = Invoice(org_id=user.org_id, customer_id=customer.id, number=number, amount_minor=cents(amount), due_date=today + timedelta(days=offset), issued_date=today + timedelta(days=offset - 30))
        db.add(invoice)
        db.flush()
        if Decimal(paid) > 0:
            db.add(Payment(org_id=user.org_id, invoice_id=invoice.id, amount_minor=cents(paid), reference=f'DEMO-PAY-{number}', paid_on=today - timedelta(days=3 if offset < 0 else 25), source='demo_seed'))
    # Settled historical records make the collections trend meaningful for a demo.
    for index, days_ago in enumerate((153, 121, 89, 61, 31), start=1):
        customer = customer_for(db, user.org_id, f'Historical Account {index}', f'history{index}@example.invalid')
        amount = 26000_00 + index * 13000_00
        pay_date = today - timedelta(days=days_ago)
        invoice = Invoice(org_id=user.org_id, customer_id=customer.id, number=f'INV-H{index:03d}',
                          amount_minor=amount, due_date=pay_date - timedelta(days=3),
                          issued_date=pay_date - timedelta(days=28))
        db.add(invoice)
        db.flush()
        db.add(Payment(org_id=user.org_id, invoice_id=invoice.id, amount_minor=amount,
                       reference=f'DEMO-HIST-{index}', paid_on=pay_date, source='demo_seed'))
    org.seeded = True
    log(db, user, 'demo.seeded', 'Loaded 13 fictional invoices with historical payments. All data is synthetic.')
    db.commit()
    return {'ok': True, 'invoices': 13}

# One-click isolated tour for judges. Switch off with ALLOW_PUBLIC_DEMO=false.
_demo_visits = {}

@app.post('/api/auth/demo')
def demo_login(request: Request, response: Response, db: Session = Depends(get_db)):
    if os.getenv('ALLOW_PUBLIC_DEMO', 'true').lower() != 'true':
        raise HTTPException(404, 'Demo sign-up disabled')
    ip = request.client.host if request.client else 'unknown'
    now = datetime.utcnow()
    recent = [t for t in _demo_visits.get(ip, []) if now - t < timedelta(hours=1)]
    if len(recent) >= 10:
        raise HTTPException(429, 'Too many demo workspaces; try again later')
    recent.append(now)
    _demo_visits[ip] = recent
    suffix = secrets.token_hex(6)
    org = Org(name='Acme Studio · Demo', plan='growth')
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email=f'judge-{suffix}@demo.dunora.local', password_hash=hash_password(secrets.token_urlsafe(24)))
    db.add(user)
    db.flush()
    seed_demo(user, db)
    login_user(response, db, user)
    return {'ok': True, 'demo': True}

@app.get('/api/billing')
def billing(user: User = Depends(session_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    return {'plan': org.plan, 'provider': 'stripe' if os.getenv('STRIPE_SECRET_KEY') else 'not_configured',
            'plans': [{'id': 'starter', 'name': 'Starter', 'price_inr': 0, 'features': ['25 invoices', 'Manual reconciliation', 'Transparent risk scoring']},
                      {'id': 'growth', 'name': 'Growth', 'price_inr': 1499, 'features': ['Unlimited invoices', 'Reminder workflows', 'CSV imports and audit export']},
                      {'id': 'scale', 'name': 'Scale', 'price_inr': 4999, 'features': ['Advanced integrations', 'Team governance roadmap', 'Priority support']}],
            'configured': bool(os.getenv('STRIPE_SECRET_KEY') and os.getenv('STRIPE_PRICE_GROWTH'))}

class CheckoutIn(BaseModel):
    plan: str

@app.post('/api/billing/checkout')
def checkout(data: CheckoutIn, user: User = Depends(session_user), db: Session = Depends(get_db)):
    if data.plan not in ('growth', 'scale'):
        raise HTTPException(422, 'Choose Growth or Scale')
    key = os.getenv('STRIPE_SECRET_KEY')
    price = os.getenv('STRIPE_PRICE_GROWTH' if data.plan == 'growth' else 'STRIPE_PRICE_SCALE')
    if not key or not price or not APP_URL:
        raise HTTPException(503, 'Checkout not configured; add Stripe price ID, secret key and APP_URL')
    org = db.get(Org, user.org_id)
    params = [('mode', 'subscription'), ('line_items[0][price]', price), ('line_items[0][quantity]', '1'),
              ('success_url', APP_URL + '/?billing=success'), ('cancel_url', APP_URL + '/?billing=cancel'),
              ('client_reference_id', str(org.id)), ('metadata[org_id]', str(org.id)), ('metadata[plan]', data.plan),
              ('subscription_data[metadata][org_id]', str(org.id)), ('subscription_data[metadata][plan]', data.plan),
              ('customer_email', user.email)]
    req = urllib.request.Request('https://api.stripe.com/v1/checkout/sessions', data=urllib.parse.urlencode(params).encode(),
                                 headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            payload = json.load(res)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        raise HTTPException(502, 'Stripe checkout unavailable; verify billing configuration')
    log(db, user, 'billing.checkout_started', f'Plan {data.plan}; Stripe session {payload["id"]}')
    db.commit()
    return {'url': payload['url']}

def verify_stripe_signature(raw: bytes, header: str, secret: str) -> bool:
    components = dict(p.split('=', 1) for p in header.split(',') if '=' in p)
    try:
        stamp = int(components.get('t', '0'))
    except ValueError:
        return False
    if abs(datetime.now(timezone.utc).timestamp() - stamp) > 300:
        return False
    expected = hmac.new(secret.encode(), f'{stamp}.'.encode() + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, val.split('=', 1)[1]) for val in header.split(',') if val.startswith('v1='))

@app.post('/api/webhooks/stripe')
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    raw = await request.body()
    if not secret or not verify_stripe_signature(raw, request.headers.get('stripe-signature', ''), secret):
        raise HTTPException(400, 'Invalid webhook signature')
    event = json.loads(raw)
    data = event.get('data', {}).get('object', {})
    kind = event.get('type')
    if kind == 'checkout.session.completed' and data.get('mode') == 'subscription' and data.get('payment_status') in ('paid', 'no_payment_required'):
        try:
            org_id = int(data['client_reference_id'])
        except (ValueError, KeyError, TypeError):
            return {'received': True}
        org = db.get(Org, org_id)
        plan = data.get('metadata', {}).get('plan')
        if org and plan in ('growth', 'scale'):
            # Production must also process subscription status changes; no entitlement on unverified checkout redirect.
            org.plan = plan
            org.stripe_customer_id = data.get('customer')
            org.stripe_subscription_id = data.get('subscription')
            db.commit()
    elif kind in ('customer.subscription.deleted', 'customer.subscription.updated'):
        subscription_id = data.get('id')
        org = db.scalar(select(Org).where(Org.stripe_subscription_id == subscription_id))
        if org:
            status = data.get('status')
            org.plan = (data.get('metadata', {}).get('plan') or org.plan) if status in ('active', 'trialing') else 'starter'
            db.commit()
    return {'received': True}

@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/static/{path:path}')
def assets(path: str):
    safe_root = (ROOT / 'static').resolve()
    dest = (safe_root / path).resolve()
    if not dest.is_relative_to(safe_root) or not dest.is_file():
        raise HTTPException(404)
    return FileResponse(dest)
