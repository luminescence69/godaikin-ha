"""
Counts energy usage for airconds - uses Sta_ODPwrCon - quite similar results to GO DAIKIN energy data.
"""

from datetime import datetime as dt
import structlog

from .types import *

logger = structlog.get_logger(__name__)


class EnergyCounter:
    def __init__(self):
        self.energy_by_unique_id: dict[UniqueID, float] = {}
        self.energy_accumulated_at_by_unique_id: dict[UniqueID, dt] = {}

    def accumulate_energy_usage_for_aircond(self, aircond: Aircond) -> float:
        now = dt.now()
        accumulated_at = self.energy_accumulated_at_by_unique_id.get(aircond.unique_id)
        self.energy_accumulated_at_by_unique_id[aircond.unique_id] = now

        if not accumulated_at:
            # First accumulation
            logger.debug("First energy accumulation", unique_id=aircond.unique_id, is_on=aircond.is_on)
            return 0.0

        energy_at_last_accum = self.energy_by_unique_id.get(aircond.unique_id, 0.0)

        # Multiple checks to ensure AC is truly on before accumulating energy
        is_actually_on = (
            aircond.is_on and 
            aircond.shadowState.Set_OnOff == 1 and
            aircond.shadowState.Sta_ODPwrCon > 0  # Additional check: power consumption > 0
        )
        
        # If AC is off, power consumption is 0
        kilowatts = (aircond.shadowState.Sta_ODPwrCon / 1000) if is_actually_on else 0.0
        hours_passed_since_last_accum = (now - accumulated_at).total_seconds() / 3600
        energy_since_last_accum = kilowatts * hours_passed_since_last_accum

        energy_now = energy_at_last_accum + energy_since_last_accum

        # Log energy accumulation for debugging
        logger.debug(
            "Energy accumulation", 
            unique_id=aircond.unique_id,
            is_on=aircond.is_on,
            set_onoff=aircond.shadowState.Set_OnOff,
            power_w=aircond.shadowState.Sta_ODPwrCon,
            is_actually_on=is_actually_on,
            kilowatts=kilowatts,
            hours_passed=round(hours_passed_since_last_accum, 4),
            energy_delta=round(energy_since_last_accum, 4),
            energy_total=round(energy_now, 4)
        )

        self.energy_by_unique_id[aircond.unique_id] = energy_now

        return energy_now

    def get_energy_usage(self, unique_id: UniqueID) -> float:
        return self.energy_by_unique_id.get(unique_id, 0.0)
    
    def reset_energy_if_off(self, aircond: Aircond) -> None:
        """Reset energy accumulation if AC has been off for a while"""
        if not aircond.is_on and aircond.shadowState.Set_OnOff == 0:
            # Reset energy counter when AC is definitively off
            old_energy = self.energy_by_unique_id.get(aircond.unique_id, 0.0)
            if old_energy > 0:
                logger.info(
                    "Resetting energy counter for turned-off AC", 
                    unique_id=aircond.unique_id,
                    old_energy=old_energy
                )
                self.energy_by_unique_id[aircond.unique_id] = 0.0