package app.opennaksha.core.data

import app.opennaksha.feature.viewer.DocType
import java.io.File
import java.io.IOException
import java.util.zip.ZipInputStream

/** Largest single map we unpack from a ZIP (guards against a broken or hostile archive). */
const val MAX_ZIPPED_MAP_BYTES = 400L * 1024 * 1024
private const val MAX_ZIP_ENTRIES = 200

/** True when [file] starts with the ZIP local-file signature "PK\u0003\u0004". */
fun isZip(file: File): Boolean = runCatching {
    file.inputStream().use { s ->
        val h = ByteArray(4)
        s.read(h) == 4 && h[0] == 'P'.code.toByte() && h[1] == 'K'.code.toByte() && h[2] == 3.toByte() && h[3] == 4.toByte()
    }
}.getOrDefault(false)

/**
 * Some authorities publish a map sheet as a ZIP holding one JPG/PDF (e.g. SMC's DP sheets A–Z).
 * Writes the first entry the viewer can show into [out] and returns its type, or null when the
 * archive has none. Entry names are never used as paths, so a crafted name cannot escape [out].
 */
fun extractMapFromZip(zip: File, out: File, maxBytes: Long = MAX_ZIPPED_MAP_BYTES): DocType? {
    ZipInputStream(zip.inputStream().buffered()).use { zin ->
        var seen = 0
        while (true) {
            val entry = zin.nextEntry ?: return null
            if (++seen > MAX_ZIP_ENTRIES) return null
            if (entry.isDirectory || entry.name.startsWith("__MACOSX/")) continue
            out.outputStream().use { o ->
                val buf = ByteArray(64 * 1024)
                var total = 0L
                while (true) {
                    val n = zin.read(buf)
                    if (n < 0) break
                    total += n
                    if (total > maxBytes) throw IOException("map inside the ZIP is larger than ${maxBytes / (1024 * 1024)} MB")
                    o.write(buf, 0, n)
                }
            }
            DocType.detect(out)?.let { return it }
        }
    }
}
