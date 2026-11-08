package app.opennaksha.feature.viewer

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapRegionDecoder
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.Closeable
import java.io.File
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log2
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * A document the viewer can render region by region. TP maps are huge single pages (PDFs up to
 * ~60 MB, JPGs of 100+ megapixels), so the viewer never renders a page at full zoom: a
 * low-resolution base image plus one viewport-sized tile of the visible region at the current zoom.
 */
interface TiledDocument : Closeable {
    val pageCount: Int

    /** Page size in document units (PDF points, or image pixels). */
    suspend fun pageSize(index: Int): IntSize

    /** Renders into a new width x height bitmap; [matrix] maps document units to bitmap pixels (scale + translate). */
    suspend fun render(index: Int, width: Int, height: Int, matrix: Matrix): Bitmap?
}

/** File types the viewer can show, detected from the first bytes. */
enum class DocType(val mime: String) {
    PDF("application/pdf"), JPEG("image/jpeg"), PNG("image/png");

    companion object {
        fun detect(file: File): DocType? = runCatching {
            file.inputStream().use { s ->
                val head = ByteArray(1024)
                val n = s.read(head)
                when {
                    n >= 3 && head[0] == 0xFF.toByte() && head[1] == 0xD8.toByte() && head[2] == 0xFF.toByte() -> JPEG
                    n >= 4 && head[0] == 0x89.toByte() && head[1] == 'P'.code.toByte() &&
                        head[2] == 'N'.code.toByte() && head[3] == 'G'.code.toByte() -> PNG
                    n > 4 && String(head, 0, n, Charsets.ISO_8859_1).contains("%PDF") -> PDF
                    else -> null
                }
            }
        }.getOrNull()

        fun open(file: File): TiledDocument? = when (detect(file)) {
            PDF -> runCatching { PdfDocument(file) }.getOrNull()
            JPEG, PNG -> runCatching { ImageDocument(file) }.getOrNull()
            null -> null
        }
    }
}

/** Large JPG/PNG maps via [BitmapRegionDecoder]: only the visible region is decoded, subsampled to the zoom. */
class ImageDocument(file: File) : TiledDocument {
    private val lock = Any()

    @Suppress("DEPRECATION") // newInstance(String) needs API 31; minSdk is 26
    private val decoder: BitmapRegionDecoder = BitmapRegionDecoder.newInstance(file.absolutePath, false)
        ?: throw IllegalArgumentException("cannot decode image")
    override val pageCount = 1

    override suspend fun pageSize(index: Int) = IntSize(decoder.width, decoder.height)

    override suspend fun render(index: Int, width: Int, height: Int, matrix: Matrix): Bitmap? = withContext(Dispatchers.IO) {
        if (width <= 0 || height <= 0) return@withContext null
        val v = FloatArray(9).also { matrix.getValues(it) }
        val s = v[Matrix.MSCALE_X]
        val tx = v[Matrix.MTRANS_X]
        val ty = v[Matrix.MTRANS_Y]
        val region = android.graphics.Rect(
            max(0, floor(-tx / s).toInt()),
            max(0, floor(-ty / s).toInt()),
            min(decoder.width, ceil((width - tx) / s).toInt()),
            min(decoder.height, ceil((height - ty) / s).toInt()),
        )
        if (region.width() <= 0 || region.height() <= 0) return@withContext null
        // Largest power of two not above 1/s: decode just enough pixels for the target size.
        val sample = if (s >= 1f) 1 else 1 shl floor(log2(1f / s)).toInt().coerceIn(0, 6)
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        val part = synchronized(lock) {
            if (decoder.isRecycled) return@withContext null
            decoder.decodeRegion(region, opts)
        } ?: return@withContext null
        val out = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        out.eraseColor(Color.WHITE)
        val dst = RectF(region.left * s + tx, region.top * s + ty, region.right * s + tx, region.bottom * s + ty)
        Canvas(out).drawBitmap(part, null, dst, Paint(Paint.FILTER_BITMAP_FLAG))
        part.recycle()
        out
    }

    override fun close() {
        synchronized(lock) { decoder.recycle() }
    }
}

/** Wraps [PdfRenderer] (not thread-safe) behind a lock. */
class PdfDocument(file: File) : TiledDocument {
    private val lock = Any()
    private val pfd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
    private val renderer = PdfRenderer(pfd)
    private var closed = false
    override val pageCount: Int = renderer.pageCount

    /** Page size in PDF points. */
    override suspend fun pageSize(index: Int): IntSize = withContext(Dispatchers.IO) {
        synchronized(lock) {
            check(!closed)
            renderer.openPage(index).use { IntSize(it.width, it.height) }
        }
    }

    override suspend fun render(index: Int, width: Int, height: Int, matrix: Matrix): Bitmap? = withContext(Dispatchers.IO) {
        if (width <= 0 || height <= 0) return@withContext null
        val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        bmp.eraseColor(Color.WHITE)
        synchronized(lock) {
            if (closed) return@withContext null
            renderer.openPage(index).use { it.render(bmp, null, matrix, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY) }
        }
        bmp
    }

    override fun close() {
        synchronized(lock) {
            if (closed) return
            closed = true
            renderer.close()
            pfd.close()
        }
    }
}

private const val BASE_MAX_SIDE = 2048f
private data class Tile(val image: ImageBitmap, val pageRect: Rect)

@Composable
fun PdfPageView(doc: TiledDocument, pageIndex: Int, modifier: Modifier = Modifier) {
    var viewSize by remember { mutableStateOf(IntSize.Zero) }
    val pageSize by produceState<IntSize?>(null, doc, pageIndex) { value = runCatching { doc.pageSize(pageIndex) }.getOrNull() }
    var scale by remember(pageIndex) { mutableFloatStateOf(1f) }
    var offset by remember(pageIndex) { mutableStateOf(Offset.Zero) }
    var tile by remember(pageIndex) { mutableStateOf<Tile?>(null) }

    val ps = pageSize
    val fit = if (ps == null || viewSize == IntSize.Zero) 0f else min(viewSize.width / ps.width.toFloat(), viewSize.height / ps.height.toFloat())
    // Allow zooming to at least ~4 px per PDF point (≈ 288 dpi) for small print on big sheets.
    val maxScale = if (fit > 0f) max(8f, 4f / fit) else 8f

    val base by produceState<ImageBitmap?>(null, doc, pageIndex, ps, fit) {
        if (ps == null || fit <= 0f) return@produceState
        val k = min(BASE_MAX_SIDE / max(ps.width, ps.height), fit * 2f)
        val m = Matrix().apply { setScale(k, k) }
        value = doc.render(pageIndex, (ps.width * k).roundToInt(), (ps.height * k).roundToInt(), m)?.asImageBitmap()
    }

    fun clamp(o: Offset, s: Float): Offset {
        if (ps == null) return o
        val dw = ps.width * fit * s
        val dh = ps.height * fit * s
        val mx = max(0f, (dw - viewSize.width) / 2f)
        val my = max(0f, (dh - viewSize.height) / 2f)
        return Offset(o.x.coerceIn(-mx, mx), o.y.coerceIn(-my, my))
    }

    // Re-render the sharp tile after gestures settle (keys change on every frame → debounced).
    LaunchedEffect(doc, pageIndex, scale, offset, viewSize, ps) {
        if (ps == null || fit <= 0f || scale <= 1.05f) {
            tile = null
            return@LaunchedEffect
        }
        delay(180)
        val s = fit * scale
        val dw = ps.width * s
        val dh = ps.height * s
        val left = (viewSize.width - dw) / 2f + offset.x
        val top = (viewSize.height - dh) / 2f + offset.y
        val x0 = max(0f, left)
        val y0 = max(0f, top)
        val x1 = min(viewSize.width.toFloat(), left + dw)
        val y1 = min(viewSize.height.toFloat(), top + dh)
        if (x1 <= x0 || y1 <= y0) return@LaunchedEffect
        val m = Matrix().apply {
            setScale(s, s)
            postTranslate(left - x0, top - y0)
        }
        val bmp = doc.render(pageIndex, (x1 - x0).roundToInt(), (y1 - y0).roundToInt(), m) ?: return@LaunchedEffect
        tile = Tile(bmp.asImageBitmap(), Rect((x0 - left) / s, (y0 - top) / s, (x1 - left) / s, (y1 - top) / s))
    }

    Box(
        modifier
            .fillMaxSize()
            .clipToBounds()
            .onSizeChanged { viewSize = it }
            .pointerInput(ps, viewSize) {
                detectTapGestures(onDoubleTap = { p ->
                    val center = Offset(viewSize.width / 2f, viewSize.height / 2f)
                    val newScale = if (scale > 1.5f) 1f else 3f
                    val factor = newScale / scale
                    offset = clamp((offset + center - p) * factor + p - center, newScale)
                    scale = newScale
                })
            }
            .pointerInput(ps, viewSize, maxScale) {
                detectTransformGestures { centroid, pan, zoom, _ ->
                    val center = Offset(viewSize.width / 2f, viewSize.height / 2f)
                    val newScale = (scale * zoom).coerceIn(1f, maxScale)
                    val factor = newScale / scale
                    offset = clamp((offset + center - centroid) * factor + centroid - center + pan, newScale)
                    scale = newScale
                }
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val b = base ?: return@Canvas
            if (ps == null || fit <= 0f) return@Canvas
            val s = fit * scale
            val dw = ps.width * s
            val dh = ps.height * s
            val left = (size.width - dw) / 2f + offset.x
            val top = (size.height - dh) / 2f + offset.y
            drawImage(
                b,
                dstOffset = IntOffset(left.roundToInt(), top.roundToInt()),
                dstSize = IntSize(dw.roundToInt(), dh.roundToInt()),
                filterQuality = FilterQuality.Medium,
            )
            tile?.let { t ->
                val r = t.pageRect
                drawImage(
                    t.image,
                    dstOffset = IntOffset((left + r.left * s).roundToInt(), (top + r.top * s).roundToInt()),
                    dstSize = IntSize((r.width * s).roundToInt(), (r.height * s).roundToInt()),
                    filterQuality = FilterQuality.Medium,
                )
            }
        }
    }
}
