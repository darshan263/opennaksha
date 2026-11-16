package app.opennaksha.feature.catalog

import app.opennaksha.core.model.Notice
import org.junit.Assert.assertEquals
import org.junit.Test

class NoticesTest {
    private fun notice(id: String, firstSeen: String) =
        Notice(id = id, title = id, url = "https://x.test/$id.pdf", firstSeen = firstSeen)

    @Test
    fun newSinceUsesSeenThenPreviousVisitThenNothing() {
        assertEquals(5L, noticesNewSince(5L, 9L))
        assertEquals(9L, noticesNewSince(null, 9L))
        assertEquals(Long.MAX_VALUE, noticesNewSince(null, null))
    }

    @Test
    fun countsNoticesFirstSeenAfterTheMark() {
        val list = listOf(
            notice("old", "2026-11-01T02:00:00Z"),
            notice("new", "2026-11-15T02:00:00Z"),
        )
        val mark = java.time.Instant.parse("2026-11-08T00:00:00Z").toEpochMilli()
        assertEquals(1, countNewNotices(list, mark))
        assertEquals(0, countNewNotices(list, Long.MAX_VALUE))
    }
}
