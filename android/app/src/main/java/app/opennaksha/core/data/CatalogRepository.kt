package app.opennaksha.core.data

import android.content.Context
import android.util.Log
import app.opennaksha.core.config.AppConfig
import app.opennaksha.core.data.db.CatalogDao
import app.opennaksha.core.data.db.ChangeRunEntity
import app.opennaksha.core.data.db.CityEntity
import app.opennaksha.core.data.db.MetaEntity
import app.opennaksha.core.data.db.RecentEntity
import app.opennaksha.core.data.db.SchemeEntity
import app.opennaksha.core.data.db.UserDao
import app.opennaksha.core.model.CatalogJson
import app.opennaksha.core.model.RunChanges
import app.opennaksha.core.model.SchemeRecord
import app.opennaksha.core.model.SchemeSummary
import app.opennaksha.core.model.Times
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import javax.inject.Inject
import javax.inject.Singleton

data class CatalogMeta(
    val generatedAt: String?,
    val lastCheckedMs: Long?,
    val latestAppVersion: String?,
    val latestAppUrl: String?,
)

data class City(val id: String, val nameEn: String, val nameGu: String, val schemeCount: Int, val updatedAt: String)

private object MetaKeys {
    const val GENERATED_AT = "generated_at"
    const val ETAG = "etag"
    const val LAST_MODIFIED = "last_modified"
    const val LAST_CHECKED = "last_checked_ms"
    const val SOURCE = "source"
    const val APP_VERSION = "latest_app_version"
    const val APP_URL = "latest_app_url"
}

@Singleton
class CatalogRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dao: CatalogDao,
    private val userDao: UserDao,
    private val config: AppConfig,
    private val client: OkHttpClient,
) : CatalogStore {
    private val updateLock = Mutex()
    private val _refreshing = MutableStateFlow(false)
    val refreshing: StateFlow<Boolean> = _refreshing

    val cities: Flow<List<City>> = dao.observeCities().map { list ->
        list.map { City(it.id, it.nameEn, it.nameGu, it.schemeCount, it.updatedAt) }
    }

    val schemes: Flow<List<SchemeSummary>> = dao.observeSchemes().map { it.map(::summary) }

    fun schemesInCity(cityId: String): Flow<List<SchemeSummary>> =
        dao.observeSchemesInCity(cityId).map { it.map(::summary) }

    fun scheme(id: String): Flow<SchemeRecord?> = dao.observeScheme(id).map { it?.let(::decode) }

    suspend fun schemeNow(id: String): SchemeRecord? = dao.scheme(id)?.let(::decode)

    val overlaySchemes: Flow<List<SchemeRecord>> =
        dao.observeSchemesWithOverlay().map { list -> list.map(::decode).filter { it.hasOverlay } }

    val runs: Flow<List<RunChanges>> = dao.observeRuns().map { list ->
        list.mapNotNull { runCatching { CatalogJson.decodeFromString(RunChanges.serializer(), it.json) }.getOrNull() }
    }

    val meta: Flow<CatalogMeta> = dao.observeMeta().map { list ->
        val m = list.associate { it.key to it.value }
        CatalogMeta(
            generatedAt = m[MetaKeys.GENERATED_AT],
            lastCheckedMs = m[MetaKeys.LAST_CHECKED]?.toLongOrNull(),
            latestAppVersion = m[MetaKeys.APP_VERSION],
            latestAppUrl = m[MetaKeys.APP_URL],
        )
    }

    val recent: Flow<List<SchemeSummary>> = combine(userDao.observeRecent(10), schemes) { recent, all ->
        val byId = all.associateBy { it.id }
        recent.mapNotNull { byId[it.schemeId] }
    }

    suspend fun markViewed(id: String) = userDao.putRecent(RecentEntity(id, System.currentTimeMillis()))

    /** First launch (or newer bundle in an updated APK): copy assets/catalog into Room. */
    suspend fun ensureBundledLoaded() = withContext(Dispatchers.IO) {
        updateLock.withLock {
            val loader = BundledCatalogLoader { path ->
                runCatching { context.assets.open(path).bufferedReader().use { it.readText() } }.getOrNull()
            }
            val snapshot = loader.load() ?: return@withLock
            if (loader.shouldLoad(snapshot.index, storedMeta())) {
                replace(snapshot, etag = null, lastModified = null, source = "bundled")
                Log.i(TAG, "loaded bundled catalog ${snapshot.index.generatedAt}")
            }
        }
    }

    /** Checks GitHub Pages for a newer catalog. Never throws. */
    suspend fun refresh(): UpdateResult = updateLock.withLock {
        _refreshing.value = true
        try {
            CatalogUpdater(client, config.catalogBaseUrl, this).update()
        } finally {
            _refreshing.value = false
        }
    }

    // ---------------------------------------------------------------- CatalogStore

    override suspend fun storedMeta() = StoredMeta(
        generatedAt = dao.meta(MetaKeys.GENERATED_AT),
        etag = dao.meta(MetaKeys.ETAG),
        lastModified = dao.meta(MetaKeys.LAST_MODIFIED),
    )

    override suspend fun replace(snapshot: CatalogSnapshot, etag: String?, lastModified: String?, source: String) {
        val cities = snapshot.index.cities.map { CityEntity(it.id, it.nameEn, it.nameGu, it.schemeCount, it.updatedAt) }
        val schemes = snapshot.cities.flatMap { it.schemes }.map(::entity)
        val runs = snapshot.changes?.runs?.map {
            ChangeRunEntity(it.runAt, Times.millis(it.runAt), CatalogJson.encodeToString(RunChanges.serializer(), it))
        }
        dao.replaceCatalog(
            cities, schemes, runs,
            listOf(
                MetaEntity(MetaKeys.GENERATED_AT, snapshot.index.generatedAt),
                MetaEntity(MetaKeys.ETAG, etag),
                MetaEntity(MetaKeys.LAST_MODIFIED, lastModified),
                MetaEntity(MetaKeys.SOURCE, source),
                MetaEntity(MetaKeys.APP_VERSION, snapshot.index.latestAppVersion),
                MetaEntity(MetaKeys.APP_URL, snapshot.index.latestAppUrl),
            ),
        )
    }

    override suspend fun saveValidators(etag: String?, lastModified: String?) =
        dao.putMeta(listOf(MetaEntity(MetaKeys.ETAG, etag), MetaEntity(MetaKeys.LAST_MODIFIED, lastModified)))

    override suspend fun markChecked(nowMs: Long) =
        dao.putMeta(listOf(MetaEntity(MetaKeys.LAST_CHECKED, nowMs.toString())))

    // ---------------------------------------------------------------- mapping

    private fun decode(e: SchemeEntity): SchemeRecord = CatalogJson.decodeFromString(SchemeRecord.serializer(), e.json)

    private fun entity(s: SchemeRecord) = SchemeEntity(
        id = s.id, cityId = s.cityId, authority = s.authority, schemeType = s.schemeType, schemeNo = s.schemeNo,
        nameEn = s.nameEn, nameGu = s.nameGu, status = s.status, statusLabel = s.statusLabel, statusDate = s.statusDate,
        firstSeenMs = Times.millis(s.firstSeen), lastChangedMs = Times.millis(s.lastChanged),
        removedFromSource = s.removedFromSource, overlayStatus = if (s.hasOverlay) s.overlay.status else "none",
        json = CatalogJson.encodeToString(SchemeRecord.serializer(), s),
    )

    private fun summary(e: SchemeEntity) = SchemeSummary(
        id = e.id, cityId = e.cityId, authority = e.authority, schemeType = e.schemeType, schemeNo = e.schemeNo,
        nameEn = e.nameEn, nameGu = e.nameGu, status = e.status, statusLabel = e.statusLabel, statusDate = e.statusDate,
        firstSeenMs = e.firstSeenMs, lastChangedMs = e.lastChangedMs, removedFromSource = e.removedFromSource,
        overlayStatus = e.overlayStatus,
    )

    private companion object {
        const val TAG = "CatalogRepository"
    }
}
