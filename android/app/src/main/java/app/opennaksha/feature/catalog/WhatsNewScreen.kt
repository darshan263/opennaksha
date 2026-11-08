package app.opennaksha.feature.catalog

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import app.opennaksha.R
import app.opennaksha.Routes
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.model.RunChanges
import app.opennaksha.core.model.SchemeSummary
import app.opennaksha.core.model.Times
import app.opennaksha.core.ui.BackButton
import app.opennaksha.core.ui.EmptyState
import app.opennaksha.core.ui.changeLabel
import app.opennaksha.core.ui.clickableRow
import app.opennaksha.core.ui.displayName
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import java.time.LocalDate
import javax.inject.Inject

/** One line in the What's new list. */
sealed interface NewsItem {
    data class Header(val day: LocalDate) : NewsItem
    data class Section(val title: Int) : NewsItem
    data class Entry(val id: String, val scheme: SchemeSummary?, val what: List<String>) : NewsItem
    data class Failed(val sources: List<String>) : NewsItem
}

/** Groups runs by day (newest first) into display rows. */
fun buildNews(runs: List<RunChanges>, schemes: Map<String, SchemeSummary>): List<NewsItem> {
    val out = mutableListOf<NewsItem>()
    runs.sortedByDescending { Times.millis(it.runAt) }.groupBy { Times.localDay(it.runAt) }.forEach { (day, dayRuns) ->
        out += NewsItem.Header(day)
        val new = dayRuns.flatMap { it.new }.distinct()
        val changed = dayRuns.flatMap { it.changed }.groupBy { it.id }.map { (id, c) -> id to c.flatMap { it.what }.distinct() }
        val removed = dayRuns.flatMap { it.removedFromSource }.distinct()
        if (new.isNotEmpty()) {
            out += NewsItem.Section(R.string.change_new)
            new.forEach { out += NewsItem.Entry(it, schemes[it], emptyList()) }
        }
        if (changed.isNotEmpty()) {
            out += NewsItem.Section(R.string.change_changed)
            changed.forEach { (id, what) -> out += NewsItem.Entry(id, schemes[id], what) }
        }
        if (removed.isNotEmpty()) {
            out += NewsItem.Section(R.string.change_removed)
            removed.forEach { out += NewsItem.Entry(it, schemes[it], emptyList()) }
        }
        val failed = dayRuns.flatMap { it.failedSources }.distinct()
        if (failed.isNotEmpty() && new.isEmpty() && changed.isEmpty() && removed.isEmpty()) {
            out.removeAt(out.lastIndex) // a day with only failures isn't news for users
        }
    }
    return out
}

@HiltViewModel
class WhatsNewViewModel @Inject constructor(repo: CatalogRepository) : ViewModel() {
    val items: StateFlow<List<NewsItem>?> = combine(repo.runs, repo.schemes) { runs, schemes ->
        buildNews(runs, schemes.associateBy { it.id })
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WhatsNewScreen(nav: NavController, vm: WhatsNewViewModel = hiltViewModel()) {
    val items by vm.items.collectAsStateWithLifecycle()
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.whats_new_title)) }, navigationIcon = { BackButton { nav.popBackStack() } }) },
    ) { padding ->
        val list = items ?: return@Scaffold
        if (list.isEmpty()) {
            EmptyState(stringResource(R.string.whats_new_empty), Modifier.padding(padding))
            return@Scaffold
        }
        LazyColumn(Modifier.padding(padding).fillMaxSize()) {
            items(list) { item ->
                when (item) {
                    is NewsItem.Header -> Text(
                        Times.formatDate(item.day.toString()).orEmpty(),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(start = 16.dp, top = 20.dp, bottom = 4.dp),
                    )
                    is NewsItem.Section -> Text(
                        stringResource(item.title),
                        style = MaterialTheme.typography.labelLarge,
                        modifier = Modifier.padding(start = 16.dp, top = 8.dp),
                    )
                    is NewsItem.Entry -> ListItem(
                        headlineContent = { Text(item.scheme?.displayName() ?: item.id) },
                        supportingContent = if (item.what.isEmpty()) null else {
                            { Text(item.what.map { changeLabel(it) }.joinToString(", ")) }
                        },
                        modifier = if (item.scheme != null) Modifier.clickableRow { nav.navigate(Routes.scheme(item.id)) } else Modifier,
                    )
                    is NewsItem.Failed -> {}
                }
            }
        }
    }
}
