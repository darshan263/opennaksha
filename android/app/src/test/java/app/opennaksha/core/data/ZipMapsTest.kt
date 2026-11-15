package app.opennaksha.core.data

import app.opennaksha.feature.viewer.DocType
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.io.IOException
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class ZipMapsTest {
    private val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte()) + ByteArray(5000) { (it % 251).toByte() }

    private fun temp(suffix: String = ".bin"): File = File.createTempFile("zipmaps", suffix).apply { deleteOnExit() }

    private fun zipOf(vararg entries: Pair<String, ByteArray?>): File = temp(".zip").also { f ->
        ZipOutputStream(f.outputStream()).use { z ->
            for ((name, bytes) in entries) {
                z.putNextEntry(ZipEntry(name))
                bytes?.let(z::write)
                z.closeEntry()
            }
        }
    }

    @Test
    fun extractsTheSheetImage() {
        // Like SMC's sheets: one JPG named after the villages, commas and all.
        val zip = zipOf("P-Abrama,Gothan,.jpg" to jpeg)
        assertTrue(isZip(zip))
        val out = temp()
        assertEquals(DocType.JPEG, extractMapFromZip(zip, out))
        assertArrayEquals(jpeg, out.readBytes())
    }

    @Test
    fun skipsFoldersAndNonMapEntries() {
        val zip = zipOf("sheet/" to null, "readme.txt" to "hello".toByteArray(), "__MACOSX/._x.jpg" to jpeg, "sheet/x.pdf" to "%PDF-1.4 x".toByteArray())
        val out = temp()
        assertEquals(DocType.PDF, extractMapFromZip(zip, out))
        assertEquals("%PDF-1.4 x", out.readText())
    }

    @Test
    fun noMapInsideReturnsNull() {
        assertNull(extractMapFromZip(zipOf("a.txt" to "x".toByteArray(), "b.dwg" to ByteArray(10)), temp()))
    }

    @Test
    fun hostileEntryNamesStayInsideOut() {
        val out = temp()
        assertEquals(DocType.JPEG, extractMapFromZip(zipOf("../../evil.jpg" to jpeg), out))
        assertFalse(File(out.parentFile?.parentFile, "evil.jpg").exists())
    }

    @Test
    fun oversizedEntryFails() {
        val zip = zipOf("big.jpg" to jpeg)
        assertThrows(IOException::class.java) { extractMapFromZip(zip, temp(), maxBytes = 1000) }
    }

    @Test
    fun recognisesZipOnlyBySignature() {
        assertFalse(isZip(temp().apply { writeBytes(jpeg) }))
        assertFalse(isZip(File("does-not-exist")))
    }
}
