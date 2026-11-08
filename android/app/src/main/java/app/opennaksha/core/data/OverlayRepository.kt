package app.opennaksha.core.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import app.opennaksha.core.config.AppConfig
import app.opennaksha.core.model.SchemeRecord
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/** Downloads overlay PNGs from GitHub Pages and caches them (cache/overlays/). */
@Singleton
class OverlayRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val config: AppConfig,
    private val client: OkHttpClient,
) {
    private val dir: File get() = File(context.cacheDir, "overlays").apply { mkdirs() }

    /** Returns the overlay bitmap, from cache or network. Throws if unavailable. */
    suspend fun load(record: SchemeRecord): Bitmap = withContext(Dispatchers.IO) {
        val ov = record.overlay
        val rel = ov.url ?: throw IOException("no overlay")
        val version = (ov.pointsSha256 ?: ov.sourceSha256 ?: "v").take(12)
        val file = File(dir, "${record.id}-$version.png")
        if (!file.exists()) {
            val base = config.catalogBaseUrl ?: throw IOException("catalog URL not configured")
            val url = if (rel.startsWith("http")) rel else "$base/${rel.trimStart('/')}"
            client.newCall(Request.Builder().url(url).build()).execute().use { resp ->
                if (!resp.isSuccessful) throw IOException("HTTP ${resp.code}")
                val tmp = File(dir, file.name + ".part")
                resp.body!!.byteStream().use { input -> tmp.outputStream().use { input.copyTo(it) } }
                dir.listFiles { f -> f.name.startsWith("${record.id}-") }?.forEach { it.delete() }
                if (!tmp.renameTo(file)) throw IOException("cannot save overlay")
            }
        }
        BitmapFactory.decodeFile(file.absolutePath) ?: run {
            file.delete()
            throw IOException("invalid overlay image")
        }
    }

    fun clear() {
        dir.deleteRecursively()
    }
}
