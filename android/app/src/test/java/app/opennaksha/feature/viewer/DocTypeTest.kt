package app.opennaksha.feature.viewer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File

class DocTypeTest {
    private fun temp(bytes: ByteArray): File = File.createTempFile("doc", ".bin").apply {
        writeBytes(bytes)
        deleteOnExit()
    }

    @Test
    fun detectsByMagicBytes() {
        assertEquals(DocType.PDF, DocType.detect(temp("%PDF-1.7\n...".toByteArray())))
        assertEquals(DocType.JPEG, DocType.detect(temp(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte()))))
        assertEquals(DocType.PNG, DocType.detect(temp(byteArrayOf(0x89.toByte(), 'P'.code.toByte(), 'N'.code.toByte(), 'G'.code.toByte(), 13, 10))))
        assertNull(DocType.detect(temp("<html>error page</html>".toByteArray())))
        assertNull(DocType.detect(File("does-not-exist")))
    }
}
