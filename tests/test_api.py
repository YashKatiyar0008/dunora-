"""Critical end-to-end accounting and security regression tests.
Run with: pytest -q
"""
import os
import uuid
from datetime import date, timedelta

# Use ephemeral test database, never developer data.
os.environ['DATABASE_URL'] = 'sqlite:///./dunora_pytest.db'
os.environ['ALLOW_PUBLIC_DEMO'] = 'true'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def register(company='Example & Co'):
    c = TestClient(app)
    email = f'{uuid.uuid4().hex}@example.org'
    r = c.post('/api/auth/register', json={'company': company, 'email': email, 'password': 'TestPassword!123'})
    assert r.status_code == 200, r.text
    return c

def inv_payload(number='INV-'+uuid.uuid4().hex[:8], amount='25000.00'):
    return {'number': number, 'customer': 'Supplier Z', 'email': 'z@example.org', 'amount': amount,
            'issued_date': (date.today()-timedelta(days=40)).isoformat(),
            'due_date': (date.today()-timedelta(days=12)).isoformat()}

def test_session_and_tenant_isolation():
    first, second = register('First'), register('Second')
    r = first.post('/api/invoices', json=inv_payload())
    assert r.status_code == 200, r.text
    invoice_id = r.json()['id']
    assert len(first.get('/api/invoices').json()) == 1
    assert second.get(f'/api/invoices/{invoice_id}').status_code == 404
    assert second.post(f'/api/invoices/{invoice_id}/payments', json={'amount': '1.00', 'reference': 'cross-tenant'}).status_code == 404
    assert second.post(f'/api/invoices/{invoice_id}/draft').status_code == 404
    assert len(second.get('/api/invoices').json()) == 0

def test_precision_partial_payment_duplicate_and_no_overpayment():
    c = register()
    assert c.post('/api/invoices',json=inv_payload(amount='10.999')).status_code == 422
    inv = c.post('/api/invoices',json=inv_payload(amount='100.25')).json()['id']
    assert c.post(f'/api/invoices/{inv}/payments',json={'amount':'40.05','reference':'bank-001'}).status_code == 200
    record = c.get(f'/api/invoices/{inv}').json()['invoice']
    assert record['paid_minor'] == 4005
    assert record['outstanding_minor'] == 6020
    assert c.post(f'/api/invoices/{inv}/payments',json={'amount':'40.05','reference':'bank-001'}).status_code == 409
    assert c.post(f'/api/invoices/{inv}/payments',json={'amount':'60.21','reference':'bank-002'}).status_code == 422
    assert c.post(f'/api/invoices/{inv}/payments',json={'amount':'60.20','reference':'bank-002'}).status_code == 200
    assert c.get(f'/api/invoices/{inv}').json()['invoice']['status'] == 'paid'

def test_dispute_blocks_reminders_and_restores():
    c = register()
    inv = c.post('/api/invoices',json=inv_payload()).json()['id']
    r = c.post(f'/api/invoices/{inv}/dispute',json={'disputed':True,'note':'Customer questions line item'})
    assert r.status_code == 200
    assert c.post(f'/api/invoices/{inv}/draft').status_code == 422
    assert len(c.get('/api/workbench').json()['recommendations']) == 0
    c.post(f'/api/invoices/{inv}/dispute',json={'disputed':False,'note':'Resolved'})
    d = c.post(f'/api/invoices/{inv}/draft').json()
    assert d['state']=='draft'
    assert c.post(f'/api/drafts/{d["id"]}/send').json()['state'] == 'simulated'
    assert c.post(f'/api/drafts/{d["id"]}/send').status_code == 409
    assert any(a['action']=='reminder.simulated' for a in c.get('/api/audit').json())

def test_auth_required_and_csrf_origin_guard():
    assert TestClient(app).get('/api/invoices').status_code == 401
    c=register()
    assert c.post('/api/invoices',json=inv_payload(),headers={'Origin':'https://attacker.invalid'}).status_code == 403

def test_csv_import_and_duplicate_handling():
    c=register()
    content='number,customer,email,amount,due_date,issued_date\nA-100,Test Client,test@example.org,12.50,2026-09-20,2026-09-01\nA-100,Test Client,test@example.org,12.50,2026-09-20,2026-09-01\n'
    r=c.post('/api/invoices/import',files={'file':('example.csv',content,'text/csv')})
    assert r.status_code==200, r.text
    assert r.json()['imported']==1
    assert r.json()['skipped']==1
    assert len(c.get('/api/invoices').json())==1

def test_demo_instant_onboarding():
    c=TestClient(app)
    assert c.post('/api/auth/demo').status_code==200
    assert c.get('/api/me').json()['seeded'] is True
    assert len(c.get('/api/invoices').json())>=8
    assert c.post('/api/demo/seed').status_code==409

def test_checkout_unconfigured_is_not_faked():
    c=register()
    res=c.post('/api/billing/checkout',json={'plan':'growth'})
    assert res.status_code==503
