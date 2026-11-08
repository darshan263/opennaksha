package app.opennaksha.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Data classes matching the published catalog JSON (pipeline/opennaksha/models.py,
 * docs/catalog-schema.md). Timestamps stay ISO-8601 strings; see [Times] for parsing.
 */
const val SUPPORTED_SCHEMA_VERSION = 1

val CatalogJson = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    coerceInputValues = true
}

@Serializable
data class CatalogIndex(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("generated_at") val generatedAt: String,
    val cities: List<CityEntry> = emptyList(),
    @SerialName("latest_app_version") val latestAppVersion: String? = null,
    @SerialName("latest_app_url") val latestAppUrl: String? = null,
)

@Serializable
data class CityEntry(
    val id: String,
    @SerialName("name_en") val nameEn: String,
    @SerialName("name_gu") val nameGu: String,
    @SerialName("scheme_count") val schemeCount: Int,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class CityFile(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("city_id") val cityId: String,
    @SerialName("generated_at") val generatedAt: String,
    val schemes: List<SchemeRecord> = emptyList(),
)

@Serializable
data class SchemeRecord(
    val id: String,
    @SerialName("city_id") val cityId: String,
    val authority: String,
    @SerialName("scheme_type") val schemeType: String,
    @SerialName("scheme_no") val schemeNo: String,
    @SerialName("name_en") val nameEn: String? = null,
    @SerialName("name_gu") val nameGu: String? = null,
    val status: String = "unknown",
    /** The source site's own wording of the status, e.g. "Submitted to Govt." */
    @SerialName("status_label") val statusLabel: String? = null,
    @SerialName("status_date") val statusDate: String? = null,
    @SerialName("source_page_url") val sourcePageUrl: String,
    val files: List<FileEntry> = emptyList(),
    val overlay: Overlay = Overlay(),
    @SerialName("first_seen") val firstSeen: String,
    @SerialName("last_changed") val lastChanged: String,
    @SerialName("last_checked") val lastChecked: String,
    @SerialName("removed_from_source") val removedFromSource: Boolean = false,
) {
    val currentFiles: List<FileEntry> get() = files.filterNot { it.superseded }
    val olderFiles: List<FileEntry> get() = files.filter { it.superseded }
    val currentMap: FileEntry? get() = currentFiles.firstOrNull { it.kind == "map" } ?: currentFiles.firstOrNull()
    val hasOverlay: Boolean get() = overlay.status != "none" && overlay.url != null && overlay.corners?.size == 4

    /** The newest current map file appeared after the scheme was first seen → the map was updated. */
    val mapUpdatedAt: String?
        get() = currentFiles.filter { it.kind == "map" }
            .maxByOrNull { Times.millis(it.firstSeen) }
            ?.takeIf { Times.millis(it.firstSeen) > Times.millis(firstSeen) }
            ?.firstSeen
}

@Serializable
data class FileEntry(
    val kind: String,
    val title: String,
    val url: String,
    val sha256: String? = null,
    @SerialName("size_bytes") val sizeBytes: Long? = null,
    val etag: String? = null,
    @SerialName("last_modified") val lastModified: String? = null,
    @SerialName("first_seen") val firstSeen: String,
    val superseded: Boolean = false,
    @SerialName("last_hashed") val lastHashed: String? = null,
)

@Serializable
data class Overlay(
    val status: String = "none",
    val url: String? = null,
    /** [[lon, lat] top-left, top-right, bottom-right, bottom-left] */
    val corners: List<List<Double>>? = null,
    @SerialName("source_sha256") val sourceSha256: String? = null,
    @SerialName("accuracy_note") val accuracyNote: String? = null,
    @SerialName("points_sha256") val pointsSha256: String? = null,
) {
    val isOutdated: Boolean get() = status == "outdated"
}

@Serializable
data class ChangesFile(
    @SerialName("schema_version") val schemaVersion: Int = 1,
    val runs: List<RunChanges> = emptyList(),
)

@Serializable
data class RunChanges(
    @SerialName("run_at") val runAt: String,
    val new: List<String> = emptyList(),
    val changed: List<SchemeChange> = emptyList(),
    @SerialName("removed_from_source") val removedFromSource: List<String> = emptyList(),
    @SerialName("failed_sources") val failedSources: List<String> = emptyList(),
)

@Serializable
data class SchemeChange(val id: String, val what: List<String> = emptyList())

object SchemeStatus {
    val ALL = listOf("draft", "preliminary", "final", "sanctioned_variation", "unknown")
}

object SchemeTypes {
    val ALL = listOf("TP", "DP", "LAP", "VILLAGE")
}
