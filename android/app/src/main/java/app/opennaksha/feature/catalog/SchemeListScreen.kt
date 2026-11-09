package app.opennaksha.feature.catalog

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import app.opennaksha.R
import app.opennaksha.Routes
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.data.SettingsRepository
import app.opennaksha.core.model.NaturalOrder
import app.opennaksha.core.model.SchemeStatus
import app.opennaksha.core.model.SchemeSummary
import app.opennaksha.core.model.SchemeTypes
import app.opennaksha.core.model.Times
import app.opennaksha.core.ui.BackButton
import app.opennaksha.core.ui.typeLabel
import app.opennaksha.core.ui.EmptyState
import app.opennaksha.core.ui.SchemeRow
import app.opennaksha.core.ui.isGujarati
import app.opennaksha.core.ui.statusLabel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import javax.inject.Inject

enum class SortBy { NUMBER, DATE }

data class ListFilter(
    val query: String = "",
    val status: String? = null,
    val type: String? = null,
    val sort: SortBy = SortBy.NUMBER,
)

data class ListState(
    val filter: ListFilter = ListFilter(),
    val items: List<SchemeSummary> = emptyList(),
    val cityName: String? = null,
    val previousVisitMs: Long? = null,
    val loaded: Boolean = false,
)

fun applyFilter(all: List<SchemeSummary>, f: ListFilter): List<SchemeSummary> {
    val filtered = all.filter {
        it.matches(f.query) && (f.status == null || it.status == f.status) && (f.type == null || it.schemeType == f.type)
    }
    return when (f.sort) {
        SortBy.NUMBER -> filtered.sortedWith(
            compareBy<SchemeSummary> { SchemeTypes.ALL.indexOf(it.schemeType) }
                .thenBy(NaturalOrder) { it.schemeNo }
                .thenBy { it.cityId },
        )
        SortBy.DATE -> filtered.sortedByDescending { maxOf(Times.millis(it.statusDate), it.lastChangedMs) }
    }
}

@HiltViewModel
class SchemeListViewModel @Inject constructor(
    handle: SavedStateHandle,
    repo: CatalogRepository,
    settings: SettingsRepository,
) : ViewModel() {
    val cityId: String? = handle.get<String>("city")?.takeIf { it.isNotBlank() }
    private val filter = MutableStateFlow(
        ListFilter(
            query = handle.get<String>("q").orEmpty(),
            type = handle.get<String>("type")?.takeIf { it.isNotBlank() },
        ),
    )

    private val source = if (cityId != null) repo.schemesInCity(cityId) else repo.schemes

    val state: StateFlow<ListState> = combine(source, filter, repo.cities, settings.settings) { all, f, cities, s ->
        ListState(
            filter = f,
            items = applyFilter(all, f),
            cityName = cities.firstOrNull { it.id == cityId }?.let { it.nameEn + "|" + it.nameGu },
            previousVisitMs = s.previousVisitMs,
            loaded = true,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ListState(filter.value))

    fun update(f: (ListFilter) -> ListFilter) = filter.update(f)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SchemeListScreen(nav: NavController, vm: SchemeListViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val gu = isGujarati()
    val title = state.cityName?.split("|")?.let { if (gu) it.getOrNull(1) else it.firstOrNull() }
        ?: stringResource(R.string.search_results)
    val f = state.filter

    Scaffold(topBar = { TopAppBar(title = { Text(title) }, navigationIcon = { BackButton { nav.popBackStack() } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            OutlinedTextField(
                value = f.query,
                onValueChange = { q -> vm.update { it.copy(query = q) } },
                placeholder = { Text(stringResource(R.string.search_hint), maxLines = 1, overflow = TextOverflow.Ellipsis) },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                trailingIcon = {
                    if (f.query.isNotEmpty()) {
                        IconButton(onClick = { vm.update { it.copy(query = "") } }) {
                            Icon(Icons.Filled.Clear, contentDescription = stringResource(R.string.action_clear))
                        }
                    }
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            )
            ChipRow {
                FilterChip(selected = f.status == null, onClick = { vm.update { it.copy(status = null) } }, label = { Text(stringResource(R.string.filter_all)) })
                SchemeStatus.ALL.forEach { st ->
                    FilterChip(selected = f.status == st, onClick = { vm.update { it.copy(status = if (it.status == st) null else st) } }, label = { Text(statusLabel(st)) })
                }
            }
            ChipRow {
                FilterChip(selected = f.type == null, onClick = { vm.update { it.copy(type = null) } }, label = { Text(stringResource(R.string.filter_all_types)) })
                SchemeTypes.ALL.forEach { t ->
                    FilterChip(selected = f.type == t, onClick = { vm.update { it.copy(type = if (it.type == t) null else t) } }, label = { Text(typeLabel(t)) })
                }
                FilterChip(selected = f.sort == SortBy.NUMBER, onClick = { vm.update { it.copy(sort = SortBy.NUMBER) } }, label = { Text(stringResource(R.string.sort_number)) })
                FilterChip(selected = f.sort == SortBy.DATE, onClick = { vm.update { it.copy(sort = SortBy.DATE) } }, label = { Text(stringResource(R.string.sort_date)) })
            }
            HorizontalDivider()
            if (state.loaded && state.items.isEmpty()) {
                EmptyState(stringResource(R.string.list_empty))
            } else {
                LazyColumn(Modifier.fillMaxSize()) {
                    items(state.items, key = { it.id }) { s ->
                        SchemeRow(s, state.previousVisitMs) { nav.navigate(Routes.scheme(s.id)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun ChipRow(content: @Composable () -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) { content() }
}
