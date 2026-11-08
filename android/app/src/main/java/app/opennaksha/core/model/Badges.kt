package app.opennaksha.core.model

enum class Badge { NEW, UPDATED, REMOVED }

/**
 * "New"/"Updated" relative to the user's previous visit (epoch millis). No previous visit
 * (first launch) → no badges, so the bundled catalog doesn't light up as all-new.
 */
fun badgeFor(firstSeenMs: Long, lastChangedMs: Long, removed: Boolean, previousVisitMs: Long?): Badge? = when {
    removed -> Badge.REMOVED
    previousVisitMs == null -> null
    firstSeenMs > previousVisitMs -> Badge.NEW
    lastChangedMs > previousVisitMs -> Badge.UPDATED
    else -> null
}

data class CityNews(val cityId: String, val newCount: Int, val updatedCount: Int)

/** Per-city counts of new/updated schemes since [sinceMs]. */
fun newsSince(schemes: List<SchemeSummary>, sinceMs: Long): List<CityNews> =
    schemes.groupBy { it.cityId }.mapNotNull { (city, items) ->
        val new = items.count { it.firstSeenMs > sinceMs && !it.removedFromSource }
        val updated = items.count { it.firstSeenMs <= sinceMs && it.lastChangedMs > sinceMs }
        if (new + updated == 0) null else CityNews(city, new, updated)
    }.sortedBy { it.cityId }

/** Lightweight row used for lists and search (no file lists). */
data class SchemeSummary(
    val id: String,
    val cityId: String,
    val authority: String,
    val schemeType: String,
    val schemeNo: String,
    val nameEn: String?,
    val nameGu: String?,
    val status: String,
    val statusLabel: String?,
    val statusDate: String?,
    val firstSeenMs: Long,
    val lastChangedMs: Long,
    val removedFromSource: Boolean,
    val overlayStatus: String,
) {
    fun matches(query: String): Boolean {
        val q = query.trim().lowercase()
        if (q.isEmpty()) return true
        return schemeNo.lowercase().contains(q) ||
            "$schemeType $schemeNo".lowercase().contains(q) ||
            "$schemeType-$schemeNo".lowercase().contains(q) ||
            (nameEn?.lowercase()?.contains(q) == true) ||
            (nameGu?.contains(query.trim()) == true)
    }
}
