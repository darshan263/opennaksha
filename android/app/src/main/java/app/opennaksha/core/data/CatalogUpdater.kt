package app.opennaksha.core.data

import android.util.Log
import app.opennaksha.core.config.CatalogUrls
import app.opennaksha.core.model.CatalogIndex
import app.opennaksha.core.model.CatalogJson
import app.opennaksha.core.model.ChangesFile
import app.opennaksha.core.model.CityFile
import app.opennaksha.core.model.SUPPORTED_SCHEMA_VERSION
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

/** A complete, validated catalog ready to be stored. */
data class CatalogSnapshot(
    val index: CatalogIndex,
    val cities: List<CityFile>,
    /** null = keep the stored changes (changes.json missing or invalid). */
    val changes: ChangesFile?,
)

data class StoredMeta(val generatedAt: String?, val etag: String?, val lastModified: String?)

/** Where the updater keeps data. Implemented by Room in the app and by a fake in tests. */
interface CatalogStore {
    suspend fun storedMeta(): StoredMeta
    suspend fun replace(snapshot: CatalogSnapshot, etag: String?, lastModified: String?, source: String)
    suspend fun saveValidators(etag: String?, lastModified: String?)
    suspend fun markChecked(nowMs: Long)
}

sealed interface UpdateResult {
    data object NotConfigured : UpdateResult
    data object NotModified : UpdateResult
    data object UpToDate : UpdateResult
    data class Updated(val generatedAt: String) : UpdateResult
    data class Failed(val reason: String) : UpdateResult
}

class CatalogValidationException(message: String) : Exception(message)

/** Parses and validates a catalog. Throws on anything the app must not accept. */
object CatalogParser {
    fun index(text: String): CatalogIndex {
        val index = CatalogJson.decodeFromString(CatalogIndex.serializer(), text)
        if (index.schemaVersion > SUPPORTED_SCHEMA_VERSION) {
            throw CatalogValidationException("unsupported schema_version ${index.schemaVersion}")
        }
        return index
    }

    fun city(text: String, expectedId: String): CityFile {
        val city = CatalogJson.decodeFromString(CityFile.serializer(), text)
        if (city.schemaVersion > SUPPORTED_SCHEMA_VERSION) {
            throw CatalogValidationException("unsupported schema_version ${city.schemaVersion} in $expectedId")
        }
        if (city.cityId != expectedId) throw CatalogValidationException("city id ${city.cityId} != $expectedId")
        if (city.schemes.any { it.cityId != expectedId }) throw CatalogValidationException("scheme from other city in $expectedId")
        return city
    }

    fun changes(text: String): ChangesFile? = runCatching {
        CatalogJson.decodeFromString(ChangesFile.serializer(), text)
            .takeIf { it.schemaVersion <= SUPPORTED_SCHEMA_VERSION }
    }.getOrNull()
}

/**
 * PLAN.md §8 catalog update logic: conditional GET on index.json; on a new generated_at download
 * every city file, validate everything, then hand the snapshot to the store in one go.
 * Any failure keeps the current data.
 */
class CatalogUpdater(
    private val client: OkHttpClient,
    private val baseUrl: String?,
    private val store: CatalogStore,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    suspend fun update(): UpdateResult = withContext(Dispatchers.IO) {
        val base = baseUrl ?: return@withContext UpdateResult.NotConfigured
        try {
            val meta = store.storedMeta()
            val req = Request.Builder().url(CatalogUrls.index(base)).apply {
                meta.etag?.let { header("If-None-Match", it) }
                meta.lastModified?.let { header("If-Modified-Since", it) }
            }.build()
            val (index, etag, lastModified) = client.newCall(req).execute().use { resp ->
                if (resp.code == 304) {
                    store.markChecked(clock())
                    return@withContext UpdateResult.NotModified
                }
                if (!resp.isSuccessful) return@withContext fail("index.json HTTP ${resp.code}")
                Triple(CatalogParser.index(resp.body!!.string()), resp.header("ETag"), resp.header("Last-Modified"))
            }
            if (index.generatedAt == meta.generatedAt) {
                store.saveValidators(etag, lastModified)
                store.markChecked(clock())
                return@withContext UpdateResult.UpToDate
            }
            val cities = index.cities.map { entry ->
                CatalogParser.city(get(CatalogUrls.city(base, entry.id)), entry.id)
            }
            val changes = runCatching { CatalogParser.changes(get(CatalogUrls.changes(base))) }.getOrNull()
            store.replace(CatalogSnapshot(index, cities, changes), etag, lastModified, source = "remote")
            store.markChecked(clock())
            UpdateResult.Updated(index.generatedAt)
        } catch (e: Exception) {
            fail("${e::class.simpleName}: ${e.message}")
        }
    }

    private fun get(url: String): String =
        client.newCall(Request.Builder().url(url).build()).execute().use { resp ->
            if (!resp.isSuccessful) throw CatalogValidationException("$url HTTP ${resp.code}")
            resp.body!!.string()
        }

    private fun fail(reason: String): UpdateResult.Failed {
        runCatching { Log.w(TAG, "catalog update failed, keeping current data: $reason") }
        return UpdateResult.Failed(reason)
    }

    private companion object {
        const val TAG = "CatalogUpdater"
    }
}

/**
 * Loads the catalog bundled in the APK (assets/catalog/). Used on first launch, and when an app
 * update ships a newer bundle than what is stored.
 */
class BundledCatalogLoader(private val readAsset: (String) -> String?) {
    fun load(): CatalogSnapshot? = runCatching {
        val index = CatalogParser.index(readAsset("catalog/index.json") ?: return null)
        val cities = index.cities.map { e ->
            CatalogParser.city(readAsset("catalog/cities/${e.id}.json") ?: error("missing ${e.id}"), e.id)
        }
        val changes = readAsset("catalog/changes.json")?.let(CatalogParser::changes)
        CatalogSnapshot(index, cities, changes)
    }.getOrNull()

    /** True when the bundle should replace stored data. */
    fun shouldLoad(bundled: CatalogIndex, stored: StoredMeta): Boolean =
        stored.generatedAt == null || bundled.generatedAt > stored.generatedAt
}
