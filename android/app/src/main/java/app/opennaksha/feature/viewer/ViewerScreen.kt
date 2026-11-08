package app.opennaksha.feature.viewer

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import app.opennaksha.R
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.data.DownloadRepository
import app.opennaksha.core.data.DownloadState
import app.opennaksha.core.model.FileEntry
import app.opennaksha.core.ui.BackButton
import app.opennaksha.core.ui.openUrl
import app.opennaksha.core.ui.startSafely
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

sealed interface ViewerState {
    data object Loading : ViewerState
    data class Downloading(val fraction: Float?) : ViewerState
    data class Ready(val file: File, val title: String) : ViewerState
    data class Error(val message: String) : ViewerState
}

@HiltViewModel
class ViewerViewModel @Inject constructor(
    handle: SavedStateHandle,
    private val repo: CatalogRepository,
    private val downloads: DownloadRepository,
) : ViewModel() {
    val schemeId: String = handle.get<String>("id").orEmpty()
    val url: String = handle.get<String>("url").orEmpty()
    private var file: FileEntry? = null

    val state: StateFlow<ViewerState> = combine(downloads.downloads, downloads.states) { list, states ->
        val dl = list.firstOrNull { it.fileUrl == url }?.takeIf { File(it.localPath).exists() }
        when (val s = states[url]) {
            is DownloadState.Running -> if (dl != null) ViewerState.Ready(File(dl.localPath), dl.title) else ViewerState.Downloading(s.fraction)
            is DownloadState.Failed -> if (dl != null) ViewerState.Ready(File(dl.localPath), dl.title) else ViewerState.Error(s.message)
            null -> if (dl != null) ViewerState.Ready(File(dl.localPath), dl.title) else ViewerState.Loading
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ViewerState.Loading)

    init {
        viewModelScope.launch {
            repo.markViewed(schemeId)
            if (downloads.downloaded(url) == null) start()
        }
    }

    fun start() = viewModelScope.launch {
        val f = file ?: repo.schemeNow(schemeId)?.files?.firstOrNull { it.url == url }
            ?: FileEntry(kind = "map", title = url.substringAfterLast('/'), url = url, firstSeen = "")
        file = f
        downloads.start(schemeId, f)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ViewerScreen(nav: NavController, vm: ViewerViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val ready = state as? ViewerState.Ready

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(ready?.title ?: "", maxLines = 1) },
                navigationIcon = { BackButton { nav.popBackStack() } },
                actions = {
                    if (ready != null) {
                        val shareTitle = stringResource(R.string.share_pdf_title)
                        IconButton(onClick = {
                            val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", ready.file)
                            val mime = DocType.detect(ready.file)?.mime ?: "application/octet-stream"
                            val send = Intent(Intent.ACTION_SEND).setType(mime)
                                .putExtra(Intent.EXTRA_STREAM, uri)
                                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            startSafely(context, Intent.createChooser(send, shareTitle))
                        }) { Icon(Icons.Filled.Share, contentDescription = stringResource(R.string.action_share)) }
                    }
                    IconButton(onClick = { openUrl(context, vm.url) }) {
                        Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = stringResource(R.string.action_open_browser))
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            when (val s = state) {
                ViewerState.Loading -> Centered { CircularProgressIndicator() }
                is ViewerState.Downloading -> Centered {
                    Text(
                        s.fraction?.let { stringResource(R.string.download_progress, (it * 100).toInt()) }
                            ?: stringResource(R.string.download_progress_unknown),
                    )
                    val f = s.fraction
                    if (f != null) {
                        LinearProgressIndicator(progress = { f }, modifier = Modifier.fillMaxWidth().padding(top = 16.dp))
                    } else {
                        LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 16.dp))
                    }
                }
                is ViewerState.Error -> Centered {
                    Text(stringResource(R.string.viewer_error_title), style = MaterialTheme.typography.titleMedium)
                    Text(stringResource(R.string.viewer_error_body), textAlign = TextAlign.Center)
                    Text(s.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = { vm.start() }) { Text(stringResource(R.string.action_retry)) }
                        OutlinedButton(onClick = { openUrl(context, vm.url) }) { Text(stringResource(R.string.action_open_browser)) }
                    }
                }
                is ViewerState.Ready -> PdfContent(s.file)
            }
        }
    }
}

@Composable
private fun PdfContent(file: File) {
    val doc = remember(file) { DocType.open(file) }
    DisposableEffect(doc) { onDispose { doc?.close() } }
    if (doc == null || doc.pageCount == 0) {
        Centered { Text(stringResource(R.string.viewer_invalid)) }
        return
    }
    var page by remember(doc) { mutableIntStateOf(0) }
    Column(Modifier.fillMaxSize()) {
        PdfPageView(doc, page, Modifier.weight(1f))
        if (doc.pageCount > 1) {
            Surface(tonalElevation = 3.dp) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    IconButton(onClick = { page-- }, enabled = page > 0) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = stringResource(R.string.viewer_prev_page))
                    }
                    Text(stringResource(R.string.viewer_page, page + 1, doc.pageCount))
                    IconButton(onClick = { page++ }, enabled = page < doc.pageCount - 1) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = stringResource(R.string.viewer_next_page))
                    }
                }
            }
        }
    }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) { content() }
}
