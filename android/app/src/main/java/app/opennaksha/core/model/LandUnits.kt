package app.opennaksha.core.model

/**
 * Land area units used in Gujarat. All values are square metres per unit and live only here.
 *
 * - 1 sq yard (vaar) = 0.83612736 m² (exact)
 * - 1 guntha = 121 sq yd = 101.17 m²
 * - 1 acre = 40 guntha = 4046.8564224 m²
 * - 1 hectare = 10 000 m²
 * - 1 vigha (bigha) = 16 guntha ≈ 1618.74 m² (17 424 sq ft) — common in Gujarat, but the size of a
 *   vigha VARIES BY REGION and the app says so on the converter screen.
 */
enum class LandUnit(val squareMetres: Double) {
    SQ_M(1.0),
    SQ_FT(0.09290304),
    SQ_YARD(0.83612736),
    GUNTHA(121 * 0.83612736),
    VIGHA(16 * 121 * 0.83612736),
    ACRE(4046.8564224),
    HECTARE(10_000.0),
}

fun convertArea(value: Double, from: LandUnit, to: LandUnit): Double =
    value * from.squareMetres / to.squareMetres
