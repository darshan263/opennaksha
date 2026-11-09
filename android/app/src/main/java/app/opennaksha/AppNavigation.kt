package app.opennaksha

import android.net.Uri
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.data.Settings
import app.opennaksha.core.data.SettingsRepository
import app.opennaksha.core.data.UpdateScheduler
import app.opennaksha.feature.catalog.HomeScreen
import app.opennaksha.feature.catalog.SchemeDetailScreen
import app.opennaksha.feature.catalog.SchemeListScreen
import app.opennaksha.feature.catalog.WhatsNewScreen
import app.opennaksha.feature.downloads.DownloadsScreen
import app.opennaksha.feature.map.MapScreen
import app.opennaksha.feature.settings.ConverterScreen
import app.opennaksha.feature.settings.LicensesScreen
import app.opennaksha.feature.settings.SettingsScreen
import app.opennaksha.feature.viewer.ViewerScreen
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

object Routes {
    const val HOME = "home"
    const val SCHEMES = "schemes?city={city}&q={q}&type={type}"
    const val SCHEME = "scheme/{id}"
    const val VIEWER = "viewer?id={id}&url={url}"
    const val MAP = "map?focus={focus}"
    const val WHATS_NEW = "whatsnew"
    const val DOWNLOADS = "downloads"
    const val SETTINGS = "settings"
    const val LICENSES = "licenses"
    const val CONVERTER = "converter"

    fun schemes(city: String? = null, q: String? = null, type: String? = null) =
        "schemes?city=${Uri.encode(city.orEmpty())}&q=${Uri.encode(q.orEmpty())}" +
            "&type=${Uri.encode(type.orEmpty())}"
    fun scheme(id: String) = "scheme/${Uri.encode(id)}"
    fun viewer(id: String, url: String) = "viewer?id=${Uri.encode(id)}&url=${Uri.encode(url)}"
    fun map(focus: String? = null) = "map?focus=${Uri.encode(focus.orEmpty())}"
}

/** App start: record the visit, load the bundled catalog, then check for a newer one. */
@HiltViewModel
class MainViewModel @Inject constructor(
    private val settingsRepo: SettingsRepository,
    private val catalog: CatalogRepository,
    private val scheduler: UpdateScheduler,
) : ViewModel() {
    val settings: StateFlow<Settings?> = settingsRepo.settings
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    init {
        viewModelScope.launch {
            settingsRepo.recordVisit()
            catalog.ensureBundledLoaded()
            catalog.refresh()
        }
        viewModelScope.launch {
            settingsRepo.settings.map { it.autoCheck to it.wifiOnly }.distinctUntilChanged().collect {
                scheduler.apply(settingsRepo.current())
            }
        }
    }

    fun acceptDisclaimer() = viewModelScope.launch { settingsRepo.setDisclaimerAccepted() }
}

private data class TopLevel(val route: String, val nav: String, val label: Int, val icon: ImageVector)

private val topLevel = listOf(
    TopLevel(Routes.HOME, Routes.HOME, R.string.nav_home, Icons.Filled.Home),
    TopLevel(Routes.MAP, Routes.map(), R.string.nav_map, Icons.Filled.Map),
    TopLevel(Routes.DOWNLOADS, Routes.DOWNLOADS, R.string.nav_downloads, Icons.Filled.Download),
    TopLevel(Routes.SETTINGS, Routes.SETTINGS, R.string.nav_settings, Icons.Filled.Settings),
)

@Composable
fun OpenNakshaRoot(vm: MainViewModel = hiltViewModel()) {
    val nav = rememberNavController()
    val settings by vm.settings.collectAsStateWithLifecycle()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route

    Scaffold(
        bottomBar = {
            if (topLevel.any { it.route == currentRoute }) {
                NavigationBar {
                    topLevel.forEach { item ->
                        NavigationBarItem(
                            selected = currentRoute == item.route,
                            onClick = { nav.navigateTopLevel(item.nav) },
                            icon = { Icon(item.icon, contentDescription = null) },
                            label = { Text(stringResource(item.label)) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(nav, startDestination = Routes.HOME, modifier = Modifier.padding(padding).consumeWindowInsets(padding)) {
            composable(Routes.HOME) { HomeScreen(nav) }
            composable(
                Routes.SCHEMES,
                arguments = listOf(
                    navArgument("city") { type = NavType.StringType; defaultValue = "" },
                    navArgument("q") { type = NavType.StringType; defaultValue = "" },
                    navArgument("type") { type = NavType.StringType; defaultValue = "" },
                ),
            ) { SchemeListScreen(nav) }
            composable(Routes.SCHEME, arguments = listOf(navArgument("id") { type = NavType.StringType })) {
                SchemeDetailScreen(nav)
            }
            composable(
                Routes.VIEWER,
                arguments = listOf(
                    navArgument("id") { type = NavType.StringType; defaultValue = "" },
                    navArgument("url") { type = NavType.StringType; defaultValue = "" },
                ),
            ) { ViewerScreen(nav) }
            composable(
                Routes.MAP,
                arguments = listOf(navArgument("focus") { type = NavType.StringType; defaultValue = "" }),
            ) { MapScreen(nav) }
            composable(Routes.WHATS_NEW) { WhatsNewScreen(nav) }
            composable(Routes.DOWNLOADS) { DownloadsScreen(nav) }
            composable(Routes.SETTINGS) { SettingsScreen(nav) }
            composable(Routes.LICENSES) { LicensesScreen(nav) }
            composable(Routes.CONVERTER) { ConverterScreen(nav) }
        }
    }

    if (settings?.disclaimerAccepted == false) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text(stringResource(R.string.disclaimer_title)) },
            text = { Text(stringResource(R.string.disclaimer_text)) },
            confirmButton = { TextButton(onClick = { vm.acceptDisclaimer() }) { Text(stringResource(R.string.action_accept)) } },
        )
    }
}

fun NavHostController.navigateTopLevel(route: String) = navigate(route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
