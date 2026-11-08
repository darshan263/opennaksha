package app.opennaksha.feature.catalog

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Calculate
import androidx.compose.material.icons.filled.NewReleases
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Badge
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import app.opennaksha.BuildConfig
import app.opennaksha.R
import app.opennaksha.Routes
import app.opennaksha.core.data.CatalogMeta
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.data.City
import app.opennaksha.core.data.SettingsRepository
import app.opennaksha.core.model.CityNews
import app.opennaksha.core.model.SchemeSummary
import app.opennaksha.core.model.Times
import app.opennaksha.core.model.compareVersions
import app.opennaksha.core.model.newsSince
import app.opennaksha.core.ui.SchemeRow
import app.opennaksha.core.ui.clickableRow
import app.opennaksha.core.ui.isGujarati
import app.opennaksha.core.ui.openUrl
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit
import javax.inject.Inject

const val ANYROR_URL = "https://anyror.gujarat.gov.in/"

data class HomeState(
    val cities: List<City> = emptyList(),
    val recent: List<SchemeSummary> = emptyList(),
    val news: List<CityNews> = emptyList(),
    val meta: CatalogMeta? = null,
    val previousVisitMs: Long? = null,
    val loaded: Boolean = false,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repo: CatalogRepository,
    settings: SettingsRepository,
) : ViewModel() {
    val refreshing = repo.refreshing

    val state: StateFlow<HomeState> = combine(
        repo.cities, repo.recent, repo.schemes, repo.meta, settings.settings,
    ) { cities, recent, schemes, meta, s ->
        // What's new since the last visit; on first launch, the last 7 days.
        val since = s.previousVisitMs ?: (System.currentTimeMillis() - TimeUnit.DAYS.toMillis(7))
        HomeState(cities, recent, newsSince(schemes, since), meta, s.previousVisitMs, loaded = true)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), HomeState())

    fun refresh() = viewModelScope.launch { repo.refresh() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(nav: NavController, vm: HomeViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var query by rememberSaveable { mutableStateOf("") }
    val gu = isGujarati()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.app_name)) },
                actions = {
                    IconButton(onClick = { nav.navigate(Routes.WHATS_NEW) }) {
                        BadgedBox(badge = { if (state.news.isNotEmpty()) Badge() }) {
                            Icon(Icons.Filled.NewReleases, contentDescription = stringResource(R.string.whats_new_title))
                        }
                    }
                },
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = refreshing,
            onRefresh = { vm.refresh() },
            modifier = Modifier.padding(padding).fillMaxSize(),
        ) {
            LazyColumn(contentPadding = PaddingValues(bottom = 24.dp), modifier = Modifier.fillMaxSize()) {
                item {
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it },
                        placeholder = { Text(stringResource(R.string.search_hint), maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = {
                            if (query.isNotBlank()) nav.navigate(Routes.schemes(q = query.trim()))
                        }),
                        trailingIcon = {
                            if (query.isNotBlank()) {
                                IconButton(onClick = { nav.navigate(Routes.schemes(q = query.trim())) }) {
                                    Icon(Icons.Filled.Search, contentDescription = stringResource(R.string.action_search))
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                    )
                }
                item {
                    val generated = state.meta?.generatedAt?.takeIf { Times.millis(it) > 0 }
                    Text(
                        generated?.let { stringResource(R.string.last_updated, Times.formatDate(it).orEmpty()) }
                            ?: stringResource(R.string.last_updated_never),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 16.dp),
                    )
                }
                val latest = state.meta?.latestAppVersion
                if (latest != null && compareVersions(latest, BuildConfig.VERSION_NAME) > 0) {
                    item {
                        Card(Modifier.fillMaxWidth().padding(16.dp)) {
                            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text(stringResource(R.string.new_version_available, latest), modifier = Modifier.weight(1f))
                                state.meta?.latestAppUrl?.let { url ->
                                    TextButton(onClick = { openUrl(context, url) }) { Text(stringResource(R.string.new_version_download)) }
                                }
                            }
                        }
                    }
                }
                if (state.news.isNotEmpty()) {
                    item {
                        Card(
                            onClick = { nav.navigate(Routes.WHATS_NEW) },
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                        ) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(stringResource(R.string.whats_new_title), style = MaterialTheme.typography.titleMedium)
                                state.news.forEach { n ->
                                    val city = state.cities.firstOrNull { it.id == n.cityId }
                                    val name = city?.let { if (gu) it.nameGu else it.nameEn } ?: n.cityId
                                    if (n.newCount > 0) Text(pluralStringResource(R.plurals.news_new, n.newCount, n.newCount, name))
                                    if (n.updatedCount > 0) Text(pluralStringResource(R.plurals.news_updated, n.updatedCount, n.updatedCount, name))
                                }
                            }
                        }
                    }
                }
                item { SectionTitle(stringResource(R.string.home_cities)) }
                if (state.loaded && state.cities.isEmpty()) {
                    item {
                        Text(
                            stringResource(R.string.home_empty),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        )
                    }
                }
                items(state.cities, key = { it.id }) { city ->
                    Card(
                        onClick = { nav.navigate(Routes.schemes(city = city.id)) },
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
                    ) {
                        Column(Modifier.padding(16.dp)) {
                            Text(if (gu) city.nameGu else city.nameEn, style = MaterialTheme.typography.titleLarge)
                            Text(
                                pluralStringResource(R.plurals.city_scheme_count, city.schemeCount, city.schemeCount),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                if (state.recent.isNotEmpty()) {
                    item { SectionTitle(stringResource(R.string.home_recent)) }
                    items(state.recent, key = { "recent-" + it.id }) { s ->
                        SchemeRow(s, state.previousVisitMs) { nav.navigate(Routes.scheme(s.id)) }
                    }
                }
                item { SectionTitle(stringResource(R.string.home_tools)) }
                item {
                    ListItem(
                        headlineContent = { Text(stringResource(R.string.tools_converter)) },
                        leadingContent = { Icon(Icons.Filled.Calculate, contentDescription = null) },
                        modifier = Modifier.clickableRow { nav.navigate(Routes.CONVERTER) },
                    )
                }
                item {
                    ListItem(
                        headlineContent = { Text(stringResource(R.string.tools_anyror)) },
                        supportingContent = { Text(stringResource(R.string.tools_anyror_desc)) },
                        leadingContent = { Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null) },
                        modifier = Modifier.clickableRow { openUrl(context, ANYROR_URL) },
                    )
                }
            }
        }
    }
}

@Composable
fun SectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 4.dp),
    )
}
