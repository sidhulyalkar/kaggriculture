from submission.guarded_market_agent import GuardedMarketMind

class DummyPredictor:
    models={"STRAWBERRY":{}}
    def available(self,p):return p=="STRAWBERRY"
    def threshold(self,p):return .5
    def probability(self,obs,seat,p):return .9
    def shock_mean(self,p):return 6.0


def test_safe_gate_rejects_incumbent_like_rate():
    m=GuardedMarketMind.__new__(GuardedMarketMind);m.mode='safe';m.exact=150;m.events=6;m.units=30;m.buckets=[1,1,1,1,1,1];m.regime_active=False;m.activation_step=None
    min_exact,min_events,min_rate,max_conc=m._thresholds();rate=m.events/m.exact;conc=max(m.buckets)/m.events
    assert not (m.exact>=min_exact and m.events>=min_events and rate>=min_rate and conc<=max_conc)


def test_safe_gate_accepts_soil_like_profile():
    m=GuardedMarketMind.__new__(GuardedMarketMind);m.mode='safe';m.exact=150;m.events=13;m.units=65;m.buckets=[2,2,2,2,2,3];m.regime_active=False;m.activation_step=None
    min_exact,min_events,min_rate,max_conc=m._thresholds();rate=m.events/m.exact;conc=max(m.buckets)/m.events
    assert m.exact>=min_exact and m.events>=min_events and rate>=min_rate and conc<=max_conc


def test_balanced_is_earlier_but_still_above_observed_incumbent_ceiling():
    m=GuardedMarketMind.__new__(GuardedMarketMind);m.mode='balanced'
    assert m._thresholds()[2] > .0446


def test_safe_threshold_sits_between_observed_incumbent_and_soil_rates():
    m=GuardedMarketMind.__new__(GuardedMarketMind);m.mode='safe';threshold=m._thresholds()[2]
    assert .0446 < threshold < .0849
