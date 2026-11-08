package app.opennaksha.feature.downloads

import android.text.format.Formatter
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.SystemUpdate
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
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
import app.opennaksha.core.data.DownloadRepository
import app.opennaksha.core.data.DownloadState
import app.opennaksha.core.data.db.DownloadEntity
import app.opennaksha.core.data.isUpdateAvailable
import app.opennaksha.core.model.SchemeRecord
import app.opennaksha.core.model.Times
import app.opennaksha.core.ui.EmptyState
import app.opennaksha.core.ui.clickableRow
import app.opennaksha.core.ui.displayName
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.mapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DownloadRow(val entity: DownloadEntity, val record: SchemeRecord?, val updateAvailable: Boolean)
data class DownloadsState(val rows: List<DownloadRow>? = null, val totalBytes: Long = 0)

@HiltViewModel
class DownloadsViewModel @Inject constructor(
    private val repo: CatalogRepository,
    private val downloads: DownloadRepository,
) : ViewModel() {
    val progress = downloads.states

    @OptIn(ExperimentalCoroutinesApi::class)
    val state: StateFlow<DownloadsState> = combine(downloads.downloads, repo.meta) { list, _ -> list }
        .mapLatest { list ->
            val rows = list.map { d ->
                val rec = repo.schemeNow(d.schemeId)
                DownloadRow(d, rec, isUpdateAvailable(d, rec))
            }
            DownloadsState(rows, downloads.totalBytes(list))
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DownloadsState())

    fun delete(url: String) = viewModelScope.launch { downloads.delete(url) }

    /** Downloads the catalog's current version of this file (same URL, or the scheme's current map). */
    fun update(row: DownloadRow) {
        val rec = row.record ?: return
        val file = rec.currentFiles.firstOrNull { it.url == row.entity.fileUrl } ?: rec.currentMap ?: return
        downloads.start(rec.id, file)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadsScreen(nav: NavController, vm: DownloadsViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val progress by vm.progress.collectAsStateWithLifecycle()
    val context = LocalContext.current

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.nav_downloads)) }) }) { padding ->
        val rows = state.rows ?: return@Scaffold
        if (rows.isEmpty()) {
            EmptyState(stringResource(R.string.downloads_empty), Modifier.padding(padding))
            return@Scaffold
        }
        LazyColumn(Modifier.padding(padding).fillMaxSize()) {
            item {
                Text(
                    stringResource(R.string.downloads_storage, Formatter.formatShortFileSize(context, state.totalBytes)),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
            items(rows, key = { it.entity.fileUrl }) { row ->
                val d = row.entity
                val running = progress[d.fileUrl] is DownloadState.Running
                ListItem(
                    headlineContent = { Text(row.record?.displayName() ?: d.schemeId) },
                    supportingContent = {
                        Text(
                            listOfNotNull(
                                d.title,
                                Formatter.formatShortFileSize(context, d.sizeBytes),
                                Times.formatDate(d.downloadedAtMs),
                                if (row.updateAvailable) stringResource(R.string.file_update_available) else null,
                            ).joinToString(" · "),
                            color = if (row.updateAvailable) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    },
                    trailingContent = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            if (running) {
                                CircularProgressIndicator(Modifier.padding(8.dp))
                            } else if (row.updateAvailable) {
                                IconButton(onClick = { vm.update(row) }) {
                                    Icon(Icons.Filled.SystemUpdate, contentDescription = stringResource(R.string.action_update))
                                }
                            }
                            IconButton(onClick = { vm.delete(d.fileUrl) }) {
                                Icon(Icons.Filled.Delete, contentDescription = stringResource(R.string.action_delete))
                            }
                        }
                    },
                    modifier = Modifier.clickableRow { nav.navigate(Routes.viewer(d.schemeId, d.fileUrl)) },
                )
            }
        }
    }
}
