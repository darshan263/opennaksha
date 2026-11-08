package app.opennaksha.feature.catalog

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.SystemUpdate
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
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
import app.opennaksha.core.data.City
import app.opennaksha.core.data.DownloadRepository
import app.opennaksha.core.data.DownloadState
import app.opennaksha.core.data.db.DownloadEntity
import app.opennaksha.core.data.isUpdateAvailable
import app.opennaksha.core.model.FileEntry
import app.opennaksha.core.model.SchemeRecord
import app.opennaksha.core.model.Times
import app.opennaksha.core.ui.BackButton
import app.opennaksha.core.ui.EmptyState
import app.opennaksha.core.ui.LabeledValue
import app.opennaksha.core.ui.displayName
import app.opennaksha.core.ui.fileKindLabel
import app.opennaksha.core.ui.isGujarati
import app.opennaksha.core.ui.openUrl
import app.opennaksha.core.ui.reportIntent
import app.opennaksha.core.ui.shareText
import app.opennaksha.core.ui.startSafely
import app.opennaksha.core.ui.statusLabel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailState(
    val record: SchemeRecord? = null,
    val city: City? = null,
    val downloads: Map<String, DownloadEntity> = emptyMap(),
    val progress: Map<String, DownloadState> = emptyMap(),
    val loaded: Boolean = false,
)

@HiltViewModel
class SchemeDetailViewModel @Inject constructor(
    handle: SavedStateHandle,
    private val repo: CatalogRepository,
    private val downloads: DownloadRepository,
) : ViewModel() {
    val id: String = handle.get<String>("id").orEmpty()

    val state: StateFlow<DetailState> = combine(
        repo.scheme(id), repo.cities, downloads.downloads, downloads.states,
    ) { record, cities, dl, progress ->
        DetailState(record, cities.firstOrNull { it.id == record?.cityId }, dl.associateBy { it.fileUrl }, progress, loaded = true)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DetailState())

    init {
        viewModelScope.launch { repo.markViewed(id) }
    }

    fun download(file: FileEntry) = downloads.start(id, file)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SchemeDetailScreen(nav: NavController, vm: SchemeDetailViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val record = state.record

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(record?.displayName() ?: "") },
                navigationIcon = { BackButton { nav.popBackStack() } },
                actions = {
                    if (record != null) {
                        val shareBody = stringResource(R.string.share_scheme_text, record.displayName(), record.sourcePageUrl)
                        IconButton(onClick = { shareText(context, shareBody) }) {
                            Icon(Icons.Filled.Share, contentDescription = stringResource(R.string.action_share))
                        }
                    }
                },
            )
        },
    ) { padding ->
        if (record == null) {
            if (state.loaded) EmptyState(stringResource(R.string.detail_not_found), Modifier.padding(padding))
            return@Scaffold
        }
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (record.removedFromSource) {
                Notice(stringResource(R.string.detail_removed), error = true)
            }
            record.mapUpdatedAt?.let { Notice(stringResource(R.string.detail_map_updated, Times.formatDate(it).orEmpty())) }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    val gu = isGujarati()
                    state.city?.let { LabeledValue(stringResource(R.string.detail_city), if (gu) it.nameGu else it.nameEn) }
                    LabeledValue(stringResource(R.string.detail_authority), record.authority)
                    LabeledValue(stringResource(R.string.detail_status), statusLabel(record.status))
                    record.statusLabel?.takeIf { it.isNotBlank() }?.let { LabeledValue(stringResource(R.string.detail_status_source), it) }
                    Times.formatDate(record.statusDate)?.let { LabeledValue(stringResource(R.string.detail_status_date), it) }
                    record.nameEn?.let { LabeledValue(stringResource(R.string.detail_name_en), it) }
                    record.nameGu?.let { LabeledValue(stringResource(R.string.detail_name_gu), it) }
                    Times.formatDate(record.firstSeen)?.let { LabeledValue(stringResource(R.string.detail_first_seen), it) }
                }
            }

            Button(onClick = { openUrl(context, record.sourcePageUrl) }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null)
                Spacer(Modifier.padding(4.dp))
                Text(stringResource(R.string.detail_open_source))
            }
            if (record.hasOverlay) {
                OutlinedButton(onClick = { nav.navigate(Routes.map(record.id)) }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.Map, contentDescription = null)
                    Spacer(Modifier.padding(4.dp))
                    Text(stringResource(R.string.detail_view_on_map))
                }
                if (record.overlay.isOutdated) Notice(stringResource(R.string.map_outdated), error = true)
            }

            Text(stringResource(R.string.detail_files), style = MaterialTheme.typography.titleMedium)
            record.currentFiles.forEach { file ->
                FileRow(
                    file = file,
                    download = state.downloads[file.url],
                    progress = state.progress[file.url],
                    updateAvailable = state.downloads[file.url]?.let { isUpdateAvailable(it, record) } == true,
                    onOpen = { nav.navigate(Routes.viewer(record.id, file.url)) },
                    onDownload = { vm.download(file) },
                    onBrowser = { openUrl(context, file.url) },
                )
                HorizontalDivider()
            }
            if (record.olderFiles.isNotEmpty()) {
                Text(stringResource(R.string.detail_older_files), style = MaterialTheme.typography.titleSmall)
                record.olderFiles.forEach { file ->
                    ListItem(
                        headlineContent = { Text(file.title) },
                        supportingContent = { Text(listOfNotNull(fileKindLabel(file.kind), Times.formatDate(file.firstSeen)).joinToString(" · ")) },
                        trailingContent = {
                            IconButton(onClick = { openUrl(context, file.url) }) {
                                Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = stringResource(R.string.action_open_browser))
                            }
                        },
                    )
                }
            }

            reportIntent(context, record)?.let { intent ->
                TextButton(onClick = { startSafely(context, intent) }) { Text(stringResource(R.string.detail_report)) }
            }
            Text(
                stringResource(R.string.disclaimer_short),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun FileRow(
    file: FileEntry,
    download: DownloadEntity?,
    progress: DownloadState?,
    updateAvailable: Boolean,
    onOpen: () -> Unit,
    onDownload: () -> Unit,
    onBrowser: () -> Unit,
) {
    val context = LocalContext.current
    Column {
        ListItem(
            headlineContent = { Text(file.title) },
            supportingContent = {
                Text(
                    listOfNotNull(
                        fileKindLabel(file.kind),
                        file.sizeBytes?.let { Formatter.formatShortFileSize(context, it) },
                        when {
                            updateAvailable -> stringResource(R.string.file_update_available)
                            download != null -> stringResource(R.string.file_downloaded)
                            else -> null
                        },
                    ).joinToString(" · "),
                )
            },
            leadingContent = {
                when {
                    updateAvailable -> Icon(Icons.Filled.SystemUpdate, contentDescription = stringResource(R.string.file_update_available), tint = MaterialTheme.colorScheme.secondary)
                    download != null -> Icon(Icons.Filled.CheckCircle, contentDescription = stringResource(R.string.file_downloaded), tint = MaterialTheme.colorScheme.primary)
                    else -> null
                }
            },
            modifier = Modifier,
        )
        when (progress) {
            is DownloadState.Running -> {
                val f = progress.fraction
                if (f != null) LinearProgressIndicator(progress = { f }, modifier = Modifier.fillMaxWidth()) else LinearProgressIndicator(Modifier.fillMaxWidth())
            }
            is DownloadState.Failed -> Text(
                stringResource(R.string.download_failed, progress.message),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
            null -> {}
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            if (file.url.isViewable()) {
                TextButton(onClick = onOpen) { Text(stringResource(R.string.action_open)) }
            }
            when {
                progress is DownloadState.Running -> CircularProgressIndicator(Modifier.padding(8.dp))
                updateAvailable -> TextButton(onClick = onDownload) {
                    Icon(Icons.Filled.SystemUpdate, contentDescription = null)
                    Text(stringResource(R.string.action_update))
                }
                download == null -> TextButton(onClick = onDownload) {
                    Icon(Icons.Filled.Download, contentDescription = null)
                    Text(stringResource(R.string.action_download))
                }
            }
            TextButton(onClick = onBrowser) { Text(stringResource(R.string.action_open_browser)) }
        }
    }
}

/** Files the in-app viewer can show: PDFs and JPG/PNG maps (links without an extension are checked by their bytes). */
private fun String.isViewable(): Boolean {
    val path = substringBefore('?').lowercase()
    return !Regex("""\.(zip|rar|dwg|dxf|kmz?|docx?|xlsx?|pptx?)$""").containsMatchIn(path)
}

@Composable
fun Notice(text: String, error: Boolean = false) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (error) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Warning, contentDescription = null)
            Spacer(Modifier.padding(6.dp))
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

