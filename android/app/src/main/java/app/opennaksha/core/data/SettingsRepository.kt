package app.opennaksha.core.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "settings")

data class Settings(
    val disclaimerAccepted: Boolean = false,
    val autoCheck: Boolean = true,
    val wifiOnly: Boolean = true,
    /** Start of the previous app session (for "New"/"Updated" badges); null on first launch. */
    val previousVisitMs: Long? = null,
)

/** App settings in DataStore. The UI language is stored by AppCompat (per-app locales). */
@Singleton
class SettingsRepository @Inject constructor(@ApplicationContext private val context: Context) {
    private object Keys {
        val DISCLAIMER = booleanPreferencesKey("disclaimer_accepted")
        val AUTO_CHECK = booleanPreferencesKey("auto_check")
        val WIFI_ONLY = booleanPreferencesKey("wifi_only")
        val LAST_VISIT = longPreferencesKey("last_visit_ms")
        val PREVIOUS_VISIT = longPreferencesKey("previous_visit_ms")
    }

    val settings: Flow<Settings> = context.dataStore.data.map { p ->
        Settings(
            disclaimerAccepted = p[Keys.DISCLAIMER] ?: false,
            autoCheck = p[Keys.AUTO_CHECK] ?: true,
            wifiOnly = p[Keys.WIFI_ONLY] ?: true,
            previousVisitMs = p[Keys.PREVIOUS_VISIT],
        )
    }

    suspend fun current(): Settings = settings.first()

    /** Call once per app start: the last visit becomes the "previous visit" used for badges. */
    suspend fun recordVisit(nowMs: Long = System.currentTimeMillis()) {
        context.dataStore.edit { p ->
            p[Keys.LAST_VISIT]?.let { p[Keys.PREVIOUS_VISIT] = it }
            p[Keys.LAST_VISIT] = nowMs
        }
    }

    suspend fun setDisclaimerAccepted() = context.dataStore.edit { it[Keys.DISCLAIMER] = true }
    suspend fun setAutoCheck(on: Boolean) = context.dataStore.edit { it[Keys.AUTO_CHECK] = on }
    suspend fun setWifiOnly(on: Boolean) = context.dataStore.edit { it[Keys.WIFI_ONLY] = on }
}
