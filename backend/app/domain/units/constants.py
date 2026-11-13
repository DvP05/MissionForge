"""Physical and gameplay constants (SI)."""

from app.schemas.units import Provenance

G0 = 9.80665  # m/s^2, standard gravity
C = 299792458.0  # m/s
KB = 1.380649e-23  # J/K
MU_EARTH = 3.986004418e14  # m^3/s^2
R_EARTH = 6378137.0  # m, WGS-84 equatorial radius
AU_M = 149_597_870_700.0  # m, IAU 2012 definition

# NOTE: gameplay-estimate unless a source is attached (see SOLAR_CONSTANT_PROVENANCE).
SOLAR_CONSTANT_W_M2 = 1361.0
SOLAR_CONSTANT_PROVENANCE = Provenance(
    fidelity="gameplay-estimate",
    source_name="MissionForge gameplay estimate (1 AU solar irradiance)",
    assumptions=["Nominal 1 AU total solar irradiance; no primary source attached."],
)
