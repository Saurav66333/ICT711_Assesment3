"""
EcoGrid Energy - Test Suite (60 tests)
Run: pytest test_ecogrid.py --cov=ecogrid --cov-report=xml
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecogrid import (
    EnergyListing, TradeRequest, TradeResult, Marketplace,
    MeterReading, SmartMeter, MeterDataIngestionService,
    Wallet, Transaction, SettlementService,
    InsufficientFundsError, InvalidTransactionError
)


# ── MARKETPLACE ──────────────────────────────

class TestEnergyListing:
    def test_valid_creation(self):
        l = EnergyListing("S1", "Alice", 10.0, 0.15)
        assert l.seller_name == "Alice" and l.is_active is True

    def test_zero_energy_raises(self):
        with pytest.raises(ValueError):
            EnergyListing("S1", "Alice", 0, 0.15)

    def test_negative_energy_raises(self):
        with pytest.raises(ValueError):
            EnergyListing("S1", "Alice", -5.0, 0.15)

    def test_zero_price_raises(self):
        with pytest.raises(ValueError):
            EnergyListing("S1", "Alice", 10.0, 0)

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            EnergyListing("S1", "Alice", 10.0, -0.10)

    def test_deactivate(self):
        l = EnergyListing("S1", "Alice", 10.0, 0.15)
        l.deactivate()
        assert l.is_active is False


class TestTradeRequest:
    def test_valid_request(self):
        r = TradeRequest("B1", "Bob", 5.0)
        assert r.status == "pending"

    def test_zero_energy_raises(self):
        with pytest.raises(ValueError):
            TradeRequest("B1", "Bob", 0)

    def test_negative_energy_raises(self):
        with pytest.raises(ValueError):
            TradeRequest("B1", "Bob", -3.0)


class TestMarketplace:
    def setup_method(self):
        self.market = Marketplace()
        self.listing = EnergyListing("S1", "Alice", 15.0, 0.12)
        self.market.add_listing(self.listing)

    def test_add_listing(self):
        assert len(self.market.get_active_listings()) == 1

    def test_add_invalid_raises(self):
        with pytest.raises(TypeError):
            self.market.add_listing("not a listing")

    def test_trade_success(self):
        result = self.market.execute_trade(TradeRequest("B1", "Bob", 5.0))
        assert result.success is True
        assert result.total_cost == pytest.approx(0.60, abs=1e-4)

    def test_trade_reduces_energy(self):
        self.market.execute_trade(TradeRequest("B1", "Bob", 5.0))
        assert self.listing.available_kwh == 10.0

    def test_trade_deactivates_when_empty(self):
        self.market.execute_trade(TradeRequest("B1", "Bob", 15.0))
        assert self.listing.is_active is False

    def test_trade_fail_no_listing(self):
        result = self.market.execute_trade(TradeRequest("B1", "Bob", 100.0))
        assert result.success is False

    def test_find_cheapest_listing(self):
        self.market.add_listing(EnergyListing("S2", "Carol", 20.0, 0.08))
        best = self.market.find_best_match(TradeRequest("B1", "Bob", 5.0))
        assert best.seller_name == "Carol"

    def test_trade_history_recorded(self):
        self.market.execute_trade(TradeRequest("B1", "Bob", 5.0))
        assert len(self.market.get_trade_history()) == 1

    def test_invalid_request_raises(self):
        with pytest.raises(TypeError):
            self.market.execute_trade("not a request")


# ── SMART METER ──────────────────────────────

class TestMeterReading:
    def test_valid_generation(self):
        r = MeterReading("MTR-001", "generation", 10.5)
        assert r.kwh_value == 10.5

    def test_valid_consumption(self):
        r = MeterReading("MTR-001", "consumption", 3.2)
        assert r.reading_type == "consumption"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            MeterReading("MTR-001", "export", 5.0)

    def test_negative_kwh_raises(self):
        with pytest.raises(ValueError):
            MeterReading("MTR-001", "generation", -1.0)

    def test_zero_kwh_allowed(self):
        r = MeterReading("MTR-001", "consumption", 0.0)
        assert r.kwh_value == 0.0


class TestSmartMeter:
    def setup_method(self):
        self.meter = SmartMeter("MTR-001", "Alice", "12 Solar St")

    def test_record_generation(self):
        self.meter.record_reading("generation", 10.0)
        assert self.meter.get_total_generation() == 10.0

    def test_record_consumption(self):
        self.meter.record_reading("consumption", 4.0)
        assert self.meter.get_total_consumption() == 4.0

    def test_net_energy_surplus(self):
        self.meter.record_reading("generation", 10.0)
        self.meter.record_reading("consumption", 4.0)
        assert self.meter.get_net_energy() == pytest.approx(6.0)

    def test_net_energy_deficit(self):
        self.meter.record_reading("generation", 2.0)
        self.meter.record_reading("consumption", 5.0)
        assert self.meter.get_net_energy() == pytest.approx(-3.0)

    def test_offline_raises(self):
        self.meter.go_offline()
        with pytest.raises(ConnectionError):
            self.meter.record_reading("generation", 5.0)

    def test_back_online(self):
        self.meter.go_offline()
        self.meter.go_online()
        self.meter.record_reading("generation", 5.0)
        assert self.meter.get_total_generation() == 5.0

    def test_readings_by_type(self):
        self.meter.record_reading("generation", 5.0)
        self.meter.record_reading("consumption", 2.0)
        assert len(self.meter.get_readings_by_type("generation")) == 1

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            self.meter.get_readings_by_type("unknown")


class TestMeterDataIngestionService:
    def setup_method(self):
        self.service = MeterDataIngestionService()
        self.meter = SmartMeter("MTR-001", "Alice", "12 Solar St")
        self.service.register_meter(self.meter)

    def test_register_meter(self):
        assert self.service.get_meter("MTR-001") is not None

    def test_duplicate_raises(self):
        with pytest.raises(ValueError):
            self.service.register_meter(self.meter)

    def test_invalid_object_raises(self):
        with pytest.raises(TypeError):
            self.service.register_meter("not a meter")

    def test_ingest_reading(self):
        self.service.ingest_reading("MTR-001", "generation", 8.0)
        assert self.meter.get_total_generation() == 8.0

    def test_unknown_meter_raises(self):
        with pytest.raises(KeyError):
            self.service.ingest_reading("MTR-999", "generation", 5.0)

    def test_surplus_meters(self):
        self.service.ingest_reading("MTR-001", "generation", 10.0)
        self.service.ingest_reading("MTR-001", "consumption", 3.0)
        assert len(self.service.get_all_surplus_meters()) == 1

    def test_system_summary(self):
        self.service.ingest_reading("MTR-001", "generation", 10.0)
        self.service.ingest_reading("MTR-001", "consumption", 4.0)
        s = self.service.get_system_summary()
        assert s["net_grid_balance_kwh"] == pytest.approx(6.0)


# ── FINANCIAL SETTLEMENT ─────────────────────

class TestWallet:
    def test_valid_creation(self):
        w = Wallet("U1", "Alice", 100.0)
        assert w.get_balance() == 100.0

    def test_negative_balance_raises(self):
        with pytest.raises(ValueError):
            Wallet("U1", "Alice", -10.0)

    def test_deposit(self):
        w = Wallet("U1", "Alice", 50.0)
        w.deposit(30.0)
        assert w.get_balance() == 80.0

    def test_deposit_zero_raises(self):
        with pytest.raises(ValueError):
            Wallet("U1", "Alice", 50.0).deposit(0)

    def test_withdraw(self):
        w = Wallet("U1", "Alice", 100.0)
        w.withdraw(40.0)
        assert w.get_balance() == 60.0

    def test_insufficient_funds_raises(self):
        with pytest.raises(InsufficientFundsError):
            Wallet("U1", "Alice", 10.0).withdraw(50.0)

    def test_withdraw_zero_raises(self):
        with pytest.raises(ValueError):
            Wallet("U1", "Alice", 100.0).withdraw(0)

    def test_history_logged(self):
        w = Wallet("U1", "Alice", 100.0)
        w.deposit(20.0)
        w.withdraw(10.0)
        assert len(w.transaction_history) == 2


class TestTransaction:
    def test_valid_transaction(self):
        t = Transaction("U1", "U2", 25.0)
        assert t.status == Transaction.STATUS_PENDING

    def test_zero_amount_raises(self):
        with pytest.raises(InvalidTransactionError):
            Transaction("U1", "U2", 0)

    def test_negative_amount_raises(self):
        with pytest.raises(InvalidTransactionError):
            Transaction("U1", "U2", -5.0)

    def test_mark_completed(self):
        t = Transaction("U1", "U2", 10.0)
        t.mark_completed()
        assert t.status == Transaction.STATUS_COMPLETED

    def test_mark_failed(self):
        t = Transaction("U1", "U2", 10.0)
        t.mark_failed()
        assert t.status == Transaction.STATUS_FAILED


class TestSettlementService:
    def setup_method(self):
        self.service = SettlementService()
        self.buyer = Wallet("B1", "Bob", 200.0)
        self.seller = Wallet("S1", "Alice", 50.0)
        self.service.register_wallet(self.buyer)
        self.service.register_wallet(self.seller)

    def test_settle_success(self):
        txn = self.service.settle_trade("B1", "S1", 5.0, 0.12)
        assert txn.status == Transaction.STATUS_COMPLETED

    def test_buyer_balance_reduced(self):
        self.service.settle_trade("B1", "S1", 5.0, 0.12)
        assert self.buyer.get_balance() == pytest.approx(199.40, abs=1e-2)

    def test_seller_receives_payout(self):
        self.service.settle_trade("B1", "S1", 5.0, 0.12)
        expected = 50.0 + round(0.60 * 0.98, 2)
        assert self.seller.get_balance() == pytest.approx(expected, abs=1e-2)

    def test_insufficient_funds_raises(self):
        poor = Wallet("P1", "Poor", 0.10)
        self.service.register_wallet(poor)
        with pytest.raises(InsufficientFundsError):
            self.service.settle_trade("P1", "S1", 100.0, 1.0)

    def test_failed_txn_recorded(self):
        poor = Wallet("P1", "Poor", 0.10)
        self.service.register_wallet(poor)
        with pytest.raises(InsufficientFundsError):
            self.service.settle_trade("P1", "S1", 100.0, 1.0)
        assert len(self.service.get_transaction_history()) == 1

    def test_duplicate_wallet_raises(self):
        with pytest.raises(ValueError):
            self.service.register_wallet(self.buyer)

    def test_unknown_wallet_raises(self):
        with pytest.raises(KeyError):
            self.service.get_wallet("UNKNOWN")

    def test_platform_revenue(self):
        self.service.settle_trade("B1", "S1", 10.0, 0.10)
        assert self.service.get_total_revenue() == pytest.approx(0.02, abs=1e-4)

    def test_completed_filter(self):
        self.service.settle_trade("B1", "S1", 5.0, 0.12)
        assert len(self.service.get_completed_transactions()) == 1
