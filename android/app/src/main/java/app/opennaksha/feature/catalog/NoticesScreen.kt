package app.opennaksha.feature.catalog

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
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
import app.opennaksha.core.data.SettingsRepository
import app.opennaksha.core.model.Badge
import app.opennaksha.core.model.Notice
import app.opennaksha.core.model.Times
import app.opennaksha.core.ui.BackButton
import app.opennaksha.core.ui.BadgeChip
import app.opennaksha.core.ui.EmptyState
import app.opennaksha.core.ui.clickableRow
import app.opennaksha.core.ui.openUrl
import app.opennaksha.core.ui.typeLabel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

const val TPVD_NOTICES_URL = "https://townplanning.gujarat.gov.in/ecitizen/Notifications"

/**
 * Notices first seen after the returned time get a "New" badge: since the Notices screen was last
 * opened, else since the previous app visit. On first launch nothing is new (everything is).
 */
fun noticesNewSince(noticesSeenMs: Long?, previousVisitMs: Long?): Long =
    noticesSeenMs ?: previousVisitMs ?: Long.MAX_VALUE

fun countNewNotices(notices: List<Notice>, sinceMs: Long): Int =
    notices.count { Times.millis(it.firstSeen) > sinceMs }

data class NoticesState(val notices: List<Notice>? = null, val newSinceMs: Long = Long.MAX_VALUE)

@HiltViewModel
class NoticesViewModel @Inject constructor(
    repo: CatalogRepository,
    private val settings: SettingsRepository,
) : ViewModel() {
    // Captured before marking the screen as seen, so this visit still shows the badges.
    private val since = MutableStateFlow<Long?>(null)

    val state: StateFlow<NoticesState> = combine(repo.notices, since) { notices, s ->
        NoticesState(if (s == null) null else notices, s ?: Long.MAX_VALUE)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), NoticesState())

    init {
        viewModelScope.launch {
            val s = settings.current()
            since.value = noticesNewSince(s.noticesSeenMs, s.previousVisitMs)
            settings.markNoticesSeen()
        }
    }
}

private val FILTERS = listOf("", "TP", "DP", "other")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NoticesScreen(nav: NavController, vm: NoticesViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var filter by rememberSaveable { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.notices_title)) },
                navigationIcon = { BackButton { nav.popBackStack() } },
            )
        },
    ) { padding ->
        val all = state.notices ?: return@Scaffold
        if (all.isEmpty()) {
            EmptyState(stringResource(R.string.notices_empty), Modifier.padding(padding))
            return@Scaffold
        }
        val shown = if (filter.isEmpty()) all else all.filter { it.kind == filter }
        LazyColumn(Modifier.padding(padding).fillMaxSize()) {
            item {
                Text(
                    stringResource(R.string.notices_source),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp),
                )
                TextButton(onClick = { openUrl(context, TPVD_NOTICES_URL) }, modifier = Modifier.padding(start = 4.dp)) {
                    Text(stringResource(R.string.notices_open_source))
                }
            }
            item {
                Row(
                    Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    FILTERS.forEach { f ->
                        val count = if (f.isEmpty()) all.size else all.count { it.kind == f }
                        if (count == 0) return@forEach
                        val label = when (f) {
                            "" -> stringResource(R.string.notices_filter_all)
                            "other" -> stringResource(R.string.notices_filter_other)
                            else -> typeLabel(f)
                        }
                        FilterChip(
                            selected = filter == f,
                            onClick = { filter = f },
                            label = { Text(stringResource(R.string.type_count, label, count)) },
                        )
                    }
                }
            }
            items(shown, key = { it.id }) { n ->
                val isNew = Times.millis(n.firstSeen) > state.newSinceMs
                ListItem(
                    headlineContent = { Text(n.title, maxLines = 4) },
                    supportingContent = {
                        Text(
                            listOfNotNull(Times.formatDate(n.date), n.referenceNo, n.description).joinToString(" · "),
                            maxLines = 3,
                        )
                    },
                    trailingContent = if (isNew) {
                        { BadgeChip(Badge.NEW) }
                    } else {
                        null
                    },
                    modifier = Modifier.fillMaxWidth().clickableRow {
                        nav.navigate(Routes.viewer("notice:${n.id}", n.url, n.title))
                    },
                )
            }
        }
    }
}
