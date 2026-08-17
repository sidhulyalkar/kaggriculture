"""V1 counter-meta and tournament comparison policies."""
from .champion_agent import HarvestMind


class CounterMeta(HarvestMind):
    def _animal_targets(self, obs, day):
        if day < 7:
            return {"COW": 2, "SHEEP": 2, "GOOSE": 0}
        if day < 11:
            return {"COW": 6, "SHEEP": 4, "GOOSE": 0}
        return {"COW": 8, "SHEEP": 6, "GOOSE": 0}

    def _crop_targets(self, obs, counts, day):
        me = int(obs.get("player", 0))
        q = len(obs["farms"][me].get("unlocked_quadrants", ["NW"]))
        at = self._animal_targets(obs, day)
        slots = max(0, 25 * q - at["COW"] - at["SHEEP"])
        if q == 1:
            return {"WHEAT": 7, "MELON": max(0, slots - 7), "STRAWBERRY": 0, "CARROT": 0, "TOMATO": 0}
        if day >= 18:
            w = min(slots, 22)
            return {"WHEAT": w, "MELON": 0, "STRAWBERRY": max(0, slots - w), "CARROT": 0, "TOMATO": 0}
        w = min(slots, 12)
        m = min(max(0, slots - w), 8)
        return {"WHEAT": w, "MELON": m, "STRAWBERRY": max(0, slots - w - m), "CARROT": 0, "TOMATO": 0}


class TournamentMind(HarvestMind):
    """High-floor V1 policy with a conservative visible-opponent switch."""
    def _animal_targets(self, obs, day):
        if day < 7:
            return {"COW": 2, "SHEEP": 2, "GOOSE": 0}
        if day < 11:
            return {"COW": 6, "SHEEP": 4, "GOOSE": 0}
        return {"COW": 8, "SHEEP": 6, "GOOSE": 0}

    def _looks_like_meta(self, obs, day):
        me = int(obs.get("player", 0))
        farms = obs.get("farms", []) or []
        opp = self._counts(farms[1 - me]) if len(farms) > 1 else {}
        if day < 10:
            return opp.get("PASTURE", 0) >= 6 and opp.get("MELON", 0) >= 8 and opp.get("GOOSE", 0) == 0
        return opp.get("PASTURE", 0) >= 10 and opp.get("STRAWBERRY", 0) >= 20 and opp.get("GOOSE", 0) <= 1

    def _crop_targets(self, obs, counts, day):
        me = int(obs.get("player", 0))
        q = len(obs["farms"][me].get("unlocked_quadrants", ["NW"]))
        at = self._animal_targets(obs, day)
        slots = max(0, 25 * q - at["COW"] - at["SHEEP"])
        if q == 1:
            return {"WHEAT": 7, "MELON": max(0, slots - 7), "STRAWBERRY": 0, "CARROT": 0, "TOMATO": 0}
        counter = self._looks_like_meta(obs, day)
        if day >= 18:
            w = min(slots, 22 if counter else 19)
            return {"WHEAT": w, "MELON": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": max(0, slots - w)}
        w_target, m_target = ((12, 8) if counter else (7, 12))
        w = min(slots, w_target)
        m = min(max(0, slots - w), m_target)
        return {"WHEAT": w, "MELON": m, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": max(0, slots - w - m)}


_POLICY = TournamentMind()
def agent(obs, configuration=None):
    return _POLICY.act(obs)
