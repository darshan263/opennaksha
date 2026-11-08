package app.opennaksha.feature.settings

import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.core.os.LocaleListCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import app.opennaksha.BuildConfig
import app.opennaksha.R
import app.opennaksha.Routes
import app.opennaksha.core.config.AppConfig
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.data.OverlayRepository
import app.opennaksha.core.data.Settings
import app.opennaksha.core.data.SettingsRepository
import app.opennaksha.core.data.UpdateResult
import app.opennaksha.core.model.Times
import app.opennaksha.core.ui.clickableRow
import app.opennaksha.feature.catalog.SectionTitle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsRepo: SettingsRepository,
    private val catalog: CatalogRepository,
    private val overlays: OverlayRepository,
    private val client: OkHttpClient,
    val config: AppConfig,
) : ViewModel() {
    val settings: StateFlow<Settings> = settingsRepo.settings.stateIn(viewModelScope, SharingStarted.Eagerly, Settings())
    val meta = catalog.meta.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val refreshing = catalog.refreshing

    suspend fun checkNow(): UpdateResult = catalog.refresh()
    fun setAutoCheck(on: Boolean) = viewModelScope.launch { settingsRepo.setAutoCheck(on) }
    fun setWifiOnly(on: Boolean) = viewModelScope.launch { settingsRepo.setWifiOnly(on) }

    /** Clears the HTTP and overlay caches. Downloaded maps are kept. */
    suspend fun clearCache() = withContext(Dispatchers.IO) {
        runCatching { client.cache?.evictAll() }
        overlays.clear()
    }
}

private fun currentLanguage(): String = AppCompatDelegate.getApplicationLocales().toLanguageTags().substringBefore(',').substringBefore('-')

private fun setLanguage(tag: String) {
    AppCompatDelegate.setApplicationLocales(
        if (tag.isEmpty()) LocaleListCompat.getEmptyLocaleList() else LocaleListCompat.forLanguageTags(tag),
    )
}

private fun resultMessageRes(r: UpdateResult): Int = when (r) {
    is UpdateResult.Updated -> R.string.update_result_updated
    UpdateResult.NotModified, UpdateResult.UpToDate -> R.string.update_result_current
    UpdateResult.NotConfigured -> R.string.settings_not_configured
    is UpdateResult.Failed -> R.string.update_result_failed
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(nav: NavController, vm: SettingsViewModel = hiltViewModel()) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val meta by vm.meta.collectAsStateWithLifecycle()
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var showDisclaimer by remember { mutableStateOf(false) }
    val lang = currentLanguage()
    val messages = mapOf(
        R.string.update_result_updated to stringResource(R.string.update_result_updated),
        R.string.update_result_current to stringResource(R.string.update_result_current),
        R.string.settings_not_configured to stringResource(R.string.settings_not_configured),
        R.string.update_result_failed to stringResource(R.string.update_result_failed),
    )
    val cacheCleared = stringResource(R.string.settings_cache_cleared)

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.nav_settings)) }) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState())) {
            SectionTitle(stringResource(R.string.settings_language))
            listOf(
                "" to stringResource(R.string.settings_language_system),
                "en" to stringResource(R.string.settings_language_en),
                "gu" to stringResource(R.string.settings_language_gu),
            ).forEach { (tag, label) ->
                ListItem(
                    headlineContent = { Text(label) },
                    leadingContent = { RadioButton(selected = lang == tag, onClick = null) },
                    modifier = Modifier.selectable(selected = lang == tag, role = Role.RadioButton) { setLanguage(tag) },
                )
            }
            HorizontalDivider()

            SectionTitle(stringResource(R.string.settings_updates))
            val generated = meta?.generatedAt?.takeIf { Times.millis(it) > 0 }
            Text(
                generated?.let { stringResource(R.string.last_updated, Times.formatDate(it).orEmpty()) }
                    ?: stringResource(R.string.last_updated_never),
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            meta?.lastCheckedMs?.let {
                Text(
                    stringResource(R.string.last_checked, Times.formatDateTime(it)),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
            }
            if (vm.config.catalogBaseUrl == null) {
                Text(
                    stringResource(R.string.settings_not_configured),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
            }
            ListItem(
                headlineContent = { Text(stringResource(R.string.settings_check_now)) },
                supportingContent = if (refreshing) { { Text(stringResource(R.string.settings_checking)) } } else null,
                modifier = Modifier.clickableRow {
                    if (!refreshing) scope.launch { snackbar.showSnackbar(messages.getValue(resultMessageRes(vm.checkNow()))) }
                },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.settings_auto_check)) },
                trailingContent = { Switch(checked = settings.autoCheck, onCheckedChange = { vm.setAutoCheck(it) }) },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.settings_wifi_only)) },
                trailingContent = { Switch(checked = settings.wifiOnly, enabled = settings.autoCheck, onCheckedChange = { vm.setWifiOnly(it) }) },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.settings_clear_cache)) },
                supportingContent = { Text(stringResource(R.string.settings_clear_cache_desc)) },
                modifier = Modifier.clickableRow {
                    scope.launch {
                        vm.clearCache()
                        snackbar.showSnackbar(cacheCleared)
                    }
                },
            )
            HorizontalDivider()

            SectionTitle(stringResource(R.string.home_tools))
            ListItem(
                headlineContent = { Text(stringResource(R.string.tools_converter)) },
                modifier = Modifier.clickableRow { nav.navigate(Routes.CONVERTER) },
            )
            HorizontalDivider()

            SectionTitle(stringResource(R.string.settings_about))
            ListItem(
                headlineContent = { Text(stringResource(R.string.settings_version, BuildConfig.VERSION_NAME)) },
                supportingContent = { Text(stringResource(R.string.settings_about_text)) },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.disclaimer_title)) },
                modifier = Modifier.clickableRow { showDisclaimer = true },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.settings_licenses)) },
                modifier = Modifier.clickableRow { nav.navigate(Routes.LICENSES) },
            )
        }
    }

    if (showDisclaimer) {
        AlertDialog(
            onDismissRequest = { showDisclaimer = false },
            title = { Text(stringResource(R.string.disclaimer_title)) },
            text = { Text(stringResource(R.string.disclaimer_text)) },
            confirmButton = { TextButton(onClick = { showDisclaimer = false }) { Text(stringResource(R.string.action_ok)) } },
        )
    }
}
