package app.opennaksha.core.config

import org.junit.Assert.assertEquals
import org.junit.Test

class CatalogUrlsTest {
    private val base = "https://example.github.io/opennaksha/"

    @Test
    fun buildsPublishedUrls() {
        assertEquals(
            "https://example.github.io/opennaksha/catalog/index.json",
            CatalogUrls.index(base),
        )
        assertEquals(
            "https://example.github.io/opennaksha/catalog/cities/surat.json",
            CatalogUrls.city(base, "surat"),
        )
        assertEquals(
            "https://example.github.io/opennaksha/catalog/changes.json",
            CatalogUrls.changes(base),
        )
        assertEquals(
            "https://example.github.io/opennaksha/overlays/surat-tp-57.png",
            CatalogUrls.overlay(base, "surat-tp-57"),
        )
    }
}
