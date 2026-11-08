package app.opennaksha.core.data

import android.content.Context
import app.opennaksha.core.data.db.DownloadEntity
import app.opennaksha.core.data.db.UserDao
import app.opennaksha.core.model.FileEntry
import app.opennaksha.core.model.SchemeRecord
import app.opennaksha.feature.viewer.DocType
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import javax.inject.Inject
import javax.inject.Singleton

sealed interface DownloadState {
    data class Running(val bytes: Long, val total: Long?) : DownloadState {
        val fraction: Float? get() = total?.takeIf { it > 0 }?.let { bytes.toFloat() / it }
    }
    data class Failed(val message: String) : DownloadState
}

/**
 * True when the catalog lists a different version of a downloaded file: the current entry for the
 * same URL has a different sha256, or the URL is no longer current and another map file is.
 */
fun isUpdateAvailable(download: DownloadEntity, record: SchemeRecord?): Boolean {
    if (record == null) return false
    val current = record.currentFiles.firstOrNull { it.url == download.fileUrl }
    if (current != null) return current.sha256 != null && current.sha256 != download.sha256
    val replacedMap = record.files.any { it.url == download.fileUrl && it.kind == "map" }
    return replacedMap && record.currentFiles.any { it.kind == "map" }
}

/**
 * Downloads PDFs directly from the official URLs into app storage (files/pdfs/). An update
 * downloads to a temp file first; the old copy is replaced only after the new one succeeds.
 */
@Singleton
class DownloadRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dao: UserDao,
    private val client: OkHttpClient,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jobs = mutableMapOf<String, Job>()
    private val _states = MutableStateFlow<Map<String, DownloadState>>(emptyMap())
    val states: StateFlow<Map<String, DownloadState>> = _states

    val downloads: Flow<List<DownloadEntity>> = dao.observeDownloads()

    private val dir: File get() = File(context.filesDir, "pdfs").apply { mkdirs() }

    suspend fun downloaded(url: String): DownloadEntity? = dao.download(url)?.takeIf { File(it.localPath).exists() }

    fun start(schemeId: String, file: FileEntry) {
        synchronized(jobs) {
            if (jobs[file.url]?.isActive == true) return
            jobs[file.url] = scope.launch { run(schemeId, file) }
        }
    }

    fun cancel(url: String) {
        synchronized(jobs) { jobs.remove(url)?.cancel() }
        _states.update { it - url }
    }

    private suspend fun run(schemeId: String, file: FileEntry) {
        val base = sha256(file.url.toByteArray()).take(32)
        val tmp = File(dir, "$base.part")
        _states.update { it + (file.url to DownloadState.Running(0, file.sizeBytes)) }
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            var bytes = 0L
            client.newCall(Request.Builder().url(file.url).build()).execute().use { resp ->
                if (!resp.isSuccessful) throw IOException("HTTP ${resp.code}")
                val body = resp.body ?: throw IOException("empty response")
                val total = body.contentLength().takeIf { it > 0 } ?: file.sizeBytes
                body.byteStream().use { input ->
                    tmp.outputStream().use { out ->
                        val buf = ByteArray(64 * 1024)
                        var lastReport = 0L
                        while (true) {
                            currentCoroutineContext().ensureActive()
                            val n = input.read(buf)
                            if (n < 0) break
                            out.write(buf, 0, n)
                            digest.update(buf, 0, n)
                            bytes += n
                            if (bytes - lastReport > 256 * 1024) {
                                lastReport = bytes
                                _states.update { it + (file.url to DownloadState.Running(bytes, total)) }
                            }
                        }
                    }
                }
            }
            val type = DocType.detect(tmp) ?: throw IOException("not a PDF or image")
            val target = File(dir, "$base.${type.name.lowercase()}")
            val previous = dao.download(file.url)?.localPath?.let(::File)
            if (target.exists() && !target.delete()) throw IOException("cannot replace old copy")
            if (!tmp.renameTo(target)) throw IOException("cannot save file")
            if (previous != null && previous.absolutePath != target.absolutePath) previous.delete()
            dao.putDownload(
                DownloadEntity(
                    fileUrl = file.url, schemeId = schemeId, title = file.title, localPath = target.absolutePath,
                    sha256 = digest.digest().toHex(), sizeBytes = bytes, downloadedAtMs = System.currentTimeMillis(),
                ),
            )
            _states.update { it - file.url }
        } catch (e: CancellationException) {
            tmp.delete()
            throw e
        } catch (e: Exception) {
            tmp.delete()
            _states.update { it + (file.url to DownloadState.Failed(e.message ?: e::class.simpleName.orEmpty())) }
        } finally {
            synchronized(jobs) { jobs.remove(file.url) }
        }
    }

    suspend fun delete(url: String) {
        dao.download(url)?.let { File(it.localPath).delete() }
        dao.deleteDownload(url)
    }

    fun totalBytes(list: List<DownloadEntity>): Long = list.sumOf { File(it.localPath).length() }

    companion object {
        fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).toHex()
        private fun ByteArray.toHex() = joinToString("") { "%02x".format(it) }
    }
}
