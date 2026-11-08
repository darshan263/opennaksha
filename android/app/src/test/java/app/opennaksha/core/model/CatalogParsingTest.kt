package app.opennaksha.core.model

import app.opennaksha.TestData
import app.opennaksha.core.data.CatalogParser
import app.opennaksha.core.data.CatalogValidationException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CatalogParsingTest {
    @Test
    fun parsesIndex() {
        val index = CatalogParser.index(TestData.index)
        assertEquals(1, index.schemaVersion)
        assertEquals("2026-11-15T02:00:00Z", index.generatedAt)
        assertEquals("ટેસ્ટ", index.cities.single().nameGu)
        assertNull(index.latestAppVersion)
    }

    @Test
    fun parsesCityFileWithNullsAndUnknownKeys() {
        val city = CatalogParser.city(TestData.city, "testcity")
        assertEquals(2, city.schemes.size)
        val tp2 = city.schemes[0]
        assertEquals("2024-03-12", tp2.statusDate)
        assertEquals("PRELIMINARY SANCTIONED", tp2.statusLabel)
        assertNull(city.schemes[1].statusLabel)
        assertNull(tp2.nameGu)
        assertEquals(2, tp2.files.size)
        assertEquals("bbb", tp2.currentMap?.sha256)
        assertEquals(1, tp2.olderFiles.size)
        assertTrue(tp2.hasOverlay)
        assertTrue(tp2.overlay.isOutdated)
        assertEquals(listOf(72.8, 21.2), tp2.overlay.corners!![0])
        assertEquals("2026-11-15T02:00:00Z", tp2.mapUpdatedAt)

        val tp10 = city.schemes[1]
        assertTrue(tp10.removedFromSource)
        assertFalse(tp10.hasOverlay)
        assertNull(tp10.currentMap)
        assertNull(tp10.mapUpdatedAt)
    }

    @Test(expected = CatalogValidationException::class)
    fun rejectsCityFileForOtherCity() {
        CatalogParser.city(TestData.city, "elsewhere")
    }

    @Test(expected = CatalogValidationException::class)
    fun rejectsNewerSchemaVersion() {
        CatalogParser.index(TestData.index.replace("\"schema_version\":1", "\"schema_version\":2"))
    }

    @Test
    fun parsesChanges() {
        val changes = CatalogParser.changes(TestData.changes)!!
        assertEquals(2, changes.runs.size)
        assertEquals(listOf("map_file"), changes.runs[0].changed.single().what)
        assertNull(CatalogParser.changes("not json"))
    }

    @Test
    fun timesParseTimestampsAndDates() {
        assertEquals(1_789_437_600_000L, Times.millis("2026-09-15T02:00:00Z"))
        assertTrue(Times.millis("2024-03-12") > 0)
        assertEquals(0L, Times.millis(null))
        assertEquals(0L, Times.millis("garbage"))
    }

    @Test
    fun naturalOrderAndVersions() {
        assertEquals(listOf("2", "2A", "10", "100"), listOf("100", "10", "2A", "2").sortedWith(NaturalOrder))
        assertTrue(compareVersions("0.10.0", "0.9.1") > 0)
        assertEquals(0, compareVersions("v1.2", "1.2.0"))
        assertTrue(compareVersions("0.1.0", "0.2") < 0)
    }
}
