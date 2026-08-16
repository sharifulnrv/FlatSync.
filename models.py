from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='manager') # admin, manager

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_number = db.Column(db.String(20), unique=True, nullable=False)
    monthly_charge = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='vacant') # occupied, vacant
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    whatsapp_number = db.Column(db.String(20))
    address = db.Column(db.Text)
    units = db.relationship('Unit', backref='resident', lazy=True)

    @property
    def total_service_charge_due(self):
        from models import MonthlyBill
        unpaid = MonthlyBill.query.filter(
            MonthlyBill.customer_id == self.id,
            MonthlyBill.status.in_(['unpaid', 'partial'])
        ).all()
        return sum(b.balance_due for b in unpaid)

    @property
    def total_service_charge_paid(self):
        from models import MonthlyBill
        bills = MonthlyBill.query.filter_by(customer_id=self.id).all()
        return sum(b.paid_amount for b in bills)

    @property
    def service_charge_history(self):
        from models import MonthlyBill
        return MonthlyBill.query.filter_by(customer_id=self.id).order_by(MonthlyBill.year.desc(), MonthlyBill.month.desc()).all()

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False) # asset, liability, equity, revenue, expense
    code = db.Column(db.String(20), unique=True) # e.g., 1001 for Cash
    is_summary = db.Column(db.Boolean, default=False)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255))
    reference = db.Column(db.String(50)) # e.g., Invoice #88
    voucher_number = db.Column(db.String(50), nullable=True)
    monthly_bill_id = db.Column(db.Integer, db.ForeignKey('monthly_bill.id'), nullable=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    bill_journal_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=True)
    
    monthly_bill = db.relationship('MonthlyBill', backref='transactions')
    event = db.relationship('Event', backref='transactions')
    bill_payments = db.relationship('JournalEntry', backref=db.backref('settled_bill', remote_side=[id]))
    entries = db.relationship('LedgerEntry', backref='parent', lazy=True)

class LedgerEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True) # For resident tracking
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=True) # For vendor/third-party tracking
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True) # Linked to a specific event
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True) # Linked to a specific asset
    account = db.relationship('Account', backref='ledger_entries')
    event = db.relationship('Event', backref='ledger_entries')
    customer = db.relationship('Customer', backref='ledger_entries')
    party = db.relationship('Party', backref='ledger_entries')
    asset = db.relationship('Asset', backref='ledger_entries')

class Party(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20)) # vendor, contractor, other
    default_account_code = db.Column(db.String(20)) # Preferred expense/income account
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='planned') # planned, active, completed
    per_resident_fee = db.Column(db.Float, default=0.0)
    
    # Relationships for isolated finance
    finance_records = db.relationship('EventFinance', backref='event', lazy=True, cascade="all, delete-orphan")

class EventFinance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255))
    type = db.Column(db.String(20)) # 'income' or 'expense'
    amount = db.Column(db.Float, default=0.0)
    category_id = db.Column(db.Integer, db.ForeignKey('event_category.id'), nullable=True)
    
    category = db.relationship('EventCategory', backref='records')

class EventCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(20), default='expense') # income, expense, or both

class AssetCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('asset_category.id'))
    purchase_date = db.Column(db.Date)
    purchase_cost = db.Column(db.Float, default=0.0)
    category = db.relationship('AssetCategory', backref='assets')
    transactions = db.relationship('AssetTransaction', backref='asset', lazy=True)

    @property
    def total_maintenance(self):
        return sum(t.amount for t in self.transactions if t.type == 'maintenance')

    @property
    def total_depreciation(self):
        return sum(t.amount for t in self.transactions if t.type == 'depreciation')

    @property
    def current_value(self):
        # Initial cost + increases (e.g. upgrades) - decreases (depreciation, sales)
        val = self.purchase_cost
        for t in self.transactions:
            if t.type in ['depreciation', 'sale']:
                val -= t.amount
            elif t.type in ['appreciation', 'upgrade']:
                val += t.amount
        return val

class AssetTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=True)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=True)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    description = db.Column(db.String(255))
    type = db.Column(db.String(20), default='maintenance') # maintenance, depreciation, sale, appreciation
    amount = db.Column(db.Float, default=0.0)
    
    party = db.relationship('Party', backref='asset_transactions')
    journal = db.relationship('JournalEntry', backref='asset_transaction', uselist=False)

class MaintenanceTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open') # open, in_progress, resolved, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    unit = db.relationship('Unit', backref='maintenance_tickets')

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class MonthlyBill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    month = db.Column(db.Integer, nullable=False) # 1-12
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    penalty_to_apply = db.Column(db.Float, default=0.0) # Fixed Penalty
    daily_penalty_rate = db.Column(db.Float, default=0.0)
    next_month_daily_rate = db.Column(db.Float, default=0.0)
    penalty_amount = db.Column(db.Float, default=0.0) # Actual applied penalty at payment
    status = db.Column(db.String(20), default='unpaid') # unpaid, partial, paid
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    paid_amount = db.Column(db.Float, default=0.0)
    penalty_mode = db.Column(db.String(20), default='auto') # 'auto' or 'manual'
    
    @property
    def current_penalty(self):
        """Calculates tiered penalty based on today's date."""
        from datetime import date
        return self.calculate_penalty(date.today())

    def calculate_penalty(self, on_date):
        """Calculates tiered penalty based on a specific date."""
        import calendar
        
        if self.status == 'paid' and self.paid_date and on_date >= self.paid_date:
            return self.penalty_amount

        if self.penalty_mode == 'manual':
            return self.penalty_amount
            
        if on_date <= self.due_date:
            return 0.0
            
        # 1. Fixed Penalty
        total = self.penalty_to_apply
        
        # 2. Daily Penalty Calculation
        last_day_val = calendar.monthrange(self.year, self.month)[1]
        from datetime import date
        last_day_of_month = date(self.year, self.month, last_day_val)
        
        if on_date <= last_day_of_month:
            overdue_days = (on_date - self.due_date).days
            total += overdue_days * self.daily_penalty_rate
        else:
            initial_period_days = (last_day_of_month - self.due_date).days
            escalated_period_days = (on_date - last_day_of_month).days
            
            total += initial_period_days * self.daily_penalty_rate
            total += escalated_period_days * self.next_month_daily_rate
            
        return total

    @property
    def balance_due(self):
        return (self.amount + self.current_penalty) - self.paid_amount

    @property
    def due_percentage(self):
        total = self.amount + self.current_penalty
        if total == 0: return 0
        return max(0, (self.balance_due / total) * 100)
    
    @property
    def voucher_number(self):
        """Return the voucher number from any linked transaction."""
        if not self.transactions:
            return None
        for txn in self.transactions:
            if txn.voucher_number:
                return txn.voucher_number
        return None

    @property
    def payment_journal_id(self):
        """Return the ID of the transaction most likely to be the payment."""
        if not self.transactions:
            return None
        
        # 1. Look for explicit payment description
        for txn in self.transactions:
            if txn.description and "payment" in txn.description.lower():
                return txn.id
        
        # 2. Look for any transaction with a voucher
        for txn in self.transactions:
            if txn.voucher_number:
                return txn.id
                
        # 3. Fallback to latest transaction if bill is paid/partial
        if self.status != 'unpaid':
            # Sort by ID descending to get the latest
            sorted_txns = sorted(self.transactions, key=lambda x: x.id, reverse=True)
            return sorted_txns[0].id
            
        return None

    def recalculate_from_ledger(self):
        """Recalculates paid_amount and penalty_amount from linked LedgerEntries."""
        from models import LedgerEntry
        
        # 1. Recalculate Paid Amount (Credits to Account 3930 - Service Charge Receivable)
        # We only count credits that are linked to this specific monthly bill
        total_payments = 0.0
        penalty_accrued = 0.0
        
        for journal in self.transactions:
            for entry in journal.entries:
                # Account 3930 is Service Charge Receivable
                if entry.account.code == '3930':
                    # A credit to receivable means a payment was received
                    if entry.credit > 0:
                        total_payments += entry.credit
                
                # Account 4110 is Late Penalty Income
                # If we have debits to 4110, it means a penalty was 'accrued' for this bill
                # Wait, penalties are DEBITED to Receivable (3930) and CREDITED to Income (4110)
                if entry.account.code == '4110' and entry.credit > 0:
                    penalty_accrued += entry.credit
        
        self.paid_amount = total_payments
        self.penalty_amount = penalty_accrued
        
        # 2. Update Status
        if self.balance_due <= 0:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'unpaid'
            
        return self.status

    unit = db.relationship('Unit', backref='monthly_bills')
    customer = db.relationship('Customer', backref='monthly_bills')
