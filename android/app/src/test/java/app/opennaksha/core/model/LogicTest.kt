package app.opennaksha.core.model

import app.opennaksha.TestData
import app.opennaksha.core.data.CatalogParser
import app.opennaksha.core.data.db.DownloadEntity
import app.opennaksha.core.data.isUpdateAvailable
import app.opennaksha.feature.catalog.ListFilter
import app.opennaksha.feature.catalog.NewsItem
import app.opennaksha.feature.catalog.SortBy
import app.opennaksha.feature.catalog.applyFilter
import app.opennaksha.feature.catalog.buildNews
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BadgeTest {
    @Test
    fun badges() {
        assertNull(badgeFor(10, 20, removed = false, previousVisitMs = null)) // first launch
        assertEquals(Badge.REMOVED, badgeFor(10, 20, removed = true, previousVisitMs = null))
        assertEquals(Badge.NEW, badgeFor(30, 30, removed = false, previousVisitMs = 25))
        assertEquals(Badge.UPDATED, badgeFor(10, 30, removed = false, previousVisitMs = 25))
        assertNull(badgeFor(10, 20, removed = false, previousVisitMs = 25))
    }

    @Test
    fun newsCountsPerCity() {
        val news = newsSince(
            listOf(summary("a", "x", first = 30, changed = 30), summary("b", "x", first = 10, changed = 40), summary("c", "y", first = 1, changed = 2)),
            sinceMs = 20,
        )
        assertEquals(listOf(CityNews("x", 1, 1)), news)
    }

    @Test
    fun filterAndSort() {
        val all = listOf(
            summary("t-10", "x", no = "10", status = "final"),
            summary("t-2", "x", no = "2", status = "draft", nameGu = "પાલ"),
            summary("t-2a", "x", no = "2A", status = "final", nameEn = "Adajan"),
        )
        assertEquals(listOf("2", "2A", "10"), applyFilter(all, ListFilter()).map { it.schemeNo })
        assertEquals(listOf("2A", "10"), applyFilter(all, ListFilter(status = "final")).map { it.schemeNo })
        assertEquals(listOf("2A"), applyFilter(all, ListFilter(query = "adaj")).map { it.schemeNo })
        assertEquals(listOf("2"), applyFilter(all, ListFilter(query = "પાલ")).map { it.schemeNo })
        assertEquals(listOf("10"), applyFilter(all, ListFilter(query = "tp 10")).map { it.schemeNo })
        assertEquals(3, applyFilter(all, ListFilter(sort = SortBy.DATE)).size)
    }

    private fun summary(
        id: String, city: String, first: Long = 0, changed: Long = 0, no: String = id, status: String = "final",
        nameEn: String? = null, nameGu: String? = null,
    ) = SchemeSummary(id, city, "TST", "TP", no, nameEn, nameGu, status, null, null, first, changed, false, "none")
}

class UnitConverterTest {
    private fun close(expected: Double, actual: Double, eps: Double = 1e-6) =
        assertEquals(expected, actual, eps * maxOf(1.0, kotlin.math.abs(expected)))

    @Test
    fun gujaratUnits() {
        close(0.83612736, convertArea(1.0, LandUnit.SQ_YARD, LandUnit.SQ_M))
        close(9.0, convertArea(1.0, LandUnit.SQ_YARD, LandUnit.SQ_FT))
        close(121.0, convertArea(1.0, LandUnit.GUNTHA, LandUnit.SQ_YARD))
        close(101.17141056, convertArea(1.0, LandUnit.GUNTHA, LandUnit.SQ_M))
        close(16.0, convertArea(1.0, LandUnit.VIGHA, LandUnit.GUNTHA))
        close(17424.0, convertArea(1.0, LandUnit.VIGHA, LandUnit.SQ_FT))
        close(40.0, convertArea(1.0, LandUnit.ACRE, LandUnit.GUNTHA), 1e-3)
        close(2.4710538, convertArea(1.0, LandUnit.HECTARE, LandUnit.ACRE))
        close(5.0, convertArea(convertArea(5.0, LandUnit.ACRE, LandUnit.VIGHA), LandUnit.VIGHA, LandUnit.ACRE))
    }
}

class UpdateAvailableTest {
    private val record = CatalogParser.city(TestData.city, "testcity").schemes[0] // current sha "bbb"

    private fun dl(url: String, sha: String) = DownloadEntity(url, record.id, "t", "/x", sha, 1, 0)

    @Test
    fun detectsNewerVersion() {
        assertTrue(isUpdateAvailable(dl("https://example.test/tp2.pdf", "aaa"), record))
        assertFalse(isUpdateAvailable(dl("https://example.test/tp2.pdf", "bbb"), record))
        assertFalse(isUpdateAvailable(dl("https://example.test/other.pdf", "zzz"), record))
        assertFalse(isUpdateAvailable(dl("https://example.test/tp2.pdf", "aaa"), null))
    }

    @Test
    fun replacedMapUrlCountsAsUpdate() {
        val moved = record.copy(
            files = record.files.map { it.copy(superseded = true) } +
                record.files.last().copy(url = "https://example.test/tp2-v2.pdf", superseded = false),
        )
        assertTrue(isUpdateAvailable(dl("https://example.test/tp2.pdf", "bbb"), moved))
    }
}

class WhatsNewTest {
    @Test
    fun groupsRunsByDay() {
        val runs = CatalogParser.changes(TestData.changes)!!.runs
        val items = buildNews(runs, emptyMap())
        val headers = items.filterIsInstance<NewsItem.Header>()
        assertEquals(2, headers.size)
        assertTrue(headers[0].day > headers[1].day)
        val entries = items.filterIsInstance<NewsItem.Entry>()
        assertEquals(listOf("map_file"), entries.first { it.id == "testcity-tst-tp-2-example" && it.what.isNotEmpty() }.what)
        assertEquals(4, entries.size) // 1 changed + 1 removed + 2 new
    }
}
