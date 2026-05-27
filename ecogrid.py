"""
EcoGrid Energy P2P Trading Platform
=====================================
Domains:
  1. Marketplace       - Match energy sellers with buyers
  2. Smart Meter       - IoT meter reading ingestion
  3. Financial         - Wallet and trade settlement
"""

import uuid
from datetime import datetime


# ─────────────────────────────────────────────
#  MARKETPLACE
# ─────────────────────────────────────────────

class EnergyListing:
    """A seller's offer to sell surplus solar energy."""

    def __init__(self, seller_id, seller_name, available_kwh, price_per_kwh):
        if available_kwh <= 0:
            raise ValueError("Available energy must be greater than zero.")
        if price_per_kwh <= 0:
            raise ValueError("Price per kWh must be greater than zero.")
        self.seller_id = seller_id
        self.seller_name = seller_name
        self.available_kwh = available_kwh
        self.price_per_kwh = price_per_kwh
        self.is_active = True
        self.created_at = datetime.now()

    def deactivate(self):
        self.is_active = False

    def __repr__(self):
        return (f"EnergyListing(seller={self.seller_name}, "
                f"{self.available_kwh} kWh @ ${self.price_per_kwh}/kWh)")


class TradeRequest:
    """A buyer's request to purchase a certain amount of energy."""

    def __init__(self, buyer_id, buyer_name, required_kwh):
        if required_kwh <= 0:
            raise ValueError("Required energy must be greater than zero.")
        self.buyer_id = buyer_id
        self.buyer_name = buyer_name
        self.required_kwh = required_kwh
        self.status = "pending"
        self.created_at = datetime.now()

    def __repr__(self):
        return (f"TradeRequest(buyer={self.buyer_name}, "
                f"{self.required_kwh} kWh, status={self.status})")


class TradeResult:
    """Result of an attempted trade."""

    def __init__(self, success, seller_name, buyer_name,
                 energy_kwh, price_per_kwh, message=""):
        self.success = success
        self.seller_name = seller_name
        self.buyer_name = buyer_name
        self.energy_kwh = energy_kwh
        self.price_per_kwh = price_per_kwh
        self.total_cost = round(energy_kwh * price_per_kwh, 2) if success else 0.0
        self.message = message
        self.timestamp = datetime.now()

    def __repr__(self):
        return (f"TradeResult(success={self.success}, "
                f"{self.energy_kwh} kWh, total=${self.total_cost})")


class Marketplace:
    """Matches energy sellers with buyers and records trade history."""

    def __init__(self):
        self.listings = []
        self.trade_history = []

    def add_listing(self, listing):
        if not isinstance(listing, EnergyListing):
            raise TypeError("Only EnergyListing objects can be added.")
        self.listings.append(listing)

    def get_active_listings(self):
        return [l for l in self.listings if l.is_active]

    def find_best_match(self, trade_request):
        """Return cheapest listing that covers the buyer's requirement."""
        eligible = [
            l for l in self.get_active_listings()
            if l.available_kwh >= trade_request.required_kwh
        ]
        if not eligible:
            return None
        return min(eligible, key=lambda l: l.price_per_kwh)

    def execute_trade(self, trade_request):
        if not isinstance(trade_request, TradeRequest):
            raise TypeError("Only TradeRequest objects can be processed.")

        best = self.find_best_match(trade_request)

        if best is None:
            result = TradeResult(
                success=False,
                seller_name="N/A",
                buyer_name=trade_request.buyer_name,
                energy_kwh=0,
                price_per_kwh=0,
                message="No suitable listing found."
            )
            trade_request.status = "failed"
        else:
            best.available_kwh -= trade_request.required_kwh
            if best.available_kwh == 0:
                best.deactivate()
            result = TradeResult(
                success=True,
                seller_name=best.seller_name,
                buyer_name=trade_request.buyer_name,
                energy_kwh=trade_request.required_kwh,
                price_per_kwh=best.price_per_kwh,
                message="Trade completed successfully."
            )
            trade_request.status = "completed"

        self.trade_history.append(result)
        return result

    def get_trade_history(self):
        return self.trade_history


# ─────────────────────────────────────────────
#  SMART METER
# ─────────────────────────────────────────────

class MeterReading:
    """A single IoT meter reading (generation or consumption)."""

    VALID_TYPES = ("generation", "consumption")

    def __init__(self, meter_id, reading_type, kwh_value):
        if reading_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid type '{reading_type}'. Use {self.VALID_TYPES}.")
        if kwh_value < 0:
            raise ValueError("kWh value cannot be negative.")
        self.meter_id = meter_id
        self.reading_type = reading_type
        self.kwh_value = kwh_value
        self.timestamp = datetime.now()

    def __repr__(self):
        return (f"MeterReading(meter={self.meter_id}, "
                f"{self.reading_type}={self.kwh_value} kWh)")


class SmartMeter:
    """IoT smart meter device installed at a property."""

    def __init__(self, meter_id, owner_name, location):
        self.meter_id = meter_id
        self.owner_name = owner_name
        self.location = location
        self.readings = []
        self.is_online = True

    def record_reading(self, reading_type, kwh_value):
        if not self.is_online:
            raise ConnectionError(f"Meter {self.meter_id} is offline.")
        reading = MeterReading(self.meter_id, reading_type, kwh_value)
        self.readings.append(reading)
        return reading

    def get_total_generation(self):
        return sum(r.kwh_value for r in self.readings if r.reading_type == "generation")

    def get_total_consumption(self):
        return sum(r.kwh_value for r in self.readings if r.reading_type == "consumption")

    def get_net_energy(self):
        """Positive = surplus to sell. Negative = drawing from grid."""
        return round(self.get_total_generation() - self.get_total_consumption(), 4)

    def get_readings_by_type(self, reading_type):
        if reading_type not in MeterReading.VALID_TYPES:
            raise ValueError(f"Invalid reading type: {reading_type}")
        return [r for r in self.readings if r.reading_type == reading_type]

    def go_offline(self):
        self.is_online = False

    def go_online(self):
        self.is_online = True

    def __repr__(self):
        return f"SmartMeter(id={self.meter_id}, owner={self.owner_name}, online={self.is_online})"


class MeterDataIngestionService:
    """Manages and ingests data from multiple smart meters across the grid."""

    def __init__(self):
        self.meters = {}

    def register_meter(self, meter):
        if not isinstance(meter, SmartMeter):
            raise TypeError("Only SmartMeter objects can be registered.")
        if meter.meter_id in self.meters:
            raise ValueError(f"Meter '{meter.meter_id}' already registered.")
        self.meters[meter.meter_id] = meter

    def ingest_reading(self, meter_id, reading_type, kwh_value):
        if meter_id not in self.meters:
            raise KeyError(f"Meter ID '{meter_id}' not found.")
        return self.meters[meter_id].record_reading(reading_type, kwh_value)

    def get_meter(self, meter_id):
        return self.meters.get(meter_id)

    def get_all_surplus_meters(self):
        return [m for m in self.meters.values() if m.get_net_energy() > 0]

    def get_system_summary(self):
        total_gen = sum(m.get_total_generation() for m in self.meters.values())
        total_con = sum(m.get_total_consumption() for m in self.meters.values())
        return {
            "total_meters": len(self.meters),
            "total_generation_kwh": round(total_gen, 4),
            "total_consumption_kwh": round(total_con, 4),
            "net_grid_balance_kwh": round(total_gen - total_con, 4),
        }


# ─────────────────────────────────────────────
#  FINANCIAL SETTLEMENT
# ─────────────────────────────────────────────

class InsufficientFundsError(Exception):
    pass


class InvalidTransactionError(Exception):
    pass


class Wallet:
    """User's digital wallet for energy trading."""

    def __init__(self, user_id, user_name, initial_balance=0.0):
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative.")
        self.user_id = user_id
        self.user_name = user_name
        self.balance = round(initial_balance, 2)
        self.transaction_history = []

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance = round(self.balance + amount, 2)
        self._log("deposit", amount)

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self.balance:
            raise InsufficientFundsError(
                f"Balance ${self.balance:.2f} is less than ${amount:.2f}.")
        self.balance = round(self.balance - amount, 2)
        self._log("withdrawal", amount)

    def _log(self, txn_type, amount):
        self.transaction_history.append({
            "type": txn_type,
            "amount": round(amount, 2),
            "balance_after": self.balance,
            "timestamp": datetime.now().isoformat(),
        })

    def get_balance(self):
        return self.balance

    def __repr__(self):
        return f"Wallet(user={self.user_name}, balance=${self.balance:.2f})"


class Transaction:
    """A financial transaction between buyer and seller."""

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    def __init__(self, sender_id, receiver_id, amount, description=""):
        if amount <= 0:
            raise InvalidTransactionError("Transaction amount must be positive.")
        self.transaction_id = str(uuid.uuid4())
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = round(amount, 2)
        self.description = description
        self.status = self.STATUS_PENDING
        self.created_at = datetime.now()
        self.completed_at = None

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self):
        self.status = self.STATUS_FAILED

    def __repr__(self):
        return (f"Transaction(id={self.transaction_id[:8]}..., "
                f"${self.amount:.2f}, status={self.status})")


class SettlementService:
    """Processes financial settlements for energy trades."""

    PLATFORM_FEE_RATE = 0.02  # 2% fee per trade

    def __init__(self):
        self.wallets = {}
        self.transactions = []

    def register_wallet(self, wallet):
        if not isinstance(wallet, Wallet):
            raise TypeError("Only Wallet objects can be registered.")
        if wallet.user_id in self.wallets:
            raise ValueError(f"Wallet for '{wallet.user_id}' already registered.")
        self.wallets[wallet.user_id] = wallet

    def get_wallet(self, user_id):
        if user_id not in self.wallets:
            raise KeyError(f"No wallet found for '{user_id}'.")
        return self.wallets[user_id]

    def calculate_fee(self, amount):
        return round(amount * self.PLATFORM_FEE_RATE, 2)

    def settle_trade(self, buyer_id, seller_id, energy_kwh, price_per_kwh):
        total = round(energy_kwh * price_per_kwh, 2)
        payout = round(total - self.calculate_fee(total), 2)

        buyer_wallet = self.get_wallet(buyer_id)
        seller_wallet = self.get_wallet(seller_id)

        txn = Transaction(
            sender_id=buyer_id,
            receiver_id=seller_id,
            amount=total,
            description=f"{energy_kwh} kWh @ ${price_per_kwh}/kWh"
        )

        try:
            buyer_wallet.withdraw(total)
            seller_wallet.deposit(payout)
            txn.mark_completed()
        except InsufficientFundsError as e:
            txn.mark_failed()
            self.transactions.append(txn)
            raise InsufficientFundsError(str(e)) from e

        self.transactions.append(txn)
        return txn

    def get_transaction_history(self):
        return self.transactions

    def get_completed_transactions(self):
        return [t for t in self.transactions if t.status == Transaction.STATUS_COMPLETED]

    def get_total_revenue(self):
        return round(sum(self.calculate_fee(t.amount)
                         for t in self.get_completed_transactions()), 2)


# ─────────────────────────────────────────────
#  DEMO
# ─────────────────────────────────────────────

def run_demo():
    print("=" * 50)
    print("   EcoGrid Energy P2P Trading Platform")
    print("=" * 50)

    # Smart Meters
    print("\n[1] Smart Meters")
    service = MeterDataIngestionService()
    meter_alice = SmartMeter("MTR-001", "Alice", "12 Solar St")
    meter_bob = SmartMeter("MTR-002", "Bob", "34 Green Ave")
    service.register_meter(meter_alice)
    service.register_meter(meter_bob)
    service.ingest_reading("MTR-001", "generation", 20.0)
    service.ingest_reading("MTR-001", "consumption", 5.0)
    service.ingest_reading("MTR-002", "generation", 3.0)
    service.ingest_reading("MTR-002", "consumption", 8.0)
    print(f"   Grid: {service.get_system_summary()}")
    print(f"   Surplus: {[m.owner_name for m in service.get_all_surplus_meters()]}")

    # Marketplace
    print("\n[2] Marketplace")
    market = Marketplace()
    market.add_listing(EnergyListing("USR-001", "Alice", 15.0, 0.12))
    result = market.execute_trade(TradeRequest("USR-002", "Bob", 5.0))
    print(f"   {result} — {result.message}")

    # Settlement
    print("\n[3] Settlement")
    settlement = SettlementService()
    settlement.register_wallet(Wallet("USR-001", "Alice", 50.0))
    settlement.register_wallet(Wallet("USR-002", "Bob", 100.0))
    if result.success:
        txn = settlement.settle_trade("USR-002", "USR-001",
                                      result.energy_kwh, result.price_per_kwh)
        print(f"   {txn}")
        print(f"   Alice: ${settlement.get_wallet('USR-001').get_balance()}")
        print(f"   Bob:   ${settlement.get_wallet('USR-002').get_balance()}")
        print(f"   Platform fee revenue: ${settlement.get_total_revenue()}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    run_demo()
