package app.opennaksha.core.data.db

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "cities")
data class CityEntity(
    @PrimaryKey val id: String,
    val nameEn: String,
    val nameGu: String,
    val schemeCount: Int,
    val updatedAt: String,
)

/** One scheme. Searchable columns are denormalized; [json] holds the full SchemeRecord. */
@Entity(tableName = "schemes")
data class SchemeEntity(
    @PrimaryKey val id: String,
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
    val json: String,
)

@Entity(tableName = "change_runs")
data class ChangeRunEntity(
    @PrimaryKey val runAt: String,
    val runAtMs: Long,
    val json: String,
)

@Entity(tableName = "meta")
data class MetaEntity(@PrimaryKey val key: String, val value: String?)

@Entity(tableName = "downloads")
data class DownloadEntity(
    @PrimaryKey val fileUrl: String,
    val schemeId: String,
    val title: String,
    val localPath: String,
    /** sha256 of the downloaded bytes. */
    val sha256: String,
    val sizeBytes: Long,
    val downloadedAtMs: Long,
)

@Entity(tableName = "recent")
data class RecentEntity(@PrimaryKey val schemeId: String, val viewedAtMs: Long)

@Dao
interface CatalogDao {
    @Query("SELECT * FROM cities ORDER BY nameEn")
    fun observeCities(): Flow<List<CityEntity>>

    @Query("SELECT * FROM schemes")
    fun observeSchemes(): Flow<List<SchemeEntity>>

    @Query("SELECT * FROM schemes WHERE cityId = :cityId")
    fun observeSchemesInCity(cityId: String): Flow<List<SchemeEntity>>

    @Query("SELECT * FROM schemes WHERE id = :id")
    fun observeScheme(id: String): Flow<SchemeEntity?>

    @Query("SELECT * FROM schemes WHERE id = :id")
    suspend fun scheme(id: String): SchemeEntity?

    @Query("SELECT * FROM schemes WHERE overlayStatus != 'none'")
    fun observeSchemesWithOverlay(): Flow<List<SchemeEntity>>

    @Query("SELECT * FROM change_runs ORDER BY runAtMs DESC")
    fun observeRuns(): Flow<List<ChangeRunEntity>>

    @Query("SELECT * FROM meta")
    fun observeMeta(): Flow<List<MetaEntity>>

    @Query("SELECT value FROM meta WHERE `key` = :key")
    suspend fun meta(key: String): String?

    @Upsert
    suspend fun putMeta(items: List<MetaEntity>)

    @Query("DELETE FROM cities")
    suspend fun clearCities()

    @Query("DELETE FROM schemes")
    suspend fun clearSchemes()

    @Query("DELETE FROM change_runs")
    suspend fun clearRuns()

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCities(items: List<CityEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSchemes(items: List<SchemeEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRuns(items: List<ChangeRunEntity>)

    /** Replaces the whole catalog atomically (all or nothing). */
    @Transaction
    suspend fun replaceCatalog(
        cities: List<CityEntity>,
        schemes: List<SchemeEntity>,
        runs: List<ChangeRunEntity>?,
        meta: List<MetaEntity>,
    ) {
        clearCities()
        clearSchemes()
        insertCities(cities)
        insertSchemes(schemes)
        if (runs != null) {
            clearRuns()
            insertRuns(runs)
        }
        putMeta(meta)
    }
}

@Dao
interface UserDao {
    @Query("SELECT * FROM downloads ORDER BY downloadedAtMs DESC")
    fun observeDownloads(): Flow<List<DownloadEntity>>

    @Query("SELECT * FROM downloads WHERE fileUrl = :url")
    suspend fun download(url: String): DownloadEntity?

    @Upsert
    suspend fun putDownload(item: DownloadEntity)

    @Query("DELETE FROM downloads WHERE fileUrl = :url")
    suspend fun deleteDownload(url: String)

    @Query("SELECT * FROM recent ORDER BY viewedAtMs DESC LIMIT :limit")
    fun observeRecent(limit: Int): Flow<List<RecentEntity>>

    @Upsert
    suspend fun putRecent(item: RecentEntity)
}

@Database(
    entities = [
        CityEntity::class, SchemeEntity::class, ChangeRunEntity::class, MetaEntity::class,
        DownloadEntity::class, RecentEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun catalogDao(): CatalogDao
    abstract fun userDao(): UserDao
}
